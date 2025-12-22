"""Report commands - report generation and run history."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.table import Table

from ..config import get_settings
from ..report import generate_json_report, generate_report
from ..store import AsyncStore
from . import app, console


@app.command()
def report(
    run_id: int | None = typer.Option(
        None,
        "--run",
        "-r",
        help="Run ID to generate report for (uses latest if not specified).",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (auto-generated if not specified).",
    ),
    format: str = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Output format: markdown or json.",
    ),
    include_disqualified: bool = typer.Option(
        False,
        "--include-disqualified",
        help="Include disqualified ideas in report.",
    ),
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Generate a report from pipeline results.

    Creates a detailed Markdown or JSON report of discovered ideas,
    including scores, evidence, and validation steps.
    """
    settings = get_settings()
    path = db_path or settings.db_path

    async def _report():
        store = AsyncStore(path)
        await store.connect()

        # output_dir can be a path like "reports/run1.md" - use parent dir
        output_dir = str(Path(output).parent) if output else "reports"

        if format.lower() == "json":
            report_path = await generate_json_report(
                store,
                run_id=run_id,
                output_dir=output_dir,
                include_disqualified=include_disqualified,
            )
        else:
            report_path = await generate_report(
                store,
                run_id=run_id,
                output_dir=output_dir,
                include_disqualified=include_disqualified,
            )

        await store.close()
        return report_path

    report_path = asyncio.run(_report())
    console.print(f"[green]✓ Report generated:[/green] {report_path}")
    console.print(f"\nOpen with: cat {report_path}")


@app.command()
def runs(
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Number of runs to show.",
    ),
    db_path: str | None = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Show recent pipeline runs."""
    settings = get_settings()
    path = db_path or settings.db_path

    async def _runs():
        store = AsyncStore(path)
        await store.connect()
        runs_list = await store.get_runs(limit=limit)
        await store.close()
        return runs_list

    runs_list = asyncio.run(_runs())

    if not runs_list:
        console.print("[yellow]No runs found[/yellow]")
        return

    table = Table(title="Pipeline Runs", show_header=True, header_style="bold")
    table.add_column("ID", width=4)
    table.add_column("Started", width=17)
    table.add_column("Status", width=9)
    table.add_column("Posts", width=5)
    table.add_column("Ideas", width=5)
    table.add_column("Qualified", width=7)
    table.add_column("Report", width=20)

    for run in runs_list:
        started = run.get("started_at", "")[:16] if run.get("started_at") else "-"
        table.add_row(
            str(run.get("id", "-")),
            started,
            run.get("status", "-"),
            str(run.get("posts_analyzed", "-")),
            str(run.get("ideas_saved", "-")),
            str(run.get("qualified_ideas", "-")),
            run.get("report_path", "-") or "-",
        )

    console.print(table)
    console.print("\nGenerate a report with: pain-radar report --run <ID>")
