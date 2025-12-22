"""Reddit scraping using RSS feeds and HTTP requests (no API required).

Uses centralized HTTP client and retry policies for robustness.
"""

from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass, field

import feedparser
import httpx
from bs4 import BeautifulSoup

from .http_client import create_http_client
from .logging_config import get_logger
from .retry_policy import (
    RateLimitError,
    adaptive_sleep,
    check_response_for_retry,
    http_retry,
)

logger = get_logger(__name__)

# Reddit RSS base URL
REDDIT_BASE = "https://www.reddit.com"

# Polite delay between requests (seconds)
REQUEST_DELAY = 0.5


@dataclass
class RedditPost:
    """Normalized Reddit post data."""

    id: str
    subreddit: str
    title: str
    body: str
    created_utc: int
    score: int
    num_comments: int
    url: str
    permalink: str
    top_comments: list[str] = field(default_factory=list)


def _extract_post_id(link: str) -> str:
    """Extract post ID from Reddit URL."""
    # URLs look like: https://www.reddit.com/r/subreddit/comments/abc123/title/
    match = re.search(r"/comments/([a-z0-9]+)/", link)
    return match.group(1) if match else ""


def _clean_html(text: str) -> str:
    """Clean HTML entities and tags from text."""
    # Decode HTML entities
    text = html.unescape(text)
    # Remove HTML tags
    soup = BeautifulSoup(text, "lxml")
    return soup.get_text(separator=" ").strip()


def _parse_rss_entry(entry: dict, subreddit: str) -> RedditPost | None:
    """Parse an RSS feed entry into a RedditPost."""
    try:
        link = entry.get("link", "")
        post_id = _extract_post_id(link)
        if not post_id:
            return None

        # Extract title
        title = entry.get("title", "")

        # Extract body from content or summary
        body = ""
        if "content" in entry and entry["content"]:
            body = entry["content"][0].get("value", "")
        elif "summary" in entry:
            body = entry.get("summary", "")
        body = _clean_html(body)

        # Parse timestamp
        created_utc = 0
        if "published_parsed" in entry and entry["published_parsed"]:
            import time

            created_utc = int(time.mktime(entry["published_parsed"]))

        return RedditPost(
            id=post_id,
            subreddit=subreddit,
            title=title,
            body=body,
            created_utc=created_utc,
            score=0,  # Not available in RSS
            num_comments=0,  # Will be updated if we scrape the page
            url=link,
            permalink=link,
            top_comments=[],
        )
    except Exception as e:
        logger.warning("rss_entry_parse_failed", error=str(e))
        return None


@http_retry
async def _fetch_rss(
    client: httpx.AsyncClient,
    subreddit: str,
    listing: str,
) -> list[RedditPost]:
    """Fetch posts from a subreddit's RSS feed.

    Args:
        client: HTTP client
        subreddit: Subreddit name
        listing: Listing type (hot, new, top, rising)

    Returns:
        List of RedditPost objects
    """
    url = f"{REDDIT_BASE}/r/{subreddit}/{listing}.rss"
    logger.debug("fetching_rss", url=url)

    response = await client.get(url)

    # Handle special cases (don't retry these)
    if response.status_code == 403:
        logger.warning("subreddit_private_or_banned", subreddit=subreddit)
        return []
    if response.status_code == 404:
        logger.warning("subreddit_not_found", subreddit=subreddit)
        return []

    # Check for retryable errors (429, 5xx)
    check_response_for_retry(response)

    # Parse RSS feed
    feed = feedparser.parse(response.text)
    posts = []

    for entry in feed.entries:
        post = _parse_rss_entry(entry, subreddit)
        if post:
            posts.append(post)

    logger.info("rss_fetched", subreddit=subreddit, posts=len(posts))
    return posts


@http_retry
async def _scrape_comments(
    client: httpx.AsyncClient,
    post: RedditPost,
    limit: int,
) -> list[str]:
    """Scrape top comments from a Reddit post page.

    Args:
        client: HTTP client
        post: RedditPost to fetch comments for
        limit: Maximum number of comments

    Returns:
        List of comment text strings
    """
    # Use .json endpoint for easier parsing
    json_url = f"{post.permalink}.json"
    if not json_url.startswith("http"):
        json_url = f"{REDDIT_BASE}{json_url}"

    # Ensure .json suffix
    if "?" in json_url:
        json_url = json_url.split("?")[0]
    if not json_url.endswith(".json"):
        json_url = json_url.rstrip("/") + ".json"

    logger.debug("scraping_comments", url=json_url)

    response = await client.get(json_url)

    # Handle non-200 responses
    if response.status_code == 403:
        logger.debug("post_private_or_deleted", post_id=post.id)
        return []
    if response.status_code == 404:
        logger.debug("post_not_found", post_id=post.id)
        return []

    # Check for retryable errors
    check_response_for_retry(response)

    try:
        data = response.json()
    except Exception as e:
        logger.warning("json_parse_failed", post_id=post.id, error=str(e))
        return []

    # Reddit JSON structure: [post_data, comments_data]
    if not isinstance(data, list) or len(data) < 2:
        return []

    comments_data = data[1].get("data", {}).get("children", [])
    comments = []

    for child in comments_data[:limit]:
        if child.get("kind") != "t1":  # t1 = comment
            continue
        body = child.get("data", {}).get("body", "")
        if body and body not in ["[deleted]", "[removed]"]:
            # Clean up the comment text
            body = _clean_html(body)
            if body:
                comments.append(body)

    return comments


async def fetch_posts(
    client: httpx.AsyncClient,
    subreddit: str,
    listing: str,
    limit: int,
    top_comments: int,
    sem: asyncio.Semaphore,
) -> list[RedditPost]:
    """Fetch posts from a subreddit using RSS and optionally scrape comments.

    Args:
        client: Shared HTTP client
        subreddit: Subreddit name (without r/)
        listing: Listing type (hot, new, top, rising)
        limit: Maximum posts to fetch (RSS limited to ~25)
        top_comments: Number of comments to scrape per post (0 to skip)
        sem: Semaphore for concurrency control

    Returns:
        List of RedditPost objects
    """
    logger.info("fetching_subreddit", subreddit=subreddit, listing=listing)

    # Fetch RSS feed
    async with sem:
        try:
            posts = await _fetch_rss(client, subreddit, listing)
        except RateLimitError as e:
            logger.warning("rate_limited", subreddit=subreddit, retry_after=e.retry_after)
            await adaptive_sleep(e.retry_after, default=30.0)
            posts = await _fetch_rss(client, subreddit, listing)
        except Exception as e:
            logger.error("rss_fetch_failed", subreddit=subreddit, error=str(e))
            return []

    # Limit posts
    posts = posts[:limit]

    # Scrape comments if requested
    if top_comments > 0:
        for post in posts:
            async with sem:
                # Polite delay between requests
                await asyncio.sleep(REQUEST_DELAY)
                try:
                    post.top_comments = await _scrape_comments(client, post, top_comments)
                except RateLimitError as e:
                    logger.warning("rate_limited", post_id=post.id, retry_after=e.retry_after)
                    await adaptive_sleep(e.retry_after, default=30.0)
                    post.top_comments = await _scrape_comments(client, post, top_comments)
                except Exception as e:
                    logger.debug("comment_scrape_failed", post_id=post.id, error=str(e))
                    post.top_comments = []

    logger.info("subreddit_complete", subreddit=subreddit, posts_fetched=len(posts))
    return posts


async def fetch_all_subreddits(
    subreddits: list[str],
    listing: str,
    limit: int,
    top_comments: int,
    max_concurrency: int,
    user_agent: str,
) -> list[RedditPost]:
    """Fetch posts from multiple subreddits.

    Args:
        subreddits: List of subreddit names
        listing: Listing type
        limit: Posts per subreddit
        top_comments: Comments per post
        max_concurrency: Maximum concurrent requests
        user_agent: User agent string

    Returns:
        Combined list of all posts
    """
    sem = asyncio.Semaphore(max_concurrency)

    # Use shared HTTP client for all requests
    async with create_http_client(user_agent=user_agent) as client:
        tasks = [fetch_posts(client, sr, listing, limit, top_comments, sem) for sr in subreddits]

        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_posts: list[RedditPost] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("subreddit_failed", subreddit=subreddits[i], error=str(result))
        else:
            all_posts.extend(result)

    logger.info("all_subreddits_complete", total_posts=len(all_posts))
    return all_posts
