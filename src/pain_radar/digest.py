"""Generates Reddit-friendly Markdown digests from Pain Clusters.

This is the core output for Pain Radar's weekly digest strategy.
"""

import datetime

from .models import Cluster


def generate_weekly_digest(clusters: list[Cluster], subreddit: str, format_type: str = "reddit") -> str:
    """Generate a weekly digest Markdown post.

    Args:
        clusters: List of pain clusters to include
        subreddit: Target subreddit name
        format_type: Output format - "reddit", "markdown", or "archive"

    Returns:
        Formatted digest string
    """
    if format_type == "reddit":
        return _generate_reddit_post(clusters, subreddit)
    elif format_type == "archive":
        return _generate_archive_page(clusters, subreddit)
    else:
        return _generate_markdown_report(clusters, subreddit)


def _generate_reddit_post(clusters: list[Cluster], subreddit: str) -> str:
    """Generate a Reddit-optimized post format."""

    num_clusters = len(clusters)

    # Title options (for reference)
    # "Top 7 problems people are repeatedly posting about in r/{subreddit} this week (with links)"
    # "I tracked 200 posts and clustered the recurring pain points. Here are the 7 worth building for."
    # "The most common 'I tried everything' threads this week. Here are the patterns."

    # Body
    md = f"I analyzed posts in r/{subreddit} from the past week to find repeated struggles. "
    md += f"Here are the top {num_clusters} patterns I found.\n\n"

    # Clusters
    for i, cluster in enumerate(clusters, 1):
        md += f"### {i}. {cluster.title}\n\n"
        md += f"**The pattern:** {cluster.summary}\n\n"

        # Verbatim quotes - the key value
        if cluster.quotes:
            md += "**What people are saying:**\n"
            for quote in cluster.quotes[:3]:  # Max 3 quotes
                md += f'> "{quote}"\n\n'

        md += f"**Who this affects:** {cluster.target_audience}\n\n"

        # Source links
        if cluster.urls:
            links = ", ".join([f"[Thread {j+1}]({url})" for j, url in enumerate(cluster.urls[:3])])
            md += f"**Sources:** {links}\n\n"

        md += "---\n\n"

    # Soft CTA - not pushy, opt-in based
    md += "---\n\n"
    md += "I track these pain points weekly. "
    md += "If you want the full list or alerts when people complain about specific topics, "
    md += "comment **'alerts'** and I'll DM you the setup.\n\n"
    md += "*This is a curated digest, not promotion. Sources are linked above.*"

    return md


def _generate_archive_page(clusters: list[Cluster], subreddit: str) -> str:
    """Generate an archive page for public transparency."""

    date_str = datetime.date.today().strftime("%Y-%m-%d")
    week_start = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    week_str = week_start.strftime("%Y-%m-%d")

    md = f"# Pain Clusters Archive: r/{subreddit}\n\n"
    md += f"**Week of:** {week_str}\n"
    md += f"**Generated:** {date_str}\n\n"

    md += "---\n\n"

    for i, cluster in enumerate(clusters, 1):
        md += f"## {i}. {cluster.title}\n\n"
        md += f"**Summary:** {cluster.summary}\n\n"
        md += f"**Target audience:** {cluster.target_audience}\n\n"
        md += f"**Why it matters:** {cluster.why_it_matters}\n\n"

        md += "### Evidence\n\n"
        for quote in cluster.quotes:
            md += f'> "{quote}"\n\n'

        md += "### Sources\n\n"
        for j, url in enumerate(cluster.urls):
            md += f"- [Thread {j+1}]({url})\n"

        md += "\n---\n\n"

    md += "## Methodology\n\n"
    md += "This digest was generated using Pain Radar, which:\n"
    md += "- Fetches public Reddit posts via RSS/JSON\n"
    md += "- Filters out self-promotion and celebration posts\n"
    md += "- Uses AI to extract pain signals and cluster them\n"
    md += "- Cites all sources with links\n\n"
    md += "No private data is scraped. No automated outreach is performed.\n"

    return md


def _generate_markdown_report(clusters: list[Cluster], subreddit: str) -> str:
    """Generate a standard markdown report."""

    date_str = datetime.date.today().strftime("%B %d, %Y")

    md = f"# Weekly Pain Clusters: r/{subreddit}\n\n"
    md += f"*Generated: {date_str}*\n\n"

    md += "## Summary\n\n"
    md += f"Found **{len(clusters)} pain clusters** from recent posts in r/{subreddit}.\n\n"

    for i, cluster in enumerate(clusters, 1):
        md += f"## {i}. {cluster.title}\n\n"
        md += f"{cluster.summary}\n\n"

        md += "### Quotes\n\n"
        for quote in cluster.quotes:
            md += f'> "{quote}"\n\n'

        md += f"**Target:** {cluster.target_audience}\n\n"
        md += f"**Opportunity:** {cluster.why_it_matters}\n\n"

        if cluster.urls:
            md += "### Sources\n\n"
            for url in cluster.urls:
                md += f"- {url}\n"

        md += "\n---\n\n"

    return md


def generate_digest_title(clusters: list[Cluster], subreddit: str) -> str:
    """Generate a title for the Reddit post.

    Returns a title optimized for Reddit engagement without being clickbait.
    """
    num = len(clusters)

    # Title templates that work on Reddit
    templates = [
        f"Top {num} problems people are repeatedly posting about in r/{subreddit} this week (with links)",
        f"I tracked posts in r/{subreddit} and clustered the recurring pain points. Here are the {num} patterns.",
        f"The most common frustrations in r/{subreddit} this week. Here are {num} patterns with quotes + links.",
        f"This week's top {num} pain points in r/{subreddit} (with verbatim quotes)",
    ]

    # Return the first template by default
    return templates[0]


def generate_comment_reply(
    pattern_summary: str,
    similar_count: int,
    common_approaches: list[str],
    thread_links: list[str] | None = None,
) -> str:
    """Generate a helpful comment reply for Reddit engagement.

    This template is for responding to posts where someone describes pain
    that matches a known pattern.

    Args:
        pattern_summary: Brief description of the pattern
        similar_count: Number of similar threads tracked
        common_approaches: What people typically try
        thread_links: Optional links to similar threads

    Returns:
        Comment text
    """
    approaches_str = ", ".join(common_approaches[:3])

    reply = "I track these threads and this comes up a lot. "
    reply += f"I've seen **{similar_count}+ similar posts** recently.\n\n"
    reply += f"**The pattern:** {pattern_summary}\n\n"
    reply += f"**What people typically try:** {approaches_str}\n\n"

    if thread_links:
        reply += "**Similar threads if helpful:**\n"
        for i, link in enumerate(thread_links[:3], 1):
            reply += f"- [Thread {i}]({link})\n"
        reply += "\n"

    reply += "---\n\n"
    reply += "*If you want the full cluster list or alerts when this topic pops up, reply 'alerts' and I'll send it.*"

    return reply
