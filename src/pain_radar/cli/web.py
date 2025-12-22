"""Web server CLI command."""

import typer
import uvicorn

from . import app


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", help="Host to bind to."),
    port: int = typer.Option(8000, help="Port to bind to."),
    reload: bool = typer.Option(False, help="Enable auto-reload."),
):
    """Start the public web interface."""
    uvicorn.run(
        "pain_radar.web_app:app",
        host=host,
        port=port,
        reload=reload,
    )
