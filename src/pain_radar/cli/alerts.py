"""Alerting CLI commands for Pain Radar."""

import asyncio

import typer
from rich.table import Table

from ..config import get_settings
from ..store import AsyncStore
from . import app, console


@app.command("alerts")
def alerts_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include inactive watchlists."),
    db_path: str | None = typer.Option(None, "--db", help="Path to database file."),
):
    """List all keyword watchlists.

    Shows active watchlists that track keywords for alert notifications.
    """
    settings = get_settings()
    path = db_path or settings.db_path

    async def _list():
        store = AsyncStore(path)
        await store.connect()

        watchlists = await store.get_watchlists(active_only=not all)

        if not watchlists:
            console.print("[yellow]No watchlists found. Create one with:[/yellow]")
            console.print("  pain-radar alerts-add 'keyword1, keyword2' --name 'My Watchlist'")
            await store.close()
            return

        table = Table(title="Keyword Watchlists")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Keywords")
        table.add_column("Subreddits")
        table.add_column("Matches", justify="right")
        table.add_column("Status")

        for wl in watchlists:
            keywords = ", ".join(wl["keywords"][:3])
            if len(wl["keywords"]) > 3:
                keywords += f" (+{len(wl['keywords']) - 3})"

            subreddits = ", ".join(wl["subreddits"][:2]) if wl["subreddits"] else "All"
            if wl["subreddits"] and len(wl["subreddits"]) > 2:
                subreddits += f" (+{len(wl['subreddits']) - 2})"

            status = "[green]Active[/green]" if wl["is_active"] else "[dim]Inactive[/dim]"

            table.add_row(
                str(wl["id"]),
                wl["name"],
                keywords,
                subreddits,
                str(wl["total_matches"]),
                status,
            )

        console.print(table)
        await store.close()

    asyncio.run(_list())


@app.command("alerts-add")
def alerts_add(
    keywords: str = typer.Argument(..., help="Comma-separated keywords to track."),
    name: str = typer.Option(None, "--name", "-n", help="Name for the watchlist."),
    subreddits: str | None = typer.Option(None, "--subreddits", "-s", help="Comma-separated subreddits to filter."),
    email: str | None = typer.Option(None, "--email", "-e", help="Email for notifications."),
    webhook: str | None = typer.Option(None, "--webhook", "-w", help="Webhook URL for notifications."),
    db_path: str | None = typer.Option(None, "--db", help="Path to database file."),
):
    """Add a new keyword watchlist.

    Create a watchlist that tracks specific keywords in pain signals.
    When a match is found, you can be notified via email or webhook.

    Examples:

        pain-radar alerts-add "stripe, payment" --name "Payment Pain"

        pain-radar alerts-add "onboarding, churn" -s "SaaS,IndieHackers" -e "me@email.com"
    """
    settings = get_settings()
    path = db_path or settings.db_path

    # Parse keywords
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    if not keyword_list:
        console.print("[red]Error: At least one keyword is required.[/red]")
        raise typer.Exit(1)

    # Parse subreddits
    subreddit_list = None
    if subreddits:
        subreddit_list = [s.strip() for s in subreddits.split(",") if s.strip()]

    # Generate name if not provided
    if not name:
        name = f"Watch: {', '.join(keyword_list[:2])}"
        if len(keyword_list) > 2:
            name += f" (+{len(keyword_list) - 2})"

    async def _add():
        store = AsyncStore(path)
        await store.connect()

        watchlist_id = await store.create_watchlist(
            name=name,
            keywords=keyword_list,
            subreddits=subreddit_list,
            notification_email=email,
            notification_webhook=webhook,
        )

        console.print(f"[green]✓ Created watchlist #{watchlist_id}:[/green] {name}")
        console.print(f"  Keywords: {', '.join(keyword_list)}")
        if subreddit_list:
            console.print(f"  Subreddits: {', '.join(subreddit_list)}")
        if email:
            console.print(f"  Email: {email}")
        if webhook:
            console.print(f"  Webhook: {webhook}")

        console.print("\n[dim]Run 'pain-radar alerts-check' to scan for matches.[/dim]")

        await store.close()

    asyncio.run(_add())


@app.command("alerts-remove")
def alerts_remove(
    watchlist_id: int = typer.Argument(..., help="Watchlist ID to remove."),
    db_path: str | None = typer.Option(None, "--db", help="Path to database file."),
):
    """Remove (deactivate) a watchlist.

    This doesn't delete the watchlist, just marks it inactive.
    """
    settings = get_settings()
    path = db_path or settings.db_path

    async def _remove():
        store = AsyncStore(path)
        await store.connect()

        wl = await store.get_watchlist(watchlist_id)
        if not wl:
            console.print(f"[red]Error: Watchlist #{watchlist_id} not found.[/red]")
            await store.close()
            raise typer.Exit(1)

        await store.delete_watchlist(watchlist_id)
        console.print(f"[green]✓ Removed watchlist #{watchlist_id}:[/green] {wl['name']}")

        await store.close()

    asyncio.run(_remove())


@app.command("alerts-check")
def alerts_check(
    hours: int = typer.Option(24, "--hours", "-h", help="Check signals from the last N hours."),
    notify: bool = typer.Option(False, "--notify", help="Send notifications for matches."),
    db_path: str | None = typer.Option(None, "--db", help="Path to database file."),
):
    """Check watchlists for matching signals.

    Scans recent pain signals against all active watchlists
    and reports any keyword matches.
    """
    settings = get_settings()
    path = db_path or settings.db_path

    async def _check():
        store = AsyncStore(path)
        await store.connect()

        console.print(f"[bold blue]Checking watchlists against last {hours}h of signals...[/bold blue]")

        matches = await store.check_watchlists(since_hours=hours)

        if not matches:
            console.print("[yellow]No matches found.[/yellow]")
            await store.close()
            return

        console.print(f"[green]✓ Found {len(matches)} matches![/green]\n")

        # Group by watchlist
        by_watchlist = {}
        for m in matches:
            wl_name = m["watchlist_name"]
            if wl_name not in by_watchlist:
                by_watchlist[wl_name] = []
            by_watchlist[wl_name].append(m)

        for wl_name, wl_matches in by_watchlist.items():
            console.print(f"[bold]{wl_name}[/bold] ({len(wl_matches)} matches)")

            for m in wl_matches[:5]:  # Show max 5 per watchlist
                console.print(f"  • [cyan]{m['keyword_matched']}[/cyan] in r/{m['subreddit']}")
                console.print(f"    {m['signal_summary'][:60]}...")
                console.print(f"    [dim]{m['url']}[/dim]")

            if len(wl_matches) > 5:
                console.print(f"  [dim]... and {len(wl_matches) - 5} more[/dim]")

            console.print()

        if notify:
            # Get unnotified matches
            unnotified = await store.get_unnotified_matches()
            if unnotified:
                console.print("[yellow]Notification sending not yet implemented.[/yellow]")
                console.print(f"[dim]Would notify {len(unnotified)} matches.[/dim]")
                # TODO: Implement email/webhook sending

        await store.close()

    asyncio.run(_check())


@app.command("alerts-matches")
def alerts_matches(
    watchlist_id: int | None = typer.Argument(None, help="Filter by watchlist ID."),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum matches to show."),
    db_path: str | None = typer.Option(None, "--db", help="Path to database file."),
):
    """Show recent alert matches.

    Display signals that matched watchlist keywords.
    """
    settings = get_settings()
    path = db_path or settings.db_path

    async def _matches():
        store = AsyncStore(path)
        await store.connect()

        matches = await store.get_unnotified_matches(watchlist_id=watchlist_id)

        if not matches:
            console.print("[yellow]No recent matches found.[/yellow]")
            await store.close()
            return

        table = Table(title=f"Alert Matches (showing {min(len(matches), limit)} of {len(matches)})")
        table.add_column("Watchlist")
        table.add_column("Keyword", style="cyan")
        table.add_column("Subreddit")
        table.add_column("Pain Point")
        table.add_column("URL")

        for m in matches[:limit]:
            table.add_row(
                m["watchlist_name"],
                m["keyword_matched"],
                f"r/{m['subreddit']}",
                m["pain_point"][:40] + "..." if len(m.get("pain_point", "") or "") > 40 else m.get("pain_point", ""),
                m["url"][:30] + "..." if m.get("url") else "",
            )

        console.print(table)
        await store.close()

    asyncio.run(_matches())
