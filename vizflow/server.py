"""Flask preview server for Vizflow charts."""

from __future__ import annotations

from html import escape

import pandas as pd
from flask import Flask, jsonify
from plotly.io import to_html

from .charting import ChartError, make_chart
from .dashboard import build_dashboard_html
from .schema import schema_as_records, suggest_charts


def create_app(frame: pd.DataFrame, *, source_name: str, default_chart: str = "auto") -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        suggestions = suggest_charts(frame)
        chart_type = default_chart
        if chart_type == "auto" and suggestions:
            chart_type = suggestions[0]["type"]
        try:
            fig = make_chart(frame, chart_type)
            chart_html = to_html(fig, include_plotlyjs="cdn", full_html=False)
            error_html = ""
        except ChartError as exc:
            chart_html = ""
            error_html = f'<p class="error">{escape(str(exc))}</p>'

        suggestion_links = "\n".join(
            f'<a href="/chart/{escape(item["type"])}">{escape(item["type"].title())}</a>' for item in suggestions
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vizflow Preview</title>
  <style>
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f8fb;
      color: #1c2430;
    }}
    header {{ padding: 24px 32px; background: #ffffff; border-bottom: 1px solid #d9dee7; }}
    main {{ padding: 22px 32px; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 16px; }}
    nav a {{ color: #0b63ce; text-decoration: none; font-weight: 600; }}
    .chart {{ border: 1px solid #d9dee7; border-radius: 8px; overflow: hidden; background: #ffffff; }}
    .error {{ color: #a32323; font-weight: 600; }}
  </style>
</head>
<body>
  <header>
    <h1>Vizflow Preview</h1>
    <p>{escape(source_name)} · {len(frame):,} rows · {len(frame.columns):,} columns</p>
  </header>
  <main>
    <nav>{suggestion_links}<a href="/dashboard">Dashboard</a><a href="/schema">Schema JSON</a><a href="/data">Sample JSON</a></nav>
    {error_html}
    <section class="chart">{chart_html}</section>
  </main>
</body>
</html>
"""

    @app.get("/chart/<chart_type>")
    def chart(chart_type: str) -> str:
        try:
            fig = make_chart(frame, chart_type)
        except ChartError as exc:
            return _error_page(str(exc)), 400
        return to_html(fig, include_plotlyjs="cdn", full_html=True)

    @app.get("/dashboard")
    def dashboard() -> str:
        return build_dashboard_html(frame, None, title=f"Vizflow Dashboard - {source_name}")

    @app.get("/schema")
    def schema() -> object:
        return jsonify(schema_as_records(frame))

    @app.get("/data")
    def data() -> object:
        return jsonify(frame.head(100).where(pd.notna(frame), None).to_dict(orient="records"))

    return app


def _error_page(message: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vizflow Preview Error</title>
  <style>
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f8fb;
      color: #1c2430;
    }}
    main {{ max-width: 760px; margin: 72px auto; padding: 0 24px; }}
    .error {{
      border: 1px solid #f0b8b8;
      border-radius: 8px;
      background: #fff5f5;
      color: #8a1f1f;
      padding: 16px 18px;
      font-weight: 600;
    }}
    a {{ color: #0b63ce; text-decoration: none; font-weight: 600; }}
  </style>
</head>
<body>
  <main>
    <p class="error">{escape(message)}</p>
    <p><a href="/">Back to preview</a></p>
  </main>
</body>
</html>
"""
