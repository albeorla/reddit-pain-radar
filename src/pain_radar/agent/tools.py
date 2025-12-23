import httpx

from pain_radar.agent.models import AgentState
from pain_radar.reddit_async import fetch_more_comments, search_related_posts


async def fetch_more_comments_tool(client: httpx.AsyncClient, state: AgentState) -> dict:
    """Agent tool to fetch more comments for the current post."""
    post = state["post"]
    # We skip what we already have (top_comments + extra_comments)
    current_count = len(post.top_comments) + len(state.get("extra_comments", []))

    # Fetch next 10 comments
    new_comments = await fetch_more_comments(client, post, start_index=current_count, limit=10)

    return {"extra_comments": new_comments}


async def search_related_posts_tool(client: httpx.AsyncClient, state: AgentState) -> dict:
    """Agent tool to search for related posts based on the title."""
    post = state["post"]
    query = post.title

    # Search for up to 5 related posts in the same subreddit
    related = await search_related_posts(client, subreddit=post.subreddit, query=query, limit=5)

    # Filter out the current post if it appears in results
    related = [p for p in related if p.id != post.id]

    return {"related_posts": related}
