import json
from pathlib import Path

from agent_release_gate.cli import build_parser, main


def test_parser_has_evaluate_command():
    parser = build_parser()
    args = parser.parse_args(["evaluate", "--spec", "a.yaml", "--results", "b.json"])
    assert args.command == "evaluate"
    assert args.spec == "a.yaml"
    assert args.results == "b.json"


def test_parser_evaluate_supports_record_history():
    parser = build_parser()
    args = parser.parse_args(
        [
            "evaluate",
            "--spec",
            "a.yaml",
            "--results",
            "b.json",
            "--record-history",
            ".gate-history",
        ]
    )

    assert args.command == "evaluate"
    assert args.record_history == ".gate-history"


def test_parser_has_trend_command():
    parser = build_parser()
    args = parser.parse_args(["trend", "--history", ".gate-history", "--window", "8"])

    assert args.command == "trend"
    assert args.history == ".gate-history"
    assert args.window == 8


def test_main_evaluate_records_history(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 0.5
cases:
  - id: case_1
    expected_all: ["refund"]
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "case_1",
                        "response": "refund approved",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    history_dir = tmp_path / "history"
    code = main(
        [
            "evaluate",
            "--spec",
            str(spec),
            "--results",
            str(results),
            "--record-history",
            str(history_dir),
        ]
    )

    assert code == 0
    assert len(list(history_dir.glob("*.json"))) == 1


def test_main_trend_fail_on_regression(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    runs = [
        ("run-1", "2026-04-01T00:00:00+00:00", 0.92),
        ("run-2", "2026-04-02T00:00:00+00:00", 0.88),
        ("run-3", "2026-04-03T00:00:00+00:00", 0.84),
    ]
    for run_id, timestamp, pass_rate in runs:
        payload = {
            "run_id": run_id,
            "timestamp": timestamp,
            "summary": {
                "pass_rate": pass_rate,
                "avg_latency_ms": 800.0,
                "avg_cost_usd": 0.01,
                "gate_passed": True,
            },
        }
        (history_dir / f"{run_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    code = main(["trend", "--history", str(history_dir), "--fail-on-regression"])
    assert code == 1
