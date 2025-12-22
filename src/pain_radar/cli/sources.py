"""Source sets CLI commands - manage subreddit bundles."""

from __future__ import annotations

import asyncio

import typer
from rich.table import Table

from ..config import get_settings
from ..presets import PRESETS, get_preset
from ..store import AsyncStore
from . import app, console


@app.command()
def sources(
    all_sets: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Include inactive source sets.",
    ),
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """List source sets and available presets."""
    settings = get_settings()
    path = db_path or settings.db_path

    async def _list():
        store = AsyncStore(path)
        await store.connect()
        source_sets = await store.get_source_sets(active_only=not all_sets)
        await store.close()
        return source_sets

    source_sets = asyncio.run(_list())

    # Show active source sets
    if source_sets:
        console.print("\n[bold]Active Source Sets[/bold]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("ID", width=4)
        table.add_column("Name", width=25)
        table.add_column("Subreddits", width=40)
        table.add_column("Preset", width=12)

        for ss in source_sets:
            subs = ", ".join(ss["subreddits"][:4])
            if len(ss["subreddits"]) > 4:
                subs += f" (+{len(ss['subreddits']) - 4} more)"
            table.add_row(
                str(ss["id"]),
                ss["name"],
                subs,
                ss.get("preset_key") or "custom",
            )
        console.print(table)
    else:
        console.print("\n[yellow]No active source sets. Add one with:[/yellow]")
        console.print("  pain-radar sources-add indie_saas")

    # Show available presets
    console.print("\n[bold]Available Presets[/bold]")
    preset_table = Table(show_header=True, header_style="bold")
    preset_table.add_column("Key", width=15)
    preset_table.add_column("Name", width=25)
    preset_table.add_column("Subreddits", width=45)

    for key, preset in PRESETS.items():
        # Check if already added
        is_added = any(ss.get("preset_key") == key for ss in source_sets)
        name = preset["name"]
        if is_added:
            name = f"[dim]{name} ✓[/dim]"
        subs = ", ".join(preset["subreddits"][:4])
        if len(preset["subreddits"]) > 4:
            subs += f" (+{len(preset['subreddits']) - 4})"
        preset_table.add_row(key, name, subs)

    console.print(preset_table)
    console.print("\nAdd a preset: [cyan]pain-radar sources-add <preset_key>[/cyan]")


@app.command("sources-add")
def sources_add(
    preset_key: str = typer.Argument(
        ...,
        help="Preset key (e.g., indie_saas, shopify, marketing) or 'custom' for manual.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Custom name (overrides preset name).",
    ),
    subreddits: str | None = typer.Option(
        None,
        "--subreddits",
        "-s",
        help="Comma-separated subreddits (required if preset_key='custom').",
    ),
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Add a source set from a preset or create a custom one."""
    settings = get_settings()
    path = db_path or settings.db_path

    # Handle preset vs custom
    if preset_key == "custom":
        if not subreddits:
            console.print("[red]Error: --subreddits required for custom source set[/red]")
            raise typer.Exit(1)
        sub_list = [s.strip() for s in subreddits.split(",") if s.strip()]
        set_name = name or "Custom Source Set"
        description = None
        pkey = None
    else:
        preset = get_preset(preset_key)
        if not preset:
            console.print(f"[red]Unknown preset: {preset_key}[/red]")
            console.print(f"Available: {', '.join(PRESETS.keys())}")
            raise typer.Exit(1)
        sub_list = preset["subreddits"]
        set_name = name or preset["name"]
        description = preset["description"]
        pkey = preset_key

    async def _add():
        store = AsyncStore(path)
        await store.connect()

        # Check if preset already exists
        if pkey:
            existing = await store.get_source_set_by_preset(pkey)
            if existing:
                console.print(f"[yellow]Preset '{pkey}' already added as '{existing['name']}'[/yellow]")
                await store.close()
                return None

        source_set_id = await store.create_source_set(
            name=set_name,
            subreddits=sub_list,
            description=description,
            preset_key=pkey,
        )
        await store.close()
        return source_set_id

    source_set_id = asyncio.run(_add())

    if source_set_id:
        console.print(f"[green]✓ Added source set '{set_name}'[/green]")
        console.print(f"  ID: {source_set_id}")
        console.print(f"  Subreddits: {', '.join(sub_list)}")
        console.print("\nFetch from this source set:")
        console.print(f"  [cyan]pain-radar fetch --source-set {source_set_id}[/cyan]")


@app.command("sources-edit")
def sources_edit(
    source_set_id: int = typer.Argument(..., help="Source set ID to edit."),
    add: str | None = typer.Option(
        None,
        "--add",
        help="Comma-separated subreddits to add.",
    ),
    remove: str | None = typer.Option(
        None,
        "--remove",
        help="Comma-separated subreddits to remove.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="New name.",
    ),
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Edit a source set - add or remove subreddits."""
    settings = get_settings()
    path = db_path or settings.db_path

    async def _edit():
        store = AsyncStore(path)
        await store.connect()

        ss = await store.get_source_set(source_set_id)
        if not ss:
            console.print(f"[red]Source set {source_set_id} not found[/red]")
            await store.close()
            return False

        current_subs = set(ss["subreddits"])

        if add:
            for sub in add.split(","):
                sub = sub.strip()
                if sub:
                    current_subs.add(sub)

        if remove:
            for sub in remove.split(","):
                sub = sub.strip()
                current_subs.discard(sub)

        await store.update_source_set(
            source_set_id,
            subreddits=sorted(list(current_subs)),
            name=name,
        )
        await store.close()
        return sorted(list(current_subs))

    result = asyncio.run(_edit())

    if result:
        console.print(f"[green]✓ Updated source set {source_set_id}[/green]")
        console.print(f"  Subreddits: {', '.join(result)}")


@app.command("sources-remove")
def sources_remove(
    source_set_id: int = typer.Argument(..., help="Source set ID to remove."),
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Remove (deactivate) a source set."""
    settings = get_settings()
    path = db_path or settings.db_path

    async def _remove():
        store = AsyncStore(path)
        await store.connect()
        ss = await store.get_source_set(source_set_id)
        if not ss:
            console.print(f"[red]Source set {source_set_id} not found[/red]")
            await store.close()
            return None
        await store.delete_source_set(source_set_id)
        await store.close()
        return ss["name"]

    name = asyncio.run(_remove())

    if name:
        console.print(f"[green]✓ Removed source set '{name}'[/green]")
