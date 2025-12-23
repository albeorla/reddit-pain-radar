import pytest
from pain_radar.reddit_async import _extract_post_id, _clean_html, _parse_rss_entry, RedditPost

def test_extract_post_id():
    """Test extracting post ID from various Reddit URLs."""
    url = "https://www.reddit.com/r/SaaS/comments/1ptgval/take_these_with_a_pinch_of_salt/"
    assert _extract_post_id(url) == "1ptgval"
    assert _extract_post_id("https://google.com") == ""

def test_clean_html():
    """Test cleaning HTML content."""
    html_text = "<div>Hello &amp; welcome <p>to the <b>world</b></p></div>"
    cleaned = _clean_html(html_text)
    # The current implementation uses separator=" " in BeautifulSoup which might add extra spaces
    assert "Hello & welcome" in cleaned
    assert "to the" in cleaned
    assert "world" in cleaned

def test_parse_rss_entry():
    """Test parsing an RSS entry into a RedditPost."""
    entry = {
        "link": "https://www.reddit.com/r/test/comments/abc123/title/",
        "title": "Test Title",
        "summary": "<div>Summary content</div>",
        "published_parsed": None
    }
    post = _parse_rss_entry(entry, "test")
    assert isinstance(post, RedditPost)
    assert post.id == "abc123"
    assert post.title == "Test Title"
    assert post.body == "Summary content"
    assert post.subreddit == "test"
