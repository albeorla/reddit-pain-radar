"""Signals commands - top, show, export."""

from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path

import typer
from rich.table import Table

from ..config import get_settings
from ..store import AsyncStore
from . import app, console


@app.command()
def top(
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Number of signals to show.",
    ),
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Show top-scored pain signals."""
    settings = get_settings()
    path = db_path or settings.db_path

    async def _top():
        store = AsyncStore(path)
        await store.connect()
        signals = await store.get_top_signals(limit=limit)
        await store.close()
        return signals

    signals = asyncio.run(_top())

    if not signals:
        console.print("[yellow]No signals found[/yellow]")
        return

    table = Table(title="Top Pain Signals", show_header=True, header_style="bold")
    table.add_column("", width=2)
    table.add_column("Score", width=5)
    table.add_column("", width=2)
    table.add_column("$", width=3)
    table.add_column("", width=2)
    table.add_column("C", width=3)
    table.add_column("", width=2)
    table.add_column("Signal", width=45)
    table.add_column("Subreddit", width=10)

    for sig in signals:
        summary = sig.get("signal_summary", "")
        table.add_row(
            "",
            str(sig.get("total_score", "-")),
            "",
            str(sig.get("profitability", "-")),
            "",
            str(sig.get("competition", "-")),
            "",
            (summary[:42] + "...") if len(summary) > 45 else summary,
            sig.get("subreddit", "")[:10],
        )

    console.print(table)
    console.print("\nP=Practicality, $=Profitability, D=Distribution, C=Competition, M=Moat")


@app.command()
def show(
    signal_id: int = typer.Argument(..., help="Signal ID to show details for."),
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Show detailed information about a specific signal."""
    settings = get_settings()
    path = db_path or settings.db_path

    async def _show():
        store = AsyncStore(path)
        await store.connect()
        signal = await store.get_signal_detail(signal_id)
        await store.close()
        return signal

    signal = asyncio.run(_show())

    if not signal:
        console.print(f"[red]Signal {signal_id} not found[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Signal #{signal_id}[/bold]")
    console.print("─" * 60)

    console.print(f"\n[bold]Summary:[/bold] {signal.get('signal_summary', 'N/A')}")
    console.print(f"[bold]Subreddit:[/bold] r/{signal.get('subreddit', 'N/A')}")
    console.print(f"[bold]Post:[/bold] {signal.get('post_title', 'N/A')}")
    console.print(f"[bold]Link:[/bold] {signal.get('permalink', 'N/A')}")

    console.print(f"\n[bold]Score:[/bold] {signal.get('total_score', 0)}/50")
    if signal.get("disqualified"):
        console.print("[red]⚠ DISQUALIFIED[/red]")

    console.print("\n[bold]Dimensions:[/bold]")
    console.print(f"  Practicality:  {signal.get('practicality', '-')}/10")
    console.print(f"  Profitability: {signal.get('profitability', '-')}/10")
    console.print(f"  Distribution:  {signal.get('distribution', '-')}/10")
    console.print(f"  Competition:   {signal.get('competition', '-')}/10")
    console.print(f"  Moat:          {signal.get('moat', '-')}/10")

    console.print(f"\n[bold]Target User:[/bold] {signal.get('target_user', 'N/A')}")
    console.print(f"[bold]Pain Point:[/bold] {signal.get('pain_point', 'N/A')}")
    console.print(f"[bold]Solution:[/bold] {signal.get('proposed_solution', 'N/A')}")

    # Evidence
    evidence = signal.get("evidence_signals")
    if evidence:
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except json.JSONDecodeError:
                evidence = []
        if evidence:
            console.print("\n[bold]Evidence:[/bold]")
            for e in evidence:
                console.print(f"  • {e}")

    # Validation steps
    steps = signal.get("next_validation_steps")
    if steps:
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except json.JSONDecodeError:
                steps = []
        if steps:
            console.print("\n[bold]Validation Steps:[/bold]")
            for step in steps:
                console.print(f"  • {step}")

    # Reasoning
    why = signal.get("why")
    if why:
        if isinstance(why, str):
            try:
                why = json.loads(why)
            except json.JSONDecodeError:
                why = []
        if why:
            console.print("\n[bold]Reasoning:[/bold]")
            for w in why:
                console.print(f"  • {w}")


@app.command()
def export(
    output: str = typer.Option(
        "signals.json",
        "--output",
        "-o",
        help="Output file path (.json or .csv).",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-l",
        help="Number of signals to export.",
    ),
    include_disqualified: bool = typer.Option(
        False,
        "--include-disqualified",
        help="Include disqualified signals.",
    ),
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Export top signals to JSON or CSV."""
    settings = get_settings()
    path = db_path or settings.db_path

    async def _export():
        store = AsyncStore(path)
        await store.connect()
        signals = await store.get_top_signals(limit=limit, include_disqualified=include_disqualified)
        await store.close()
        return signals

    signals = asyncio.run(_export())

    if not signals:
        console.print("[yellow]No signals to export[/yellow]")
        return

    output_path = Path(output)

    if output.endswith(".csv"):
        with open(output_path, "w", newline="") as f:
            if signals:
                writer = csv.DictWriter(f, fieldnames=signals[0].keys())
                writer.writeheader()
                writer.writerows(signals)
    else:
        with open(output_path, "w") as f:
            json.dump(signals, f, indent=2, default=str)

    console.print(f"[green]✓ Exported {len(signals)} signals to {output}[/green]")
