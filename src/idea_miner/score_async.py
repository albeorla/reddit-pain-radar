"""Async LangChain scoring for extracted ideas."""

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
from .models import IdeaExtraction, IdeaScore
from .prompts import SCORE_SYSTEM_PROMPT, SCORE_USER_TEMPLATE

logger = get_logger(__name__)


class LLMScoringError(Exception):
    """Error during LLM scoring."""

    pass


SCORE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SCORE_SYSTEM_PROMPT),
    ("user", SCORE_USER_TEMPLATE),
])


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=30),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
)
async def score_idea(llm: BaseChatModel, extraction: IdeaExtraction) -> IdeaScore:
    """Score an extracted idea using LLM.

    Args:
        llm: LangChain chat model with structured output support
        extraction: IdeaExtraction to score

    Returns:
        IdeaScore with rubric scores and evaluation

    Raises:
        LLMScoringError: If scoring fails
    """
    logger.debug("scoring_idea", idea=extraction.idea_summary[:50])

    try:
        # Create chain with structured output
        chain = SCORE_PROMPT | llm.with_structured_output(IdeaScore)

        # Invoke the chain
        result = await chain.ainvoke({
            "idea_summary": extraction.idea_summary,
            "target_user": extraction.target_user,
            "pain_point": extraction.pain_point,
            "proposed_solution": extraction.proposed_solution,
            "evidence_signals": "\n".join(f"- {s}" for s in extraction.evidence_signals) or "None",
            "risk_flags": "\n".join(f"- {f}" for f in extraction.risk_flags) or "None",
        })

        logger.info(
            "idea_scored",
            idea=extraction.idea_summary[:50],
            total=result.total,
            disqualified=result.disqualified,
        )
        return result

    except Exception as e:
        logger.error("scoring_failed", idea=extraction.idea_summary[:50], error=str(e))
        raise LLMScoringError(f"Failed to score idea: {e}") from e
