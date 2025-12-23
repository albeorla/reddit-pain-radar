import httpx
import pytest
import respx

from pain_radar.agent.models import AgentState
from pain_radar.reddit_async import RedditPost


@pytest.mark.asyncio
async def test_agent_tools_abstraction():
    # This test will fail because pain_radar.agent.tools doesn't exist yet
    from pain_radar.agent.tools import fetch_more_comments_tool, search_related_posts_tool

    post = RedditPost(
        id="p1",
        subreddit="s1",
        title="T1",
        body="B1",
        created_utc=0,
        score=0,
        num_comments=0,
        url="U1",
        permalink="/r/s1/p1/",
    )
    state: AgentState = {
        "post": post,
        "extraction": None,
        "critique": None,
        "score": 0,
        "attempts": 0,
        "relevant": True,
        "extra_comments": [],
        "related_posts": [],
    }

    with respx.mock(base_url="https://www.reddit.com") as respx_mock:
        # Mock for fetch_more_comments
        json_content = [{}, {"data": {"children": [{"kind": "t1", "data": {"body": "New Comment"}}]}}]
        respx_mock.get("/r/s1/p1/.json").mock(return_value=httpx.Response(200, json=json_content))

        # Mock for search_related_posts
        rss_content = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><id>t3_p2</id><link>https://www.reddit.com/r/s1/comments/p2/title/</link><title>RT</title><content type="html">RB</content></entry></feed>"""
        respx_mock.get("/r/s1/search.rss?q=T1&restrict_sr=on&sort=relevance").mock(
            return_value=httpx.Response(200, text=rss_content)
        )

        async with httpx.AsyncClient() as client:
            # Test tools
            comments_update = await fetch_more_comments_tool(client, state)
            assert "extra_comments" in comments_update
            assert comments_update["extra_comments"] == ["New Comment"]

            search_update = await search_related_posts_tool(client, state)
            assert "related_posts" in search_update
            assert len(search_update["related_posts"]) == 1
            assert search_update["related_posts"][0].id == "p2"
