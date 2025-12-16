"""Pipeline orchestration with async concurrency."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List, Optional, Tuple

from langchain_core.language_models import BaseChatModel

from .analyze import LLMAnalysisError, analyze_post
from .config import Settings
from .logging_config import get_logger
from .models import FullAnalysis
from .reddit_async import RedditPost, fetch_all_subreddits
from .store import AsyncStore

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    """Result from running the pipeline."""

    run_id: Optional[int]
    posts_fetched: int
    posts_analyzed: int
    ideas_saved: int
    errors: int
    qualified_ideas: int
    top_ideas: List[dict]


async def process_post(
    llm: BaseChatModel,
    store: AsyncStore,
    post: RedditPost,
    sem: asyncio.Semaphore,
    run_id: Optional[int] = None,
) -> Tuple[str, Optional[FullAnalysis], Optional[str]]:
    """Process a single post: analyze and save.

    Args:
        llm: LangChain chat model
        store: Async storage
        post: Reddit post to process
        sem: Semaphore for concurrency control
        run_id: Optional run ID to associate with saved ideas

    Returns:
        Tuple of (post_id, analysis or None, error message or None)
    """
    async with sem:
        try:
            analysis = await analyze_post(llm, post)
            await store.save_idea(post, analysis.extraction, analysis.score, run_id=run_id)
            return (post.id, analysis, None)
        except LLMAnalysisError as e:
            logger.warning("post_analysis_failed", post_id=post.id, error=str(e))
            return (post.id, None, str(e))
        except Exception as e:
            logger.error("post_processing_failed", post_id=post.id, error=str(e))
            return (post.id, None, str(e))


async def run_pipeline(
    settings: Settings,
    llm: BaseChatModel,
    fetch_new: bool = True,
    process_limit: Optional[int] = None,
) -> PipelineResult:
    """Run the full idea mining pipeline.

    Args:
        settings: Application settings
        llm: LangChain chat model for analysis
        fetch_new: Whether to fetch new posts from Reddit
        process_limit: Maximum posts to process (None = all)

    Returns:
        PipelineResult with stats and top ideas
    """
    logger.info(
        "pipeline_starting",
        subreddits=settings.subreddits,
        fetch_new=fetch_new,
        process_limit=process_limit,
    )

    # Initialize storage
    store = AsyncStore(settings.db_path)
    await store.connect()
    await store.init_db()

    posts: List[RedditPost] = []
    run_id: Optional[int] = None

    try:
        # Create a run record
        run_id = await store.create_run(settings.subreddits)
        logger.info("run_created", run_id=run_id)

        # Fetch new posts if requested
        if fetch_new:
            posts = await fetch_all_subreddits(
                subreddits=settings.subreddits,
                listing=settings.listing,
                limit=settings.posts_per_subreddit,
                top_comments=settings.top_comments,
                max_concurrency=settings.max_concurrency,
                user_agent=settings.user_agent,
            )
            await store.upsert_posts(posts)
        else:
            # Load unprocessed posts from database
            limit = process_limit or 1000
            posts = await store.get_unprocessed_posts(limit=limit)
            logger.info("loaded_unprocessed_posts", count=len(posts))

        # Apply process limit
        if process_limit and len(posts) > process_limit:
            posts = posts[:process_limit]

        # Process posts concurrently
        sem = asyncio.Semaphore(settings.max_concurrency)
        tasks = [process_post(llm, store, post, sem, run_id) for post in posts]
        results = await asyncio.gather(*tasks)

        # Count results by extraction state
        from .models import ExtractionState
        
        analyzed = sum(1 for _, analysis, _ in results if analysis is not None)
        errors = sum(1 for _, _, error in results if error is not None)
        
        # Count by extraction state
        extracted = sum(
            1 for _, analysis, _ in results 
            if analysis is not None and analysis.extraction.extraction_state == ExtractionState.EXTRACTED
        )
        not_extractable = sum(
            1 for _, analysis, _ in results 
            if analysis is not None and analysis.extraction.extraction_state == ExtractionState.NOT_EXTRACTABLE
        )
        disqualified = sum(
            1 for _, analysis, _ in results 
            if analysis is not None and analysis.extraction.extraction_state == ExtractionState.DISQUALIFIED
        )
        qualified = sum(
            1 for _, analysis, _ in results 
            if analysis is not None 
            and analysis.extraction.extraction_state == ExtractionState.EXTRACTED
            and analysis.score is not None
            and not analysis.score.disqualified
        )

        # Get top ideas
        top_ideas = await store.get_top_ideas(limit=10)

        # Update run record
        await store.update_run(
            run_id=run_id,
            posts_fetched=len(posts),
            posts_analyzed=analyzed,
            ideas_saved=extracted + disqualified,  # Only save extractable ideas
            qualified_ideas=qualified,
            errors=errors,
            status="completed",
        )

        # Log stats
        stats = await store.get_stats()
        logger.info(
            "pipeline_complete", 
            run_id=run_id, 
            extracted=extracted,
            not_extractable=not_extractable,
            disqualified=disqualified,
            qualified=qualified,
            **stats
        )

        return PipelineResult(
            run_id=run_id,
            posts_fetched=len(posts),
            posts_analyzed=analyzed,
            ideas_saved=analyzed,
            errors=errors,
            qualified_ideas=qualified,
            top_ideas=top_ideas,
        )

    except Exception as e:
        # Update run as failed
        if run_id:
            await store.update_run(
                run_id=run_id,
                posts_fetched=len(posts),
                posts_analyzed=0,
                ideas_saved=0,
                qualified_ideas=0,
                errors=1,
                status="failed",
            )
        raise

    finally:
        await store.close()


async def run_fetch_only(settings: Settings) -> int:
    """Fetch posts from Reddit without processing.

    Args:
        settings: Application settings

    Returns:
        Number of posts fetched
    """
    logger.info("fetch_only_starting", subreddits=settings.subreddits)

    store = AsyncStore(settings.db_path)
    await store.connect()
    await store.init_db()

    try:
        posts = await fetch_all_subreddits(
            subreddits=settings.subreddits,
            listing=settings.listing,
            limit=settings.posts_per_subreddit,
            top_comments=settings.top_comments,
            max_concurrency=settings.max_concurrency,
            user_agent=settings.user_agent,
        )
        await store.upsert_posts(posts)
        return len(posts)
    finally:
        await store.close()


async def run_process_only(
    settings: Settings,
    llm: BaseChatModel,
    limit: Optional[int] = None,
) -> PipelineResult:
    """Process existing unprocessed posts.

    Args:
        settings: Application settings
        llm: LangChain chat model
        limit: Maximum posts to process

    Returns:
        PipelineResult with stats
    """
    return await run_pipeline(
        settings=settings,
        llm=llm,
        fetch_new=False,
        process_limit=limit,
    )
