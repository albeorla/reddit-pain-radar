"""Report generation for pipeline runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .store import AsyncStore


async def generate_report(
    store: AsyncStore,
    run_id: Optional[int] = None,
    output_dir: str = "reports",
    include_disqualified: bool = False,
) -> str:
    """Generate a markdown report for a pipeline run.

    Args:
        store: Async store connection
        run_id: Specific run ID, or None for latest run
        output_dir: Directory to save reports
        include_disqualified: Whether to include disqualified ideas

    Returns:
        Path to generated report
    """
    run = None
    
    # Try to get run info
    if run_id is not None:
        run = await store.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
    else:
        runs = await store.get_runs(limit=1)
        if runs:
            run = runs[0]
            run_id = run["id"]

    # Get ideas
    ideas = []
    if run_id:
        ideas = await store.get_ideas_for_run(run_id)
    
    # If no ideas for this run, get top ideas overall
    if not ideas:
        ideas = await store.get_top_ideas(limit=50, include_disqualified=True)
    
    if not ideas:
        raise ValueError("No ideas found in database. Run 'idea-miner run' first.")

    # Filter out disqualified if needed
    if not include_disqualified:
        qualified_ideas = [i for i in ideas if not i.get("disqualified")]
    else:
        qualified_ideas = ideas

    # Get stats
    stats = await store.get_stats()

    # Create a synthetic run dict if none exists
    if not run:
        run = {
            "id": "all",
            "started_at": datetime.now().isoformat(),
            "subreddits": "[]",
            "posts_fetched": stats.get("total_posts", 0),
            "posts_analyzed": stats.get("processed_posts", 0),
        }

    # Generate report content
    report = _generate_markdown_report(run, ideas, stats)

    # Save report
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_label = run_id if run_id else "all"
    filename = f"idea_report_{run_label}_{timestamp}.md"
    report_path = output_path / filename

    report_path.write_text(report)

    return str(report_path)


def _generate_markdown_report(run: dict, ideas: List[dict], stats: dict) -> str:
    """Generate markdown report content.

    Args:
        run: Run dictionary
        ideas: List of idea dictionaries
        stats: Database statistics

    Returns:
        Markdown report content
    """
    subreddits = json.loads(run.get("subreddits", "[]")) if run.get("subreddits") else []
    started = run.get("started_at", "Unknown")[:19].replace("T", " ")
    
    lines = [
        f"# Idea Miner Report - Run #{run.get('id', 'N/A')}",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Run Started:** {started}",
        f"**Subreddits:** {', '.join(subreddits) if subreddits else 'N/A'}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Posts Fetched | {run.get('posts_fetched', stats.get('total_posts', 0))} |",
        f"| Posts Analyzed | {run.get('posts_analyzed', stats.get('processed_posts', 0))} |",
        f"| Ideas Extracted | {len(ideas)} |",
        f"| Qualified Ideas | {len([i for i in ideas if not i.get('disqualified')])} |",
        f"| Average Score | {stats.get('avg_score', 0)} |",
        "",
    ]

    # Top ideas section
    qualified = [i for i in ideas if not i.get("disqualified")]
    if qualified:
        lines.extend([
            "## 🏆 Top Ideas",
            "",
        ])

        for rank, idea in enumerate(qualified[:10], 1):
            score = idea.get("total_score", 0)
            summary = idea.get("idea_summary", "No summary")
            subreddit = idea.get("subreddit", "unknown")
            permalink = idea.get("permalink", "")
            
            lines.extend([
                f"### #{rank}: {summary[:80]}{'...' if len(summary) > 80 else ''}",
                "",
                f"**Score:** {score}/50 | **Subreddit:** r/{subreddit}",
                "",
                "| Dimension | Score |",
                "|-----------|-------|",
                f"| Practicality | {idea.get('practicality', '-')}/10 |",
                f"| Profitability | {idea.get('profitability', '-')}/10 |",
                f"| Distribution | {idea.get('distribution', '-')}/10 |",
                f"| Competition | {idea.get('competition', '-')}/10 |",
                f"| Moat | {idea.get('moat', '-')}/10 |",
                "",
            ])
            
            # Target user and pain point
            if idea.get("target_user"):
                lines.append(f"**Target User:** {idea.get('target_user')}")
            if idea.get("pain_point"):
                lines.append(f"**Pain Point:** {idea.get('pain_point')}")
            if idea.get("proposed_solution"):
                lines.append(f"**Solution:** {idea.get('proposed_solution')}")
            lines.append("")
            
            # Evidence signals
            signals = idea.get("evidence_signals")
            if signals:
                if isinstance(signals, str):
                    signals = json.loads(signals)
                if signals:
                    lines.append("**Evidence:**")
                    for sig in signals[:3]:
                        lines.append(f"- {sig}")
                    lines.append("")
            
            # Next steps
            next_steps = idea.get("next_validation_steps")
            if next_steps:
                if isinstance(next_steps, str):
                    next_steps = json.loads(next_steps)
                if next_steps:
                    lines.append("**Validation Steps:**")
                    for step in next_steps[:3]:
                        lines.append(f"- {step}")
                    lines.append("")
            
            # Why scores
            why = idea.get("why")
            if why:
                if isinstance(why, str):
                    why = json.loads(why)
                if why:
                    lines.append("**Reasoning:**")
                    for reason in why[:3]:
                        lines.append(f"- {reason}")
                    lines.append("")
            
            if permalink:
                lines.append(f"[📎 View Original Post]({permalink})")
            lines.extend(["", "---", ""])

    # Disqualified ideas section
    disqualified = [i for i in ideas if i.get("disqualified")]
    if disqualified:
        lines.extend([
            "## ⚠️ Disqualified Ideas",
            "",
            "These ideas were flagged as problematic:",
            "",
        ])
        for idea in disqualified[:5]:
            summary = idea.get("idea_summary", "No summary")[:60]
            reasons = idea.get("disqualify_reasons")
            if isinstance(reasons, str):
                reasons = json.loads(reasons)
            reason_text = ", ".join(reasons[:2]) if reasons else "No reason given"
            lines.append(f"- **{summary}...** - {reason_text}")
        lines.append("")

    # Footer
    lines.extend([
        "---",
        "",
        "*Report generated by Idea Miner*",
    ])

    return "\n".join(lines)


async def generate_json_report(
    store: AsyncStore,
    run_id: Optional[int] = None,
    output_dir: str = "reports",
) -> str:
    """Generate a JSON report for a pipeline run.

    Args:
        store: Async store connection
        run_id: Specific run ID, or None for latest run
        output_dir: Directory to save reports

    Returns:
        Path to generated report
    """
    # Get run info
    if run_id is None:
        runs = await store.get_runs(limit=1)
        if not runs:
            raise ValueError("No runs found in database")
        run = runs[0]
        run_id = run["id"]
    else:
        run = await store.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

    # Get ideas
    ideas = await store.get_ideas_for_run(run_id)
    if not ideas:
        ideas = await store.get_top_ideas(limit=50, include_disqualified=True)

    # Get stats
    stats = await store.get_stats()

    # Build report object
    report = {
        "run": run,
        "stats": stats,
        "ideas": ideas,
        "generated_at": datetime.now().isoformat(),
    }

    # Parse JSON fields in ideas
    for idea in report["ideas"]:
        for field in ["evidence_signals", "risk_flags", "disqualify_reasons", "why", "next_validation_steps", "top_comments"]:
            if idea.get(field) and isinstance(idea[field], str):
                try:
                    idea[field] = json.loads(idea[field])
                except json.JSONDecodeError:
                    pass

    # Save report
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"idea_report_{run_id}_{timestamp}.json"
    report_path = output_path / filename

    report_path.write_text(json.dumps(report, indent=2, default=str))

    return str(report_path)
