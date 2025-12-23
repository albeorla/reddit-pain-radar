import operator
from typing import Annotated, TypedDict

from pain_radar.models import PainSignal
from pain_radar.reddit_async import RedditPost


class AgentState(TypedDict):
    """State of the Adaptive Researcher agent."""

    post: RedditPost
    extraction: PainSignal | None
    critique: str | None
    score: int
    attempts: int
    relevant: bool | None
    extra_comments: Annotated[list[str], operator.add]
    related_posts: Annotated[list[RedditPost], operator.add]
