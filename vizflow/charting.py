"""Plotly chart generation for Vizflow."""

from __future__ import annotations

from pathlib import Path
import warnings

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .schema import classify_series, columns_by_type, suggest_charts


CHART_TYPES = ("auto", "bar", "line", "scatter", "pie", "heatmap", "treemap", "histogram")
EXPORT_FORMATS = ("html", "png", "svg", "pdf")


class ChartError(RuntimeError):
    """Raised when a chart cannot be created or exported."""


def _require_columns(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise ChartError("Cannot chart an empty dataset.")
    if not list(frame.columns):
        raise ChartError("Cannot chart a dataset with no columns.")


def _validate_column(frame: pd.DataFrame, column: str | None, option: str) -> str | None:
    if column is None:
        return None
    if column not in frame.columns:
        raise ChartError(f"{option} column not found: {column}")
    return column


def _first(groups: dict[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        values = groups.get(key) or []
        if values:
            return values[0]
    return None


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if classify_series(frame[column]) == "numeric"]


def _coerce_datetime_axis(frame: pd.DataFrame, column: str | None) -> pd.DataFrame:
    if not column or column not in frame.columns:
        return frame
    if classify_series(frame[column]) != "datetime":
        return frame
    out = frame.copy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        out[column] = pd.to_datetime(out[column], errors="coerce", format="mixed")
    return out


def _with_index(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.insert(0, "_row", range(1, len(out) + 1))
    return out


def _bar_chart(
    frame: pd.DataFrame,
    *,
    x: str | None,
    y: str | None,
    color: str | None,
    title: str | None,
) -> go.Figure:
    groups = columns_by_type(frame)
    x = x or _first(groups, "categorical", "boolean", "datetime", "text") or frame.columns[0]
    y = y or _first(groups, "numeric")

    frame = _coerce_datetime_axis(frame, x)
    if y and y in frame.columns:
        group_columns = [x]
        if color and color in frame.columns and color != x:
            group_columns.append(color)
        plot_frame = frame.groupby(group_columns, dropna=False, as_index=False)[y].sum(numeric_only=True)
        return px.bar(plot_frame, x=x, y=y, color=color if color in group_columns else None, title=title)

    if color and color in frame.columns and color != x:
        counts = frame.groupby([x, color], dropna=False).size().reset_index(name="count")
        return px.bar(counts, x=x, y="count", color=color, title=title or f"{x} counts")
    counts = frame[x].astype(str).fillna("(null)").value_counts().head(30).rename_axis(x).reset_index(name="count")
    return px.bar(counts, x=x, y="count", title=title or f"{x} counts")


def _line_chart(
    frame: pd.DataFrame,
    *,
    x: str | None,
    y: str | None,
    color: str | None,
    title: str | None,
) -> go.Figure:
    groups = columns_by_type(frame)
    y = y or _first(groups, "numeric")
    if not y:
        raise ChartError("Line charts need at least one numeric column. Pass --y explicitly if needed.")
    x = x or _first(groups, "datetime", "categorical") or "_row"
    plot_frame = _with_index(frame) if x == "_row" else frame.copy()
    plot_frame = _coerce_datetime_axis(plot_frame, x)
    return px.line(plot_frame.sort_values(x), x=x, y=y, color=color, markers=True, title=title)


def _scatter_chart(
    frame: pd.DataFrame,
    *,
    x: str | None,
    y: str | None,
    color: str | None,
    title: str | None,
) -> go.Figure:
    numeric = _numeric_columns(frame)
    if not x:
        x = numeric[0] if numeric else None
    if not y:
        y = next((column for column in numeric if column != x), None)
    if not x or not y:
        raise ChartError("Scatter charts need two numeric columns. Pass --x and --y explicitly.")
    return px.scatter(frame, x=x, y=y, color=color, trendline=None, title=title)


def _pie_chart(frame: pd.DataFrame, *, x: str | None, y: str | None, title: str | None) -> go.Figure:
    groups = columns_by_type(frame)
    names = x or _first(groups, "categorical", "boolean", "text") or frame.columns[0]
    values = y or _first(groups, "numeric")
    if values and values in frame.columns:
        plot_frame = frame.groupby(names, dropna=False, as_index=False)[values].sum(numeric_only=True)
        return px.pie(plot_frame, names=names, values=values, title=title)
    counts = frame[names].astype(str).fillna("(null)").value_counts().head(20).rename_axis(names).reset_index(name="count")
    return px.pie(counts, names=names, values="count", title=title or f"{names} share")


def _heatmap_chart(frame: pd.DataFrame, *, title: str | None) -> go.Figure:
    numeric = frame[_numeric_columns(frame)]
    if numeric.shape[1] < 2:
        raise ChartError("Heatmaps need at least two numeric columns.")
    corr = numeric.corr(numeric_only=True)
    return px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        title=title or "Numeric correlation heatmap",
    )


def _treemap_chart(
    frame: pd.DataFrame,
    *,
    x: str | None,
    y: str | None,
    color: str | None,
    title: str | None,
) -> go.Figure:
    groups = columns_by_type(frame)
    path = [x] if x else (groups["categorical"] + groups["boolean"] + groups["text"])[:3]
    if not path:
        raise ChartError("Treemaps need at least one categorical/text column.")
    values = y or _first(groups, "numeric")
    if values and values in frame.columns:
        plot_frame = frame.groupby(path, dropna=False, as_index=False)[values].sum(numeric_only=True)
    else:
        plot_frame = frame.groupby(path, dropna=False).size().reset_index(name="count")
        values = "count"
    return px.treemap(plot_frame, path=path, values=values, color=color, title=title)


def _histogram_chart(frame: pd.DataFrame, *, x: str | None, color: str | None, title: str | None) -> go.Figure:
    groups = columns_by_type(frame)
    x = x or _first(groups, "numeric", "datetime", "categorical", "text")
    if not x:
        raise ChartError("Histogram charts need at least one column.")
    plot_frame = _coerce_datetime_axis(frame, x)
    return px.histogram(plot_frame, x=x, color=color, nbins=30, title=title)


def make_chart(
    frame: pd.DataFrame,
    chart_type: str = "auto",
    *,
    x: str | None = None,
    y: str | None = None,
    color: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Create an interactive Plotly chart."""

    _require_columns(frame)
    if chart_type not in CHART_TYPES:
        raise ChartError(f"Unsupported chart type: {chart_type}")

    x = _validate_column(frame, x, "--x")
    y = _validate_column(frame, y, "--y")
    color = _validate_column(frame, color, "--color")

    if chart_type == "auto":
        suggestions = suggest_charts(frame)
        chart_type = suggestions[0]["type"] if suggestions else "bar"

    if chart_type == "bar":
        fig = _bar_chart(frame, x=x, y=y, color=color, title=title)
    elif chart_type == "line":
        fig = _line_chart(frame, x=x, y=y, color=color, title=title)
    elif chart_type == "scatter":
        fig = _scatter_chart(frame, x=x, y=y, color=color, title=title)
    elif chart_type == "pie":
        fig = _pie_chart(frame, x=x, y=y, title=title)
    elif chart_type == "heatmap":
        fig = _heatmap_chart(frame, title=title)
    elif chart_type == "treemap":
        fig = _treemap_chart(frame, x=x, y=y, color=color, title=title)
    elif chart_type == "histogram":
        fig = _histogram_chart(frame, x=x, color=color, title=title)
    else:
        raise ChartError(f"Unsupported chart type: {chart_type}")

    fig.update_layout(template="plotly_white", margin=dict(l=48, r=32, t=72, b=48))
    return fig


def save_figure(fig: go.Figure, output: str | Path, output_format: str | None = None) -> Path:
    """Save a Plotly figure as HTML, PNG, SVG, or PDF."""

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = (output_format or path.suffix.lstrip(".") or "html").lower()

    try:
        if fmt == "html":
            fig.write_html(path, include_plotlyjs="cdn", full_html=True)
        elif fmt in {"png", "svg", "pdf"}:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                fig.write_image(path, format=fmt)
        else:
            raise ChartError(f"Unsupported export format: {fmt}")
    except ValueError as exc:
        if fmt in {"png", "svg", "pdf"}:
            raise ChartError(
                "Static image export requires the kaleido package and a working Chrome/Chromium runtime."
            ) from exc
        raise ChartError(f"Could not save chart to {path}: {exc}") from exc
    except Exception as exc:
        raise ChartError(f"Could not save chart to {path}: {exc}") from exc
    return path
