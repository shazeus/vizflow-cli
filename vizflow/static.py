"""Matplotlib static export fallback for PNG, SVG, and PDF outputs."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import textwrap
import warnings

_mpl_config = Path(tempfile.gettempdir()) / "vizflow-matplotlib"
_mpl_config.mkdir(parents=True, exist_ok=True)
(_mpl_config / "fontconfig").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_config))
os.environ.setdefault("XDG_CACHE_HOME", str(_mpl_config))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from .charting import ChartError
from .schema import classify_series, columns_by_type, suggest_charts


STATIC_FORMATS = {"png", "svg", "pdf"}


def _first(groups: dict[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        values = groups.get(key) or []
        if values:
            return values[0]
    return None


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if classify_series(frame[column]) == "numeric"]


def _validate_column(frame: pd.DataFrame, column: str | None, option: str) -> str | None:
    if column is None:
        return None
    if column not in frame.columns:
        raise ChartError(f"{option} column not found: {column}")
    return column


def _parse_axis(frame: pd.DataFrame, column: str) -> pd.Series:
    if classify_series(frame[column]) != "datetime":
        return frame[column]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return pd.to_datetime(frame[column], errors="coerce", format="mixed")


def _resolve_chart_type(frame: pd.DataFrame, chart_type: str) -> str:
    if chart_type != "auto":
        return chart_type
    suggestions = suggest_charts(frame)
    return suggestions[0]["type"] if suggestions else "bar"


def _style_axes(ax: plt.Axes, title: str | None = None) -> None:
    ax.grid(True, axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    if title:
        ax.set_title(title)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def _draw_bar(
    ax: plt.Axes,
    frame: pd.DataFrame,
    x: str | None,
    y: str | None,
    color: str | None,
    title: str | None,
) -> None:
    groups = columns_by_type(frame)
    x = x or _first(groups, "categorical", "boolean", "datetime", "text") or str(frame.columns[0])
    y = y or _first(groups, "numeric")
    color = color if color and color in frame.columns and color != x else None

    if color and y and y in frame.columns:
        grouped_frame = frame.groupby([x, color], dropna=False)[y].sum(numeric_only=True).unstack(fill_value=0)
        grouped_frame = grouped_frame.loc[grouped_frame.sum(axis=1).sort_values(ascending=False).head(30).index]
        grouped_frame.index = grouped_frame.index.astype(str)
        grouped_frame.plot(kind="bar", ax=ax)
        ax.legend(title=color)
        ylabel = y
    elif color:
        grouped_frame = frame.groupby([x, color], dropna=False).size().unstack(fill_value=0)
        grouped_frame = grouped_frame.loc[grouped_frame.sum(axis=1).sort_values(ascending=False).head(30).index]
        grouped_frame.index = grouped_frame.index.astype(str)
        grouped_frame.plot(kind="bar", ax=ax)
        ax.legend(title=color)
        ylabel = "count"
    else:
        if y and y in frame.columns:
            grouped = frame.groupby(x, dropna=False)[y].sum(numeric_only=True).sort_values(ascending=False).head(30)
            ylabel = y
        else:
            grouped = frame[x].astype(str).fillna("(null)").value_counts().head(30)
            ylabel = "count"
        ax.bar(grouped.index.astype(str), grouped.to_numpy(), color="#2f6fbd")
    ax.set_xlabel(x)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=35)
    _style_axes(ax, title or "Bar chart")


def _draw_line(
    ax: plt.Axes,
    frame: pd.DataFrame,
    x: str | None,
    y: str | None,
    color: str | None,
    title: str | None,
) -> None:
    groups = columns_by_type(frame)
    y = y or _first(groups, "numeric")
    if not y:
        raise ChartError("Line charts need at least one numeric column.")
    plot_frame = frame.copy()
    if x:
        plot_frame[x] = _parse_axis(plot_frame, x)
    else:
        x = _first(groups, "datetime", "categorical")
        if x:
            plot_frame[x] = _parse_axis(plot_frame, x)
        else:
            x = "_row"
            plot_frame.insert(0, x, range(1, len(plot_frame) + 1))

    plot_frame = plot_frame.sort_values(x)
    if color and color in plot_frame.columns:
        for label, group in plot_frame.groupby(color, dropna=False):
            ax.plot(group[x], group[y], marker="o", linewidth=2, label=str(label))
        ax.legend(title=color)
    else:
        ax.plot(plot_frame[x], plot_frame[y], marker="o", linewidth=2, color="#2f6fbd")
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.tick_params(axis="x", rotation=30)
    _style_axes(ax, title or "Line chart")


def _draw_scatter(
    ax: plt.Axes,
    frame: pd.DataFrame,
    x: str | None,
    y: str | None,
    color: str | None,
    title: str | None,
) -> None:
    numeric = _numeric_columns(frame)
    x = x or (numeric[0] if numeric else None)
    y = y or next((column for column in numeric if column != x), None)
    if not x or not y:
        raise ChartError("Scatter charts need two numeric columns.")
    if color and color in frame.columns:
        for label, group in frame.groupby(color, dropna=False):
            ax.scatter(group[x], group[y], label=str(label), alpha=0.85)
        ax.legend(title=color)
    else:
        ax.scatter(frame[x], frame[y], color="#2f6fbd", alpha=0.85)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    _style_axes(ax, title or "Scatter chart")


def _draw_pie(ax: plt.Axes, frame: pd.DataFrame, x: str | None, y: str | None, title: str | None) -> None:
    groups = columns_by_type(frame)
    names = x or _first(groups, "categorical", "boolean", "text") or str(frame.columns[0])
    values = y or _first(groups, "numeric")
    if values and values in frame.columns:
        grouped = frame.groupby(names, dropna=False)[values].sum(numeric_only=True).sort_values(ascending=False).head(12)
    else:
        grouped = frame[names].astype(str).fillna("(null)").value_counts().head(12)
    ax.pie(grouped.to_numpy(), labels=grouped.index.astype(str), autopct="%1.1f%%", startangle=90)
    ax.set_title(title or "Pie chart")


def _draw_heatmap(ax: plt.Axes, fig: plt.Figure, frame: pd.DataFrame, title: str | None) -> None:
    numeric = frame[_numeric_columns(frame)]
    if numeric.shape[1] < 2:
        raise ChartError("Heatmaps need at least two numeric columns.")
    corr = numeric.corr(numeric_only=True)
    image = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)), corr.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(corr.index)), corr.index)
    for row_index, row in enumerate(corr.to_numpy()):
        for col_index, value in enumerate(row):
            ax.text(col_index, row_index, f"{value:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title(title or "Correlation heatmap")


def _draw_histogram(ax: plt.Axes, frame: pd.DataFrame, x: str | None, color: str | None, title: str | None) -> None:
    groups = columns_by_type(frame)
    x = x or _first(groups, "numeric", "datetime", "categorical", "text")
    if not x:
        raise ChartError("Histogram charts need at least one column.")
    if classify_series(frame[x]) == "numeric":
        if color and color in frame.columns:
            for label, group in frame.groupby(color, dropna=False):
                ax.hist(pd.to_numeric(group[x], errors="coerce").dropna(), bins=30, alpha=0.6, label=str(label))
            ax.legend(title=color)
        else:
            ax.hist(pd.to_numeric(frame[x], errors="coerce").dropna(), bins=30, color="#2f6fbd", alpha=0.85)
        ax.set_ylabel("count")
    else:
        counts = frame[x].astype(str).fillna("(null)").value_counts().head(30)
        ax.bar(counts.index.astype(str), counts.to_numpy(), color="#2f6fbd")
        ax.tick_params(axis="x", rotation=35)
        ax.set_ylabel("count")
    ax.set_xlabel(x)
    _style_axes(ax, title or "Histogram")


def _binary_treemap(items: list[tuple[str, float]], x: float, y: float, w: float, h: float) -> list[tuple[str, float, float, float, float, float]]:
    total = sum(value for _, value in items)
    if not items or total <= 0:
        return []
    if len(items) == 1:
        label, value = items[0]
        return [(label, value, x, y, w, h)]

    half = total / 2
    running = 0.0
    split_at = 1
    for index, (_, value) in enumerate(items, start=1):
        running += value
        if running >= half:
            split_at = index
            break

    left = items[:split_at]
    right = items[split_at:]
    left_total = sum(value for _, value in left)
    if w >= h:
        left_w = w * (left_total / total)
        return _binary_treemap(left, x, y, left_w, h) + _binary_treemap(right, x + left_w, y, w - left_w, h)

    left_h = h * (left_total / total)
    return _binary_treemap(left, x, y, w, left_h) + _binary_treemap(right, x, y + left_h, w, h - left_h)


def _draw_treemap(ax: plt.Axes, frame: pd.DataFrame, x: str | None, y: str | None, title: str | None) -> None:
    groups = columns_by_type(frame)
    category = x or _first(groups, "categorical", "boolean", "text")
    if not category:
        raise ChartError("Treemaps need at least one categorical/text column.")
    values = y or _first(groups, "numeric")
    if values and values in frame.columns:
        grouped = frame.groupby(category, dropna=False)[values].sum(numeric_only=True).sort_values(ascending=False).head(20)
    else:
        grouped = frame[category].astype(str).fillna("(null)").value_counts().head(20)

    items = [(str(label), float(value)) for label, value in grouped.items() if float(value) > 0]
    rectangles = _binary_treemap(items, 0.0, 0.0, 1.0, 1.0)
    cmap = plt.get_cmap("tab20")
    for index, (label, value, x0, y0, width, height) in enumerate(rectangles):
        ax.add_patch(Rectangle((x0, y0), width, height, facecolor=cmap(index % 20), edgecolor="white", linewidth=2))
        if width * height > 0.025:
            text = "\n".join(textwrap.wrap(f"{label}\n{value:g}", width=max(8, int(width * 32))))
            ax.text(x0 + width / 2, y0 + height / 2, text, ha="center", va="center", fontsize=8, color="#111827")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title or "Treemap")


def save_static_chart(
    frame: pd.DataFrame,
    chart_type: str,
    output: str | Path,
    *,
    output_format: str | None = None,
    x: str | None = None,
    y: str | None = None,
    color: str | None = None,
    title: str | None = None,
) -> Path:
    """Save a non-interactive PNG, SVG, or PDF chart without a browser runtime."""

    path = Path(output)
    fmt = (output_format or path.suffix.lstrip(".")).lower()
    if fmt not in STATIC_FORMATS:
        raise ChartError(f"Matplotlib fallback does not support {fmt}.")
    if frame.empty:
        raise ChartError("Cannot chart an empty dataset.")

    x = _validate_column(frame, x, "--x")
    y = _validate_column(frame, y, "--y")
    color = _validate_column(frame, color, "--color")
    chart_type = _resolve_chart_type(frame, chart_type)

    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    if chart_type == "bar":
        _draw_bar(ax, frame, x, y, color, title)
    elif chart_type == "line":
        _draw_line(ax, frame, x, y, color, title)
    elif chart_type == "scatter":
        _draw_scatter(ax, frame, x, y, color, title)
    elif chart_type == "pie":
        _draw_pie(ax, frame, x, y, title)
    elif chart_type == "heatmap":
        _draw_heatmap(ax, fig, frame, title)
    elif chart_type == "histogram":
        _draw_histogram(ax, frame, x, color, title)
    elif chart_type == "treemap":
        _draw_treemap(ax, frame, x, y, title)
    else:
        plt.close(fig)
        raise ChartError(f"Unsupported chart type for static export: {chart_type}")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format=fmt, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path
