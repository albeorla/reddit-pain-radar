"""Rich progress utilities for CLI feedback."""

from __future__ import annotations

from contextlib import contextmanager

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

console = Console()


def create_progress() -> Progress:
    """Create a configured Progress instance for pipeline operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )


@contextmanager
def progress_context():
    """Context manager for progress display."""
    progress = create_progress()
    with progress:
        yield progress


# Shared progress instance for use across async operations
_current_progress: Progress | None = None
_fetch_task_id = None
_analyze_task_id = None


def set_progress(progress: Progress | None):
    """Set the current progress instance."""
    global _current_progress
    _current_progress = progress


def get_progress() -> Progress | None:
    """Get the current progress instance."""
    return _current_progress


def start_fetch_task(total: int) -> None:
    """Start the fetch progress task."""
    global _fetch_task_id
    if _current_progress:
        _fetch_task_id = _current_progress.add_task("Fetching posts...", total=total)


def advance_fetch() -> None:
    """Advance the fetch progress by 1."""
    if _current_progress and _fetch_task_id is not None:
        _current_progress.advance(_fetch_task_id)


def complete_fetch() -> None:
    """Mark fetch task as complete."""
    global _fetch_task_id
    if _current_progress and _fetch_task_id is not None:
        _current_progress.update(_fetch_task_id, description="[green]✓ Fetched posts")
    _fetch_task_id = None


def start_analyze_task(total: int) -> None:
    """Start the analyze progress task."""
    global _analyze_task_id
    if _current_progress:
        _analyze_task_id = _current_progress.add_task("Analyzing with AI...", total=total)


def advance_analyze() -> None:
    """Advance the analyze progress by 1."""
    if _current_progress and _analyze_task_id is not None:
        _current_progress.advance(_analyze_task_id)


def complete_analyze() -> None:
    """Mark analyze task as complete."""
    global _analyze_task_id
    if _current_progress and _analyze_task_id is not None:
        _current_progress.update(_analyze_task_id, description="[green]✓ Analysis complete")
    _analyze_task_id = None
