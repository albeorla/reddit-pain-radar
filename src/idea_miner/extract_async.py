"""Async LangChain extraction for ideas from Reddit posts."""

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
from .models import IdeaExtraction
from .prompts import EXTRACT_SYSTEM_PROMPT, EXTRACT_USER_TEMPLATE
from .reddit_async import RedditPost

logger = get_logger(__name__)


class LLMExtractionError(Exception):
    """Error during LLM extraction."""

    pass


EXTRACT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", EXTRACT_SYSTEM_PROMPT),
    ("user", EXTRACT_USER_TEMPLATE),
])


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=30),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
)
async def extract_idea(llm: BaseChatModel, post: RedditPost) -> IdeaExtraction:
    """Extract a business idea from a Reddit post using LLM.

    Args:
        llm: LangChain chat model with structured output support
        post: Reddit post to analyze

    Returns:
        IdeaExtraction with structured idea details

    Raises:
        LLMExtractionError: If extraction fails
    """
    logger.debug("extracting_idea", post_id=post.id, title=post.title[:50])

    try:
        # Create chain with structured output
        chain = EXTRACT_PROMPT | llm.with_structured_output(IdeaExtraction)

        # Format comments with indices
        comments_formatted = "\n\n".join(
            f"[{i}] {c}" for i, c in enumerate(post.top_comments)
        )

        # Invoke the chain
        result = await chain.ainvoke({
            "title": post.title,
            "body": post.body or "(no body)",
            "comments": comments_formatted or "(no comments)",
        })

        logger.info(
            "idea_extracted",
            post_id=post.id,
            idea=result.idea_summary[:100],
            signals_count=len(result.evidence_signals),
        )
        return result

    except Exception as e:
        logger.error("extraction_failed", post_id=post.id, error=str(e))
        raise LLMExtractionError(f"Failed to extract idea from post {post.id}: {e}") from e
