"""Dataset comparison reports."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.io import to_html
from rich.console import Console
from rich.table import Table

from .schema import classify_series


def compare_summary(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, Any]:
    left_nulls = int(left.isna().sum().sum())
    right_nulls = int(right.isna().sum().sum())
    return {
        "left_rows": len(left),
        "right_rows": len(right),
        "row_delta": len(right) - len(left),
        "left_columns": len(left.columns),
        "right_columns": len(right.columns),
        "column_delta": len(right.columns) - len(left.columns),
        "left_nulls": left_nulls,
        "right_nulls": right_nulls,
        "null_delta": right_nulls - left_nulls,
        "added_columns": sorted(set(right.columns) - set(left.columns)),
        "removed_columns": sorted(set(left.columns) - set(right.columns)),
        "shared_columns": sorted(set(left.columns) & set(right.columns)),
    }


def schema_diff(left: pd.DataFrame, right: pd.DataFrame) -> list[dict[str, str]]:
    columns = sorted(set(left.columns) | set(right.columns))
    rows: list[dict[str, str]] = []
    for column in columns:
        left_type = classify_series(left[column]) if column in left.columns else "-"
        right_type = classify_series(right[column]) if column in right.columns else "-"
        status = "same" if left_type == right_type else "changed"
        if column not in left.columns:
            status = "added"
        elif column not in right.columns:
            status = "removed"
        rows.append({"column": column, "left_type": left_type, "right_type": right_type, "status": status})
    return rows


def compare_figure(left: pd.DataFrame, right: pd.DataFrame, left_label: str, right_label: str) -> go.Figure:
    metrics = ["Rows", "Columns", "Null cells", "Duplicate rows"]
    left_values = [len(left), len(left.columns), int(left.isna().sum().sum()), int(left.duplicated().sum())]
    right_values = [len(right), len(right.columns), int(right.isna().sum().sum()), int(right.duplicated().sum())]
    fig = go.Figure()
    fig.add_bar(name=left_label, x=metrics, y=left_values)
    fig.add_bar(name=right_label, x=metrics, y=right_values)
    fig.update_layout(
        barmode="group",
        title="Dataset comparison",
        template="plotly_white",
        margin=dict(l=48, r=32, t=72, b=48),
    )
    return fig


def render_compare(console: Console, left: pd.DataFrame, right: pd.DataFrame, left_label: str, right_label: str) -> None:
    summary = compare_summary(left, right)
    console.print(
        f"[bold]{left_label}[/]: {summary['left_rows']:,} rows, {summary['left_columns']:,} columns  "
        f"[bold]{right_label}[/]: {summary['right_rows']:,} rows, {summary['right_columns']:,} columns"
    )

    delta = Table(title="Dataset Delta")
    delta.add_column("Metric")
    delta.add_column(left_label, justify="right")
    delta.add_column(right_label, justify="right")
    delta.add_column("Delta", justify="right")
    delta.add_row("Rows", f"{summary['left_rows']:,}", f"{summary['right_rows']:,}", f"{summary['row_delta']:+,}")
    delta.add_row(
        "Columns",
        f"{summary['left_columns']:,}",
        f"{summary['right_columns']:,}",
        f"{summary['column_delta']:+,}",
    )
    delta.add_row(
        "Null cells",
        f"{summary['left_nulls']:,}",
        f"{summary['right_nulls']:,}",
        f"{summary['null_delta']:+,}",
    )
    console.print(delta)

    diff = Table(title="Schema Differences")
    diff.add_column("Column", style="cyan")
    diff.add_column(left_label)
    diff.add_column(right_label)
    diff.add_column("Status")
    for row in schema_diff(left, right):
        if row["status"] != "same":
            diff.add_row(row["column"], row["left_type"], row["right_type"], row["status"])
    console.print(diff)


def build_compare_html(left: pd.DataFrame, right: pd.DataFrame, left_label: str, right_label: str) -> str:
    summary = compare_summary(left, right)
    diff_rows = "\n".join(
        "<tr>"
        f"<td>{escape(row['column'])}</td>"
        f"<td>{escape(row['left_type'])}</td>"
        f"<td>{escape(row['right_type'])}</td>"
        f"<td>{escape(row['status'])}</td>"
        "</tr>"
        for row in schema_diff(left, right)
    )
    fig_html = to_html(compare_figure(left, right, left_label, right_label), include_plotlyjs="cdn", full_html=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vizflow Compare</title>
  <style>
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f8fb;
      color: #1c2430;
    }}
    header {{ padding: 28px 36px 18px; background: #ffffff; border-bottom: 1px solid #d9dee7; }}
    main {{ padding: 24px 36px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .metric {{ background: #ffffff; border: 1px solid #d9dee7; border-radius: 8px; padding: 14px; }}
    .label {{ color: #5b6675; font-size: 13px; }}
    .value {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; border: 1px solid #d9dee7; }}
    th, td {{ border-bottom: 1px solid #e8ebf0; padding: 10px 12px; text-align: left; }}
    th {{ background: #f0f3f8; }}
    .chart {{ margin: 18px 0; border: 1px solid #d9dee7; border-radius: 8px; overflow: hidden; background: #ffffff; }}
  </style>
</head>
<body>
  <header>
    <h1>Vizflow Compare</h1>
    <p>{escape(left_label)} vs {escape(right_label)}</p>
  </header>
  <main>
    <section class="metrics">
      <div class="metric"><div class="label">Row delta</div><div class="value">{summary['row_delta']:+,}</div></div>
      <div class="metric"><div class="label">Column delta</div><div class="value">{summary['column_delta']:+,}</div></div>
      <div class="metric"><div class="label">Null cell delta</div><div class="value">{summary['null_delta']:+,}</div></div>
    </section>
    <section class="chart">{fig_html}</section>
    <h2>Schema Diff</h2>
    <table>
      <thead><tr><th>Column</th><th>{escape(left_label)}</th><th>{escape(right_label)}</th><th>Status</th></tr></thead>
      <tbody>{diff_rows}</tbody>
    </table>
  </main>
</body>
</html>
"""


def write_compare_html(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_label: str,
    right_label: str,
    output: str | Path,
) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_compare_html(left, right, left_label, right_label), encoding="utf-8")
    return path

