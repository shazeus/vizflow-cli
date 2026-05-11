"""Command-line interface for Vizflow."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

import click
from rich.console import Console

from . import __version__
from .charting import CHART_TYPES, EXPORT_FORMATS, ChartError, make_chart, save_figure
from .compare import render_compare, write_compare_html
from .dashboard import write_dashboard
from .io import DataLoadError, default_output_path, infer_format, read_data, write_data
from .schema import render_schema
from .server import create_app


console = Console()
F = TypeVar("F", bound=Callable[..., object])
STATIC_FORMATS = {"png", "svg", "pdf"}


def _friendly_errors(func: F) -> F:
    def wrapper(*args: object, **kwargs: object) -> object:
        try:
            return func(*args, **kwargs)
        except (DataLoadError, ChartError) as exc:
            raise click.ClickException(str(exc)) from exc
        except OSError as exc:
            raise click.ClickException(str(exc)) from exc

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper  # type: ignore[return-value]


def _save_chart_with_fallback(
    frame,
    fig,
    destination: str,
    output_format: str,
    chart_type: str,
    *,
    x: str | None,
    y: str | None,
    color: str | None,
    title: str | None = None,
) -> Path:
    try:
        return save_figure(fig, destination, output_format)
    except ChartError:
        if output_format not in STATIC_FORMATS:
            raise
        import contextlib
        import io

        with contextlib.redirect_stderr(io.StringIO()):
            from .static import save_static_chart

        console.print("[yellow]Plotly static export unavailable; using Matplotlib fallback.[/]")
        return save_static_chart(
            frame,
            chart_type,
            destination,
            output_format=output_format,
            x=x,
            y=y,
            color=color,
            title=title,
        )


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="vizflow")
def cli() -> None:
    """Build visualization pipelines from CSV, JSON, SQL, and stdin data."""


@cli.command()
@click.argument("file", required=False)
@click.option("--type", "chart_type", type=click.Choice(CHART_TYPES), default="auto", show_default=True)
@click.option("--x", help="Column to use for the x axis or category labels.")
@click.option("--y", help="Column to use for the y axis or values.")
@click.option("--color", help="Optional column used for color grouping.")
@click.option("--title", help="Chart title.")
@click.option("-o", "--output", help="Output chart path. Defaults to <input>-chart.html.")
@click.option("--format", "output_format", type=click.Choice(EXPORT_FORMATS), help="Output format.")
@click.option("--query", help="SQL query for SQLite database or SQL script inputs.")
@click.option("--table", help="Table name for SQLite database or SQL script inputs.")
@_friendly_errors
def plot(
    file: str | None,
    chart_type: str,
    x: str | None,
    y: str | None,
    color: str | None,
    title: str | None,
    output: str | None,
    output_format: str | None,
    query: str | None,
    table: str | None,
) -> None:
    """Generate a single interactive chart."""

    frame = read_data(file, query=query, table=table)
    fig = make_chart(frame, chart_type, x=x, y=y, color=color, title=title)
    fmt = output_format or (Path(output).suffix.lstrip(".") if output else "html")
    destination = output or str(default_output_path(file, fmt, "chart"))
    saved = _save_chart_with_fallback(
        frame,
        fig,
        destination,
        fmt,
        chart_type,
        x=x,
        y=y,
        color=color,
        title=title,
    )
    console.print(f"[green]Chart written:[/] {saved}")


@cli.command()
@click.argument("file")
@click.option("--charts", help='Comma-separated specs, e.g. "bar:region,line:date:revenue".')
@click.option("--title", default="Vizflow Dashboard", show_default=True)
@click.option("-o", "--output", help="Output dashboard path. Defaults to <input>-dashboard.html.")
@click.option("--query", help="SQL query for SQLite database or SQL script inputs.")
@click.option("--table", help="Table name for SQLite database or SQL script inputs.")
@_friendly_errors
def dashboard(
    file: str,
    charts: str | None,
    title: str,
    output: str | None,
    query: str | None,
    table: str | None,
) -> None:
    """Combine multiple charts into a single HTML dashboard."""

    frame = read_data(file, query=query, table=table)
    destination = output or str(default_output_path(file, "html", "dashboard"))
    saved = write_dashboard(frame, charts, destination, title=title)
    console.print(f"[green]Dashboard written:[/] {saved}")


@cli.command()
@click.argument("file", required=False)
@click.option("--query", help="SQL query for SQLite database or SQL script inputs.")
@click.option("--table", help="Table name for SQLite database or SQL script inputs.")
@_friendly_errors
def schema(file: str | None, query: str | None, table: str | None) -> None:
    """Inspect data types, null counts, unique values, stats, and chart suggestions."""

    frame = read_data(file, query=query, table=table)
    render_schema(console, frame)


@cli.command()
@click.argument("file")
@click.option("--to", "output_format", type=click.Choice(["csv", "json", "parquet"]), required=True)
@click.option("-o", "--output", help="Output path. Defaults to <input>.<format>.")
@click.option("--query", help="SQL query for SQLite database or SQL script inputs.")
@click.option("--table", help="Table name for SQLite database or SQL script inputs.")
@_friendly_errors
def convert(
    file: str,
    output_format: str,
    output: str | None,
    query: str | None,
    table: str | None,
) -> None:
    """Convert data between CSV, JSON, and Parquet."""

    frame = read_data(file, query=query, table=table)
    destination = output or str(default_output_path(file, output_format))
    saved = write_data(frame, destination, infer_format(destination, output_format))
    console.print(f"[green]Converted data written:[/] {saved}")


@cli.command()
@click.argument("file")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=5050, type=int, show_default=True)
@click.option("--type", "chart_type", type=click.Choice(CHART_TYPES), default="auto", show_default=True)
@click.option("--query", help="SQL query for SQLite database or SQL script inputs.")
@click.option("--table", help="Table name for SQLite database or SQL script inputs.")
@_friendly_errors
def serve(
    file: str,
    host: str,
    port: int,
    chart_type: str,
    query: str | None,
    table: str | None,
) -> None:
    """Start a local web server for interactive chart preview."""

    frame = read_data(file, query=query, table=table)
    app = create_app(frame, source_name=file, default_chart=chart_type)
    console.print(f"[green]Serving Vizflow preview:[/] http://{host}:{port}")
    app.run(host=host, port=port)


@cli.command()
@click.argument("file", required=False)
@click.option("--format", "output_format", type=click.Choice(EXPORT_FORMATS), required=True)
@click.option("--type", "chart_type", type=click.Choice(CHART_TYPES), default="auto", show_default=True)
@click.option("--x", help="Column to use for the x axis or category labels.")
@click.option("--y", help="Column to use for the y axis or values.")
@click.option("--color", help="Optional column used for color grouping.")
@click.option("-o", "--output", help="Output path. Defaults to <input>-export.<format>.")
@click.option("--query", help="SQL query for SQLite database or SQL script inputs.")
@click.option("--table", help="Table name for SQLite database or SQL script inputs.")
@_friendly_errors
def export(
    file: str | None,
    output_format: str,
    chart_type: str,
    x: str | None,
    y: str | None,
    color: str | None,
    output: str | None,
    query: str | None,
    table: str | None,
) -> None:
    """Export a chart as PNG, SVG, HTML, or PDF."""

    frame = read_data(file, query=query, table=table)
    fig = make_chart(frame, chart_type, x=x, y=y, color=color)
    destination = output or str(default_output_path(file, output_format, "export"))
    saved = _save_chart_with_fallback(
        frame,
        fig,
        destination,
        output_format,
        chart_type,
        x=x,
        y=y,
        color=color,
    )
    console.print(f"[green]Export written:[/] {saved}")


@cli.command()
@click.argument("file1")
@click.argument("file2")
@click.option("-o", "--output", help="Output comparison report. Defaults to vizflow-compare.html.")
@_friendly_errors
def compare(file1: str, file2: str, output: str | None) -> None:
    """Compare two datasets and generate a visual HTML report."""

    left = read_data(file1)
    right = read_data(file2)
    left_label = Path(file1).name
    right_label = Path(file2).name
    render_compare(console, left, right, left_label, right_label)
    destination = output or str(Path.cwd() / "vizflow-compare.html")
    saved = write_compare_html(left, right, left_label, right_label, destination)
    console.print(f"[green]Comparison report written:[/] {saved}")
