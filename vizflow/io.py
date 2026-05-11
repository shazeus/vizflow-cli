"""Data loading and conversion helpers for Vizflow."""

from __future__ import annotations

import io
import sqlite3
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


class DataLoadError(RuntimeError):
    """Raised when Vizflow cannot read a dataset."""


def _normalize_frame(value: pd.DataFrame | pd.Series, source: str) -> pd.DataFrame:
    if isinstance(value, pd.Series):
        value = value.to_frame(name=value.name or "value")
    if not isinstance(value, pd.DataFrame):
        raise DataLoadError(f"{source} did not produce a tabular dataset.")
    if value.empty and len(value.columns) == 0:
        raise DataLoadError(f"{source} contains no columns.")
    return value


def _read_json_buffer(buffer: io.StringIO, source: str, prefer_lines: bool = False) -> pd.DataFrame:
    attempts: Iterable[bool] = (True, False) if prefer_lines else (False, True)
    last_error: Exception | None = None
    for lines in attempts:
        buffer.seek(0)
        try:
            return _normalize_frame(pd.read_json(buffer, lines=lines), source)
        except ValueError as exc:
            last_error = exc
    raise DataLoadError(f"Could not parse JSON from {source}: {last_error}") from last_error


def _read_text_buffer(text: str, source: str) -> pd.DataFrame:
    stripped = text.lstrip()
    if not stripped:
        raise DataLoadError(f"{source} is empty.")

    if stripped[0] in "[{":
        return _read_json_buffer(io.StringIO(text), source)

    try:
        return _normalize_frame(pd.read_csv(io.StringIO(text)), source)
    except Exception as csv_error:
        try:
            return _read_json_buffer(io.StringIO(text), source, prefer_lines=True)
        except Exception as json_error:
            raise DataLoadError(
                f"Could not parse stdin as CSV or JSON: CSV={csv_error}; JSON={json_error}"
            ) from json_error


def read_stdin() -> pd.DataFrame:
    """Read CSV or JSON data from stdin."""

    if sys.stdin.isatty():
        raise DataLoadError("No input file was provided and stdin is empty.")
    return _read_text_buffer(sys.stdin.read(), "stdin")


def _first_table(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"
    ).fetchall()
    if not rows:
        raise DataLoadError("No tables were found in the SQL source.")
    return str(rows[0][0])


def _read_sqlite_database(path: Path, query: str | None = None, table: str | None = None) -> pd.DataFrame:
    try:
        with sqlite3.connect(path) as conn:
            if query:
                frame = pd.read_sql_query(query, conn)
            else:
                selected = table or _first_table(conn)
                frame = pd.read_sql_query(f'select * from "{selected}"', conn)
    except sqlite3.Error as exc:
        raise DataLoadError(f"Could not read SQLite database {path}: {exc}") from exc
    return _normalize_frame(frame, str(path))


def _read_sql_script(path: Path, query: str | None = None, table: str | None = None) -> pd.DataFrame:
    try:
        script = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        script = path.read_text()

    try:
        with sqlite3.connect(":memory:") as conn:
            conn.executescript(script)
            if query:
                frame = pd.read_sql_query(query, conn)
            else:
                selected = table or _first_table(conn)
                frame = pd.read_sql_query(f'select * from "{selected}"', conn)
    except sqlite3.Error as exc:
        raise DataLoadError(f"Could not execute SQL script {path}: {exc}") from exc
    return _normalize_frame(frame, str(path))


def read_data(
    file_path: str | None,
    *,
    query: str | None = None,
    table: str | None = None,
) -> pd.DataFrame:
    """Read a dataset from CSV, JSON, Parquet, SQLite, SQL script, or stdin."""

    if not file_path or file_path == "-":
        return read_stdin()

    path = Path(file_path).expanduser()
    if not path.exists():
        raise DataLoadError(f"File not found: {path}")
    if not path.is_file():
        raise DataLoadError(f"Expected a file, got: {path}")

    suffix = path.suffix.lower()
    try:
        if suffix in {".csv", ".txt"}:
            return _normalize_frame(pd.read_csv(path), str(path))
        if suffix in {".tsv", ".tab"}:
            return _normalize_frame(pd.read_csv(path, sep="\t"), str(path))
        if suffix == ".jsonl":
            return _normalize_frame(pd.read_json(path, lines=True), str(path))
        if suffix == ".json":
            try:
                return _normalize_frame(pd.read_json(path), str(path))
            except ValueError:
                return _normalize_frame(pd.read_json(path, lines=True), str(path))
        if suffix == ".parquet":
            return _normalize_frame(pd.read_parquet(path), str(path))
        if suffix in {".db", ".sqlite", ".sqlite3"}:
            return _read_sqlite_database(path, query=query, table=table)
        if suffix == ".sql":
            return _read_sql_script(path, query=query, table=table)
    except DataLoadError:
        raise
    except Exception as exc:
        raise DataLoadError(f"Could not read {path}: {exc}") from exc

    raw = path.read_text(encoding="utf-8", errors="replace")
    return _read_text_buffer(raw, str(path))


def infer_format(path: str | Path, explicit: str | None = None) -> str:
    """Infer a supported output format from a path or explicit option."""

    if explicit:
        return explicit.lower()
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in {"csv", "json", "parquet"}:
        return suffix
    raise DataLoadError("Could not infer output format; pass --to explicitly.")


def default_output_path(file_path: str | None, suffix: str, stem_extra: str | None = None) -> Path:
    """Build a stable default output path for a command."""

    if file_path and file_path != "-":
        source = Path(file_path)
        stem = source.stem
        directory = source.parent
    else:
        stem = "vizflow"
        directory = Path.cwd()

    if stem_extra:
        stem = f"{stem}-{stem_extra}"
    return directory / f"{stem}.{suffix.lstrip('.')}"


def write_data(frame: pd.DataFrame, output: str | Path, output_format: str) -> Path:
    """Write a dataframe to CSV, JSON, or Parquet."""

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = output_format.lower()
    try:
        if fmt == "csv":
            frame.to_csv(path, index=False)
        elif fmt == "json":
            frame.to_json(path, orient="records", indent=2)
        elif fmt == "parquet":
            frame.to_parquet(path, index=False)
        else:
            raise DataLoadError(f"Unsupported output format: {output_format}")
    except DataLoadError:
        raise
    except Exception as exc:
        raise DataLoadError(f"Could not write {path}: {exc}") from exc
    return path

