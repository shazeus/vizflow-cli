"""Dashboard assembly helpers."""

from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
from plotly.io import to_html

from .charting import ChartError, make_chart
from .schema import classify_series, suggest_charts


def _split_spec(spec: str) -> list[str]:
    return [part.strip() for part in spec.split(":") if part.strip()]


def parse_chart_specs(charts: str | None, frame: pd.DataFrame) -> list[dict[str, str | None]]:
    """Parse dashboard chart specs like ``bar:region,line:date:revenue``."""

    parsed: list[dict[str, str | None]] = []
    if charts:
        for raw in charts.split(","):
            parts = _split_spec(raw)
            if not parts:
                continue
            chart_type = parts[0]
            if chart_type == "auto":
                chart_type = "bar"
            if len(parts) == 1:
                parsed.append({"type": chart_type, "x": None, "y": None, "color": None})
            elif len(parts) == 2:
                column = parts[1]
                if column not in frame.columns:
                    raise ChartError(f"Dashboard column not found: {column}")
                semantic_type = classify_series(frame[column])
                if chart_type in {"line", "bar", "scatter"} and semantic_type == "numeric":
                    parsed.append({"type": chart_type, "x": None, "y": column, "color": None})
                else:
                    parsed.append({"type": chart_type, "x": column, "y": None, "color": None})
            elif len(parts) == 3:
                parsed.append({"type": chart_type, "x": parts[1], "y": parts[2], "color": None})
            else:
                parsed.append({"type": chart_type, "x": parts[1], "y": parts[2], "color": parts[3]})

    if parsed:
        return parsed

    for suggestion in suggest_charts(frame)[:4]:
        parsed.append({"type": suggestion["type"], "x": None, "y": None, "color": None})
    return parsed or [{"type": "bar", "x": None, "y": None, "color": None}]


def build_dashboard_html(
    frame: pd.DataFrame,
    charts: str | None,
    *,
    title: str = "Vizflow Dashboard",
) -> str:
    specs = parse_chart_specs(charts, frame)
    fragments: list[str] = []
    for index, spec in enumerate(specs):
        fig = make_chart(
            frame,
            str(spec["type"]),
            x=spec.get("x"),
            y=spec.get("y"),
            color=spec.get("color"),
            title=f"{str(spec['type']).title()} chart",
        )
        fragments.append(to_html(fig, include_plotlyjs="cdn" if index == 0 else False, full_html=False))

    escaped_title = escape(title)
    chart_cards = "\n".join(f'<section class="chart">{fragment}</section>' for fragment in fragments)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f8fb;
      color: #1c2430;
    }}
    body {{ margin: 0; }}
    header {{
      padding: 28px 36px 18px;
      border-bottom: 1px solid #d9dee7;
      background: #ffffff;
    }}
    h1 {{ margin: 0 0 6px; font-size: 28px; letter-spacing: 0; }}
    p {{ margin: 0; color: #5b6675; }}
    main {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 18px;
      padding: 24px;
    }}
    .chart {{
      min-height: 420px;
      border: 1px solid #d9dee7;
      border-radius: 8px;
      background: #ffffff;
      overflow: hidden;
    }}
    @media (max-width: 640px) {{
      header {{ padding: 22px 18px 14px; }}
      main {{ grid-template-columns: 1fr; padding: 14px; }}
      .chart {{ min-height: 360px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escaped_title}</h1>
    <p>{len(frame):,} rows, {len(frame.columns):,} columns</p>
  </header>
  <main>
    {chart_cards}
  </main>
</body>
</html>
"""


def write_dashboard(
    frame: pd.DataFrame,
    charts: str | None,
    output: str | Path,
    *,
    title: str = "Vizflow Dashboard",
) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_dashboard_html(frame, charts, title=title), encoding="utf-8")
    return path

