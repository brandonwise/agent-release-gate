import json
from pathlib import Path

from agent_release_gate.history import analyze_history, record_history
from agent_release_gate.models import GateReport, GateSummary, ScoredCase


def _report(pass_rate: float, gate_passed: bool = True) -> GateReport:
    return GateReport(
        summary=GateSummary(
            total_cases=10,
            passed_cases=int(pass_rate * 10),
            pass_rate=pass_rate,
            avg_latency_ms=850.0,
            avg_cost_usd=0.011,
            gate_passed=gate_passed,
            gate_reasons=["ok"],
        ),
        cases=[ScoredCase(id="case_1", score=0.9, passed=gate_passed, notes=["ok"])],
    )


def _write_run(history_dir: Path, run_id: str, timestamp: str, pass_rate: float) -> None:
    payload = {
        "run_id": run_id,
        "timestamp": timestamp,
        "summary": {
            "pass_rate": pass_rate,
            "avg_latency_ms": 800.0,
            "avg_cost_usd": 0.01,
            "gate_passed": pass_rate >= 0.8,
        },
    }
    (history_dir / f"{run_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_record_history_writes_run_summary(tmp_path: Path):
    history_dir = tmp_path / "history"
    path = record_history(_report(0.9), history_dir=history_dir, run_id="run-001")

    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-001"
    assert payload["summary"]["pass_rate"] == 0.9


def test_analyze_history_detects_declining_trend(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    _write_run(history_dir, "run-1", "2026-04-01T00:00:00+00:00", 0.92)
    _write_run(history_dir, "run-2", "2026-04-02T00:00:00+00:00", 0.89)
    _write_run(history_dir, "run-3", "2026-04-03T00:00:00+00:00", 0.86)
    _write_run(history_dir, "run-4", "2026-04-04T00:00:00+00:00", 0.83)
    _write_run(history_dir, "run-5", "2026-04-05T00:00:00+00:00", 0.80)

    trend = analyze_history(history_dir=history_dir, window=10)

    assert trend.pass_rate_direction == "declining"
    assert trend.any_regression is True
    assert trend.pass_rate_slope < 0


def test_analyze_history_window_uses_most_recent_runs(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    _write_run(history_dir, "run-1", "2026-04-01T00:00:00+00:00", 0.90)
    _write_run(history_dir, "run-2", "2026-04-02T00:00:00+00:00", 0.85)
    _write_run(history_dir, "run-3", "2026-04-03T00:00:00+00:00", 0.80)
    _write_run(history_dir, "run-4", "2026-04-04T00:00:00+00:00", 0.93)
    _write_run(history_dir, "run-5", "2026-04-05T00:00:00+00:00", 0.95)
    _write_run(history_dir, "run-6", "2026-04-06T00:00:00+00:00", 0.97)

    trend = analyze_history(history_dir=history_dir, window=3)

    assert len(trend.runs) == 3
    assert trend.runs[0].run_id == "run-4"
    assert trend.pass_rate_direction == "improving"
