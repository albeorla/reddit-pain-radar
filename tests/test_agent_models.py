from pain_radar.agent.models import AgentState
from pain_radar.reddit_async import RedditPost


def test_agent_state_initialization():
    post = RedditPost(
        id="test",
        subreddit="test",
        title="test",
        body="test",
        created_utc=0,
        score=0,
        num_comments=0,
        url="test",
        permalink="test",
    )
    state = AgentState(
        post=post,
        extraction=None,
        critique=None,
        score=0,
        attempts=0,
        relevant=None,
        extra_comments=[],
        related_posts=[],
    )
    assert state["post"].id == "test"
    assert state["attempts"] == 0
    assert state["relevant"] is None
