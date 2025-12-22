"""Cluster and Digest CLI commands - Core Pain Radar workflow."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import typer
from rich.markdown import Markdown
from rich.panel import Panel

from ..cluster import Clusterer
from ..config import get_settings
from ..digest import (
    generate_comment_reply,
    generate_digest_title,
    generate_weekly_digest,
)
from ..store import AsyncStore
from . import app, console


@app.command()
def cluster(
    days: int = typer.Option(7, help="Days to look back."),
    subreddit: str | None = typer.Option(None, "--subreddit", "-s", help="Filter by subreddit."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't save clusters."),
    db_path: str | None = typer.Option(None, "--db", help="Path to database file."),
):
    """Cluster recent pain signals into themes.

    This is the core Pain Radar workflow - grouping individual pain points
    into actionable clusters with quotes and links.
    """
    settings = get_settings()
    path = db_path or settings.db_path

    async def _cluster():
        store = AsyncStore(path)
        await store.connect()

        console.print(f"[bold blue]Finding pain signals from last {days} days...[/bold blue]")
        items = await store.get_unclustered_pain_points(subreddit=subreddit, days=days)

        if not items:
            console.print("[yellow]No unclustered pain signals found.[/yellow]")
            await store.close()
            return

        console.print(f"Found {len(items)} signals. Clustering with AI...")

        clusterer = Clusterer(model_name=settings.openai_model)
        clusters = await clusterer.cluster_items(items)

        if not clusters:
            console.print("[red]No clusters generated.[/red]")
            await store.close()
            return

        console.print(f"[green]✓ Generated {len(clusters)} pain clusters:[/green]\n")

        for i, c in enumerate(clusters, 1):
            console.print(f"{i}. [bold]{c.title}[/bold] ({len(c.signal_ids)} signals)")
            console.print(f"   {c.summary}")
            console.print(f"   Who: {c.target_audience}")
            console.print(f"   Why: {c.why_it_matters}\n")

        if not dry_run:
            week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
            await store.save_clusters(clusters, week_start)
            console.print(f"[green]Saved clusters for week of {week_start}[/green]")

            # Generate digest preview
            if subreddit:
                digest = generate_weekly_digest(clusters, subreddit, format_type="reddit")
                console.print("\n[bold]Reddit Post Preview:[/bold]")
                console.print(Panel(digest[:600] + "...", title="Digest Preview"))

        await store.close()

    asyncio.run(_cluster())


@app.command()
def digest(
    subreddit: str = typer.Argument(..., help="Subreddit to generate digest for."),
    days: int = typer.Option(7, help="Days to look back for signals."),
    top_n: int = typer.Option(7, "--top", "-n", help="Number of clusters to include."),
    format_type: str = typer.Option("reddit", "--format", "-f", help="Output format: reddit, archive, markdown"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output file path."),
    db_path: str | None = typer.Option(None, "--db", help="Path to database file."),
):
    """Generate a weekly pain clusters digest for a subreddit.

    This creates a Reddit-ready post with:
    - Clustered pain points
    - Verbatim quotes
    - Source links
    - Soft CTA for alerts opt-in

    Formats:
    - reddit: Optimized for posting to Reddit
    - archive: Public archive page with methodology
    - markdown: Standard markdown report
    """
    settings = get_settings()
    path = db_path or settings.db_path

    async def _digest():
        store = AsyncStore(path)
        await store.connect()

        console.print(f"[bold blue]Generating digest for r/{subreddit}...[/bold blue]")

        # Get recent pain signals
        items = await store.get_unclustered_pain_points(subreddit=subreddit, days=days)

        if not items:
            console.print("[yellow]No pain signals found for this subreddit.[/yellow]")
            await store.close()
            return

        console.print(f"Found {len(items)} signals. Clustering...")

        # Cluster them
        clusterer = Clusterer(model_name=settings.openai_model)
        clusters = await clusterer.cluster_items(items)

        if not clusters:
            console.print("[red]No clusters could be generated.[/red]")
            await store.close()
            return

        # Limit to top N
        clusters = clusters[:top_n]

        # Generate digest
        digest_content = generate_weekly_digest(clusters, subreddit, format_type=format_type)
        title = generate_digest_title(clusters, subreddit)

        # Output
        if output:
            output_path = Path(output)
            output_path.write_text(digest_content)
            console.print(f"[green]✓ Digest saved to {output}[/green]")
        else:
            console.print("\n[bold]Suggested Title:[/bold]")
            console.print(f"  {title}\n")
            console.print("[bold]Digest Content:[/bold]\n")
            console.print(Panel(Markdown(digest_content), title=f"r/{subreddit} Weekly Digest"))

        await store.close()

    asyncio.run(_digest())


@app.command()
def reply_template(
    pattern: str = typer.Argument(..., help="Brief description of the pain pattern."),
    count: int = typer.Option(10, "--count", "-c", help="Number of similar threads tracked."),
    approaches: str = typer.Option("", "--approaches", "-a", help="Comma-separated common approaches."),
):
    """Generate a helpful comment reply template.

    Use this to create contextual, helpful replies for Reddit engagement.
    The template follows the daily comment strategy for Pain Radar GTM.
    """
    approaches_list = [a.strip() for a in approaches.split(",") if a.strip()] or [
        "Manual workaround",
        "Third-party tools",
        "Custom scripts",
    ]

    reply = generate_comment_reply(
        pattern_summary=pattern,
        similar_count=count,
        common_approaches=approaches_list,
    )

    console.print("\n[bold]Comment Reply Template:[/bold]\n")
    console.print(Panel(reply, title="Copy this reply"))
    console.print("\n[dim]Customize the links and details before posting.[/dim]")
