"""
CoPaw Code CLI entry point.

Provides the main CLI commands for CoPaw Code.
"""

import click

__version__ = "0.1.0"


@click.group()
@click.version_option(version=__version__, prog_name="copaw")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """
    CoPaw Code - AI-powered coding assistant.

    A Claude Code-like AI coding assistant for intelligent code
    understanding, generation, and modification.
    """
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    if debug:
        click.echo("Debug mode enabled")


@cli.command()
@click.option("--host", default="0.0.0.0", help="API host")
@click.option("--port", default=8000, help="API port")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def api(host: str, port: int, reload: bool) -> None:
    """Start the REST API server."""
    import uvicorn

    click.echo(f"Starting CoPaw Code API v{__version__}")
    click.echo(f"Server: http://{host}:{port}")
    click.echo("Press Ctrl+C to stop")

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@cli.command()
@click.option("--working-dir", default=".", help="Working directory")
@click.option("--provider", default=None, help="LLM provider (anthropic/openai)")
@click.option("--model", default=None, help="Model name")
def shell(working_dir: str, provider: str | None, model: str | None) -> None:
    """Start an interactive shell session."""
    click.echo(f"CoPaw Code v{__version__}")
    click.echo("Starting interactive shell...")
    click.echo("Interactive shell is not yet implemented.")


@cli.command()
def version() -> None:
    """Show version information."""
    click.echo(f"CoPaw Code v{__version__}")


@cli.command()
@click.argument("prompt")
@click.option("--working-dir", default=".", help="Working directory")
@click.option("--output", "-o", default=None, help="Output file")
def run(prompt: str, working_dir: str, output: str | None) -> None:
    """Execute a single prompt and exit."""
    click.echo(f"Processing: {prompt[:50]}...")
    click.echo("Command execution is not yet implemented.")


@cli.command()
def config() -> None:
    """Show current configuration."""
    try:
        import yaml

        from core.config import get_settings

        settings = get_settings()
        # Convert enums to strings for YAML output
        config_dict = {
            "app_name": settings.app_name,
            "version": settings.app_version,
            "debug": settings.debug,
            "log_level": str(settings.log_level),
            "llm_provider": str(settings.default_provider),
            "llm_model": settings.default_model,
        }
        click.echo("Current Configuration:")
        click.echo(yaml.dump(config_dict, default_flow_style=False))
    except ImportError:
        click.echo("Configuration module not available.")


if __name__ == "__main__":
    cli()
