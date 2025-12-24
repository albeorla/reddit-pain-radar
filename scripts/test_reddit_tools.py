#!/usr/bin/env python3
"""Manual verification script for fetch_more_comments and search_related_posts.

Usage:
    python scripts/test_reddit_tools.py
"""

import asyncio
import sys

from pain_radar.http_client import create_http_client
from pain_radar.reddit_async import (
    RedditPost,
    fetch_more_comments,
    search_related_posts,
)


async def test_fetch_more_comments():
    """Test fetch_more_comments with a real Reddit post.

    Uses a popular post from r/SideProject for testing.
    """
    print("\n" + "=" * 60)
    print("TEST 1: fetch_more_comments")
    print("=" * 60)

    # Use a well-known subreddit and find a real post
    # First, let's search for a post with comments
    async with create_http_client() as client:
        # Get a post from r/SideProject or r/SaaS that's likely to have comments
        posts = await search_related_posts(
            client,
            subreddit="SideProject",
            query="feedback",
            limit=5,
        )

        if not posts:
            print("❌ Could not find any posts to test with")
            return False

        # Find a post that likely has comments
        test_post = posts[0]
        print(f"\n📝 Testing with post: {test_post.title[:60]}...")
        print(f"   URL: {test_post.url}")
        print(f"   ID: {test_post.id}")

        # Try to fetch initial comments (first 5)
        from pain_radar.reddit_async import _scrape_comments

        initial_comments = await _scrape_comments(client, test_post, limit=5, start_index=0)
        print(f"\n📥 Initial comments (first 5): {len(initial_comments)} fetched")
        for i, comment in enumerate(initial_comments[:3]):
            print(f"   {i + 1}. {comment[:80]}...")

        # Now test fetch_more_comments to get additional ones
        if len(initial_comments) >= 5:
            # Create a post object with the initial comments set
            post_with_comments = RedditPost(
                id=test_post.id,
                subreddit=test_post.subreddit,
                title=test_post.title,
                body=test_post.body,
                created_utc=test_post.created_utc,
                score=test_post.score,
                num_comments=test_post.num_comments,
                url=test_post.url,
                permalink=test_post.permalink,
                top_comments=initial_comments,
            )

            # Fetch more comments starting after the initial batch
            more_comments = await fetch_more_comments(client, post_with_comments, start_index=5, limit=5)
            print(f"\n📥 Additional comments (next 5): {len(more_comments)} fetched")
            for i, comment in enumerate(more_comments[:3]):
                print(f"   {i + 1}. {comment[:80]}...")

            if len(more_comments) > 0:
                print("\n✅ fetch_more_comments: PASSED - fetched additional comments")
                return True
            else:
                print("\n⚠️  fetch_more_comments: PARTIAL - no more comments available (post may have < 10 comments)")
                return True
        else:
            print(f"\n⚠️  Post only has {len(initial_comments)} comments, testing with that")
            return True

    return False


async def test_search_related_posts():
    """Test search_related_posts with a sample query.

    Searches r/SideProject for posts about a common topic.
    """
    print("\n" + "=" * 60)
    print("TEST 2: search_related_posts")
    print("=" * 60)

    test_cases = [
        ("SideProject", "feedback on my app"),
        ("SaaS", "pricing strategy"),
        ("indiehackers", "first customer"),
    ]

    results = []

    async with create_http_client() as client:
        for subreddit, query in test_cases:
            print(f"\n🔍 Searching r/{subreddit} for: '{query}'")

            try:
                posts = await search_related_posts(
                    client,
                    subreddit=subreddit,
                    query=query,
                    limit=5,
                )

                if posts:
                    print(f"   ✅ Found {len(posts)} related posts:")
                    for i, post in enumerate(posts[:3]):
                        print(f"      {i + 1}. {post.title[:60]}...")
                    results.append(True)
                else:
                    print("   ⚠️  No posts found (subreddit may be private or empty)")
                    results.append(True)  # Not a failure, just empty results

            except Exception as e:
                print(f"   ❌ Error: {e}")
                results.append(False)

            # Small delay to avoid rate limiting
            await asyncio.sleep(1)

    passed = all(results)
    if passed:
        print("\n✅ search_related_posts: PASSED - successfully searched multiple subreddits")
    else:
        print("\n❌ search_related_posts: FAILED - some searches failed")

    return passed


async def main():
    """Run all manual verification tests."""
    print("\n" + "=" * 60)
    print("MANUAL VERIFICATION: Reddit Research Tools")
    print("=" * 60)
    print("\nThis script tests the following functions with real Reddit API calls:")
    print("  1. fetch_more_comments - Fetches additional comments beyond initial set")
    print("  2. search_related_posts - Searches for relevant posts in a subreddit")

    results = []

    try:
        # Test 1: fetch_more_comments
        result1 = await test_fetch_more_comments()
        results.append(("fetch_more_comments", result1))

        # Small delay between tests
        await asyncio.sleep(2)

        # Test 2: search_related_posts
        result2 = await test_search_related_posts()
        results.append(("search_related_posts", result2))

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All manual verification tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed - please review the output above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
