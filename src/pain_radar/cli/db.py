"""Database commands - init-db, stats."""

from __future__ import annotations

import asyncio

import typer
from rich.table import Table

from ..config import get_settings
from ..store import AsyncStore
from . import app, console


@app.command("init-db")
def init_db(
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Initialize the database schema.

    Creates the SQLite database and tables if they don't exist.
    """
    settings = get_settings()
    path = db_path or settings.db_path

    async def _init():
        store = AsyncStore(path)
        await store.connect()
        await store.init_db()
        await store.close()

    asyncio.run(_init())
    console.print(f"[green]✓ Database initialized:[/green] {path}")


@app.command()
def stats(
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Show database statistics."""
    settings = get_settings()
    path = db_path or settings.db_path

    async def _stats():
        store = AsyncStore(path)
        await store.connect()
        stats = await store.get_stats()
        await store.close()
        return stats

    stats = asyncio.run(_stats())

    table = Table(title="Database Statistics", show_header=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Posts", str(stats.get("total_posts", 0)))
    table.add_row("Processed Posts", str(stats.get("processed_posts", 0)))
    table.add_row("Total Ideas", str(stats.get("total_ideas", 0)))
    table.add_row("Qualified Ideas", str(stats.get("qualified_ideas", 0)))
    table.add_row("Average Score", f"{stats.get('avg_score', 0):.1f}")

    console.print(table)
