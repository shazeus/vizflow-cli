from pathlib import Path

from click.testing import CliRunner

from vizflow.cli import cli


def test_schema_json_output() -> None:
    runner = CliRunner()
    csv_path = Path(__file__).resolve().parents[1] / "examples" / "sales.csv"

    result = runner.invoke(cli, ["schema", str(csv_path), "--json-output"])

    assert result.exit_code == 0
    assert '"rows"' in result.output
    assert '"schema"' in result.output
    assert '"suggested_charts"' in result.output
