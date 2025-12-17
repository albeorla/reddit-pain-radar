"""CLI subpackage for Pain Radar.

Provides a modular CLI structure with commands organized by function.
"""

from __future__ import annotations

import typer
from rich.console import Console

from ..config import Settings, get_settings
from ..logging_config import configure_logging, get_logger

# Create main app
app = typer.Typer(
    name="pain-radar",
    help="Track Reddit pain points and generate weekly Pain Cluster digests.",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        from .. import __version__

        console.print(f"pain-radar {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
):
    """Pain Radar - Track recurring Reddit pain points and cluster them for insights."""
    pass


# Import and register command modules
from . import fetch, ideas, pipeline, report, db, cluster, web, alerts, sources  # noqa: E402, F401
