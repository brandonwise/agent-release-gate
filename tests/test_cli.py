import json
from pathlib import Path
from typing import Optional

from agent_release_gate.cli import build_parser, main


def _write_run(
    history_dir: Path,
    run_id: str,
    timestamp: str,
    pass_rate: float,
    *,
    avg_latency_ms: Optional[float] = 800.0,
    p95_latency_ms: Optional[float] = 1200.0,
    avg_cost_usd: Optional[float] = 0.01,
) -> None:
    payload = {
        "run_id": run_id,
        "timestamp": timestamp,
        "summary": {
            "pass_rate": pass_rate,
            "avg_latency_ms": avg_latency_ms,
            "p95_latency_ms": p95_latency_ms,
            "avg_cost_usd": avg_cost_usd,
            "gate_passed": True,
        },
    }
    (history_dir / f"{run_id}.json").write_text(json.dumps(payload), encoding="utf-8")


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


def test_parser_trend_supports_metric_regression_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "trend",
            "--history",
            ".gate-history",
            "--fail-on-latency-regression",
            "--fail-on-p95-regression",
            "--fail-on-cost-regression",
            "--fail-on-any-regression",
        ]
    )

    assert args.fail_on_latency_regression is True
    assert args.fail_on_p95_regression is True
    assert args.fail_on_cost_regression is True
    assert args.fail_on_any_regression is True


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

    _write_run(history_dir, "run-1", "2026-04-01T00:00:00+00:00", 0.92)
    _write_run(history_dir, "run-2", "2026-04-02T00:00:00+00:00", 0.88)
    _write_run(history_dir, "run-3", "2026-04-03T00:00:00+00:00", 0.84)

    code = main(["trend", "--history", str(history_dir), "--fail-on-regression"])
    assert code == 1


def test_main_trend_fail_on_regression_only_checks_pass_rate(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    _write_run(
        history_dir,
        "run-1",
        "2026-04-01T00:00:00+00:00",
        0.90,
        avg_latency_ms=700.0,
        p95_latency_ms=1000.0,
        avg_cost_usd=0.010,
    )
    _write_run(
        history_dir,
        "run-2",
        "2026-04-02T00:00:00+00:00",
        0.92,
        avg_latency_ms=800.0,
        p95_latency_ms=1200.0,
        avg_cost_usd=0.011,
    )
    _write_run(
        history_dir,
        "run-3",
        "2026-04-03T00:00:00+00:00",
        0.94,
        avg_latency_ms=900.0,
        p95_latency_ms=1400.0,
        avg_cost_usd=0.012,
    )

    assert main(["trend", "--history", str(history_dir), "--fail-on-regression"]) == 0
    assert main(["trend", "--history", str(history_dir), "--fail-on-latency-regression"]) == 1
    assert main(["trend", "--history", str(history_dir), "--fail-on-any-regression"]) == 1


def test_main_trend_fail_on_p95_regression(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    _write_run(
        history_dir,
        "run-1",
        "2026-04-01T00:00:00+00:00",
        0.95,
        avg_latency_ms=800.0,
        p95_latency_ms=1000.0,
        avg_cost_usd=0.010,
    )
    _write_run(
        history_dir,
        "run-2",
        "2026-04-02T00:00:00+00:00",
        0.95,
        avg_latency_ms=800.0,
        p95_latency_ms=1200.0,
        avg_cost_usd=0.010,
    )
    _write_run(
        history_dir,
        "run-3",
        "2026-04-03T00:00:00+00:00",
        0.95,
        avg_latency_ms=800.0,
        p95_latency_ms=1400.0,
        avg_cost_usd=0.010,
    )

    assert main(["trend", "--history", str(history_dir), "--fail-on-p95-regression"]) == 1


def test_main_trend_fail_on_cost_regression(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    _write_run(
        history_dir,
        "run-1",
        "2026-04-01T00:00:00+00:00",
        0.95,
        avg_latency_ms=800.0,
        p95_latency_ms=1200.0,
        avg_cost_usd=0.010,
    )
    _write_run(
        history_dir,
        "run-2",
        "2026-04-02T00:00:00+00:00",
        0.95,
        avg_latency_ms=800.0,
        p95_latency_ms=1200.0,
        avg_cost_usd=0.011,
    )
    _write_run(
        history_dir,
        "run-3",
        "2026-04-03T00:00:00+00:00",
        0.95,
        avg_latency_ms=800.0,
        p95_latency_ms=1200.0,
        avg_cost_usd=0.012,
    )

    assert main(["trend", "--history", str(history_dir), "--fail-on-cost-regression"]) == 1


def test_main_trend_missing_optional_metric_history_does_not_trigger_metric_failure(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    _write_run(
        history_dir,
        "run-1",
        "2026-04-01T00:00:00+00:00",
        0.90,
        avg_latency_ms=800.0,
        p95_latency_ms=None,
        avg_cost_usd=0.010,
    )
    _write_run(
        history_dir,
        "run-2",
        "2026-04-02T00:00:00+00:00",
        0.91,
        avg_latency_ms=810.0,
        p95_latency_ms=None,
        avg_cost_usd=0.010,
    )
    _write_run(
        history_dir,
        "run-3",
        "2026-04-03T00:00:00+00:00",
        0.92,
        avg_latency_ms=820.0,
        p95_latency_ms=None,
        avg_cost_usd=0.010,
    )

    assert main(["trend", "--history", str(history_dir), "--fail-on-p95-regression"]) == 0
