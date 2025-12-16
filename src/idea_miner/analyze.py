"""Combined extraction and scoring in a single LLM call."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .logging_config import get_logger
from .models import ExtractionState, FullAnalysis
from .prompts import FULL_ANALYSIS_SYSTEM_PROMPT, FULL_ANALYSIS_USER_TEMPLATE
from .reddit_async import RedditPost

logger = get_logger(__name__)


class LLMAnalysisError(Exception):
    """Error during LLM analysis."""

    pass


FULL_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", FULL_ANALYSIS_SYSTEM_PROMPT),
    ("user", FULL_ANALYSIS_USER_TEMPLATE),
])


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=30),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
)
async def analyze_post(llm: BaseChatModel, post: RedditPost) -> FullAnalysis:
    """Analyze a Reddit post in a single LLM call (extract + score).

    This is more efficient than separate extract/score calls for most use cases.

    Args:
        llm: LangChain chat model with structured output support
        post: Reddit post to analyze

    Returns:
        FullAnalysis with extraction and optional score

    Raises:
        LLMAnalysisError: If analysis fails
    """
    logger.debug("analyzing_post", post_id=post.id, title=post.title[:50])

    try:
        # Create chain with structured output
        chain = FULL_ANALYSIS_PROMPT | llm.with_structured_output(FullAnalysis)

        # Format comments with indices for attribution
        comments_formatted = "\n".join(
            f"[{i}] {c}" for i, c in enumerate(post.top_comments)
        ) if post.top_comments else "(no comments)"

        # Invoke the chain
        result = await chain.ainvoke({
            "title": post.title,
            "body": post.body or "(no body)",
            "comments": comments_formatted,
        })

        # Log results based on extraction state
        state = result.extraction.extraction_state
        
        if state == ExtractionState.EXTRACTED and result.score:
            logger.info(
                "post_analyzed",
                post_id=post.id,
                idea=result.extraction.idea_summary[:80],
                total=result.score.total,
                confidence=result.score.confidence,
                evidence_strength=result.extraction.evidence_strength,
                disqualified=False,
            )
        elif state == ExtractionState.DISQUALIFIED:
            logger.info(
                "post_analyzed",
                post_id=post.id,
                idea=result.extraction.idea_summary[:80],
                total=result.score.total if result.score else 0,
                disqualified=True,
                reason=result.extraction.risk_flags[0] if result.extraction.risk_flags else "unknown",
            )
        else:  # NOT_EXTRACTABLE
            logger.info(
                "post_not_extractable",
                post_id=post.id,
                reason=result.extraction.not_extractable_reason or "unknown",
            )

        return result

    except Exception as e:
        logger.error("analysis_failed", post_id=post.id, error=str(e))
        raise LLMAnalysisError(f"Failed to analyze post {post.id}: {e}") from e
