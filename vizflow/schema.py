"""Schema profiling and chart recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import warnings

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
)
from rich.console import Console
from rich.table import Table


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    dtype: str
    semantic_type: str
    nulls: int
    null_pct: float
    unique: int
    sample: str
    stats: dict[str, Any]


def _sample_values(series: pd.Series, limit: int = 4) -> str:
    values = series.dropna().astype(str).unique().tolist()[:limit]
    return ", ".join(values) if values else "-"


def _parse_datetimes(values: pd.Series) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return pd.to_datetime(values, errors="coerce", utc=False, format="mixed")


def classify_series(series: pd.Series) -> str:
    """Map pandas dtypes to visualization-friendly semantic types."""

    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    if is_bool_dtype(series):
        return "boolean"
    if is_datetime64_any_dtype(series):
        return "datetime"
    if is_numeric_dtype(series):
        return "numeric"

    sample = non_null.astype(str).head(100)
    parsed = _parse_datetimes(sample)
    if len(parsed) and parsed.notna().mean() >= 0.8:
        return "datetime"

    unique = non_null.nunique(dropna=True)
    if unique <= max(20, int(len(non_null) * 0.25)):
        return "categorical"
    return "text"


def profile_column(series: pd.Series) -> ColumnProfile:
    nulls = int(series.isna().sum())
    total = int(len(series))
    semantic_type = classify_series(series)
    stats: dict[str, Any] = {}

    if semantic_type == "numeric":
        numeric = pd.to_numeric(series, errors="coerce")
        stats = {
            "min": _round_value(numeric.min()),
            "max": _round_value(numeric.max()),
            "mean": _round_value(numeric.mean()),
            "median": _round_value(numeric.median()),
            "std": _round_value(numeric.std()),
        }
    elif semantic_type == "datetime":
        dates = _parse_datetimes(series)
        if dates.notna().any():
            stats = {
                "min": str(dates.min()),
                "max": str(dates.max()),
            }

    return ColumnProfile(
        name=str(series.name),
        dtype=str(series.dtype),
        semantic_type=semantic_type,
        nulls=nulls,
        null_pct=(nulls / total * 100) if total else 0.0,
        unique=int(series.nunique(dropna=True)),
        sample=_sample_values(series),
        stats=stats,
    )


def _round_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 4)
    return value


def inspect_schema(frame: pd.DataFrame) -> list[ColumnProfile]:
    return [profile_column(frame[column]) for column in frame.columns]


def columns_by_type(frame: pd.DataFrame) -> dict[str, list[str]]:
    groups = {"numeric": [], "datetime": [], "categorical": [], "boolean": [], "text": [], "empty": []}
    for profile in inspect_schema(frame):
        groups.setdefault(profile.semantic_type, []).append(profile.name)
    return groups


def suggest_charts(frame: pd.DataFrame) -> list[dict[str, str]]:
    """Suggest likely chart types for the dataframe."""

    groups = columns_by_type(frame)
    numeric = groups["numeric"]
    temporal = groups["datetime"]
    categorical = groups["categorical"] + groups["boolean"]
    text = groups["text"]
    suggestions: list[dict[str, str]] = []

    if temporal and numeric:
        suggestions.append(
            {
                "type": "line",
                "columns": f"{temporal[0]} -> {numeric[0]}",
                "reason": "datetime and numeric columns are good for trends",
            }
        )
    if categorical and numeric:
        suggestions.append(
            {
                "type": "bar",
                "columns": f"{categorical[0]} -> {numeric[0]}",
                "reason": "categorical and numeric columns support comparisons",
            }
        )
        if frame[categorical[0]].nunique(dropna=True) <= 12:
            suggestions.append(
                {
                    "type": "pie",
                    "columns": f"{categorical[0]} -> {numeric[0]}",
                    "reason": "few categories can show part-to-whole distribution",
                }
            )
        if len(categorical) >= 1:
            suggestions.append(
                {
                    "type": "treemap",
                    "columns": f"{categorical[0]} -> {numeric[0]}",
                    "reason": "hierarchical category share is available",
                }
            )
    if len(numeric) >= 2:
        suggestions.append(
            {
                "type": "scatter",
                "columns": f"{numeric[0]} vs {numeric[1]}",
                "reason": "two numeric columns support relationship analysis",
            }
        )
        suggestions.append(
            {
                "type": "heatmap",
                "columns": ", ".join(numeric[:6]),
                "reason": "numeric columns can be summarized as correlations",
            }
        )
    if numeric:
        suggestions.append(
            {
                "type": "histogram",
                "columns": numeric[0],
                "reason": "numeric columns support distribution analysis",
            }
        )
    if categorical and not numeric:
        suggestions.append(
            {
                "type": "bar",
                "columns": categorical[0],
                "reason": "category counts can be visualized directly",
            }
        )
    if text and not suggestions:
        suggestions.append(
            {
                "type": "bar",
                "columns": text[0],
                "reason": "top value counts are the safest default",
            }
        )

    return suggestions[:6]


def schema_as_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for profile in inspect_schema(frame):
        records.append(
            {
                "name": profile.name,
                "dtype": profile.dtype,
                "semantic_type": profile.semantic_type,
                "nulls": profile.nulls,
                "null_pct": profile.null_pct,
                "unique": profile.unique,
                "sample": profile.sample,
                "stats": profile.stats,
            }
        )
    return records


def render_schema(console: Console, frame: pd.DataFrame) -> None:
    """Render a schema inspector report with Rich."""

    console.print(f"[bold]Rows:[/] {len(frame):,}  [bold]Columns:[/] {len(frame.columns):,}")
    table = Table(title="Schema Inspector", show_lines=False)
    table.add_column("Column", style="cyan", no_wrap=True)
    table.add_column("Pandas dtype", style="magenta")
    table.add_column("Type", style="green")
    table.add_column("Nulls", justify="right")
    table.add_column("Unique", justify="right")
    table.add_column("Stats / sample", overflow="fold")

    for profile in inspect_schema(frame):
        if profile.stats:
            details = ", ".join(f"{key}={value}" for key, value in profile.stats.items() if value is not None)
        else:
            details = profile.sample
        table.add_row(
            profile.name,
            profile.dtype,
            profile.semantic_type,
            f"{profile.nulls:,} ({profile.null_pct:.1f}%)",
            f"{profile.unique:,}",
            details or "-",
        )
    console.print(table)

    suggestions = suggest_charts(frame)
    if suggestions:
        suggestion_table = Table(title="Suggested Charts")
        suggestion_table.add_column("Chart", style="bold yellow")
        suggestion_table.add_column("Columns", style="cyan")
        suggestion_table.add_column("Why")
        for suggestion in suggestions:
            suggestion_table.add_row(suggestion["type"], suggestion["columns"], suggestion["reason"])
        console.print(suggestion_table)
