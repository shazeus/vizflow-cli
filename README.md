<p align="center">
  <h1 align="center">Vizflow</h1>
  <p align="center">A data visualization pipeline tool for fast schema inspection, charting, dashboards, and export.</p>
  <p align="center">
    <a href="https://pypi.org/project/vizflow-cli/"><img src="https://img.shields.io/pypi/v/vizflow-cli?color=blue&label=PyPI" alt="PyPI"></a>
    <a href="https://pypi.org/project/vizflow-cli/"><img src="https://img.shields.io/pypi/pyversions/vizflow-cli" alt="Python"></a>
    <a href="https://github.com/shazeus/vizflow-cli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/shazeus/vizflow-cli" alt="License"></a>
    <a href="https://github.com/shazeus/vizflow-cli/stargazers"><img src="https://img.shields.io/github/stars/shazeus/vizflow-cli?style=social" alt="Stars"></a>
  </p>
</p>

---

Vizflow turns raw CSV, JSON, Parquet, SQLite, SQL script, and piped stdin data into useful visual outputs without writing boilerplate notebooks. It profiles column types, recommends chart families, generates Plotly-powered interactive charts, serves local browser previews, combines charts into dashboards, converts datasets between common formats, and produces comparison reports for changing data files.

- **Automatic schema inspection** — detect semantic column types, null counts, unique values, samples, and numeric/date statistics.
- **Smart chart suggestions** — recommend line, bar, scatter, pie, heatmap, treemap, and histogram views from the data shape.
- **Interactive Plotly charts** — generate browser-ready HTML or static PNG/SVG/PDF exports.
- **Dashboard mode** — combine multiple chart specs into a responsive standalone HTML page.
- **Local preview server** — launch a Flask web server for chart, schema, and sample-data browsing on localhost.
- **Data conversion and comparison** — convert CSV/JSON/Parquet inputs and compare two datasets visually.
- **Pipe support** — stream CSV or JSON directly into commands with `cat data.csv | vizflow plot`.

## Installation

```bash
pip install vizflow-cli
```

For local development:

```bash
git clone https://github.com/shazeus/vizflow-cli.git
cd vizflow-cli
pip install -e .
```

## Usage

Inspect a dataset:

```bash
vizflow schema examples/sales.csv
```

Create an auto-selected chart:

```bash
vizflow plot examples/sales.csv --output sales-chart.html
```

Create a specific chart:

```bash
vizflow plot examples/sales.csv --type line --x date --y revenue --color region
```

Build a dashboard:

```bash
vizflow dashboard examples/sales.csv --charts "bar:region:revenue,line:date:revenue,pie:category:revenue"
```

Convert a file:

```bash
vizflow convert examples/sales.csv --to json --output sales.json
```

Preview in a browser:

```bash
vizflow serve examples/sales.csv --port 5050
```

Use stdin:

```bash
cat examples/sales.csv | vizflow plot --type bar --x region --y revenue --output piped.html
```

## Commands

| Command | Description | Example |
| --- | --- | --- |
| `vizflow plot <file>` | Generate a single interactive chart. Omit `<file>` to read stdin. | `vizflow plot data.csv --type scatter --x price --y volume` |
| `vizflow dashboard <file>` | Combine multiple charts into one standalone HTML page. | `vizflow dashboard data.csv --charts "bar:team,line:date:sales"` |
| `vizflow schema <file>` | Inspect data types, nulls, unique values, stats, and chart suggestions. | `vizflow schema data.json` |
| `vizflow convert <file>` | Convert datasets between CSV, JSON, and Parquet. | `vizflow convert data.csv --to parquet` |
| `vizflow serve <file>` | Start a Flask preview server with chart and schema endpoints. | `vizflow serve data.sqlite --table events` |
| `vizflow export <file>` | Export a chart as PNG, SVG, HTML, or PDF. | `vizflow export data.csv --format svg --type bar` |
| `vizflow compare <file1> <file2>` | Compare two datasets and write an HTML report. | `vizflow compare before.csv after.csv` |

## Configuration

Vizflow is intentionally CLI-first and does not require a config file. Common options are available directly on commands:

| Option | Purpose |
| --- | --- |
| `--type` | Choose `auto`, `bar`, `line`, `scatter`, `pie`, `heatmap`, `treemap`, or `histogram`. |
| `--x`, `--y`, `--color` | Override inferred chart columns. |
| `--query` | Run a SQL query against SQLite database or SQL script inputs. |
| `--table` | Select a table from SQLite database or SQL script inputs. |
| `--output` | Set the generated file path. |
| `--format` | Choose export format for chart output. |

Static image export uses Plotly's Kaleido engine when available. If the local browser runtime is unavailable, Vizflow falls back to a Matplotlib renderer for PNG, SVG, and PDF outputs.

## License

MIT License. See [LICENSE](LICENSE).
