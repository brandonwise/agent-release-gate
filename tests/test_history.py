import json
from pathlib import Path
from typing import Optional

from agent_release_gate.history import analyze_history, record_history, trend_to_dict
from agent_release_gate.models import GateReport, GateSummary, ScoredCase


def _report(
    pass_rate: float,
    gate_passed: bool = True,
    *,
    avg_latency_ms: float = 850.0,
    p95_latency_ms: float = 1100.0,
    avg_cost_usd: float = 0.011,
) -> GateReport:
    return GateReport(
        summary=GateSummary(
            total_cases=10,
            passed_cases=int(pass_rate * 10),
            pass_rate=pass_rate,
            avg_latency_ms=avg_latency_ms,
            avg_cost_usd=avg_cost_usd,
            gate_passed=gate_passed,
            gate_reasons=["ok"],
            p95_latency_ms=p95_latency_ms,
        ),
        cases=[ScoredCase(id="case_1", score=0.9, passed=gate_passed, notes=["ok"])],
    )


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
            "avg_latency_ms": 800.0,
            "gate_passed": pass_rate >= 0.8,
        },
    }
    payload["summary"]["avg_latency_ms"] = avg_latency_ms
    payload["summary"]["p95_latency_ms"] = p95_latency_ms
    payload["summary"]["avg_cost_usd"] = avg_cost_usd
    (history_dir / f"{run_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_record_history_writes_run_summary(tmp_path: Path):
    history_dir = tmp_path / "history"
    path = record_history(_report(0.9), history_dir=history_dir, run_id="run-001")

    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-001"
    assert payload["summary"]["pass_rate"] == 0.9
    assert payload["summary"]["p95_latency_ms"] == 1100.0


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
    assert trend.pass_rate_regression is True
    assert trend.any_regression is True
    assert trend.any_trend_regression is True
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


def test_analyze_history_detects_latency_p95_and_cost_regressions(tmp_path: Path):
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
        0.96,
        avg_latency_ms=850.0,
        p95_latency_ms=1400.0,
        avg_cost_usd=0.011,
    )
    _write_run(
        history_dir,
        "run-3",
        "2026-04-03T00:00:00+00:00",
        0.97,
        avg_latency_ms=900.0,
        p95_latency_ms=1600.0,
        avg_cost_usd=0.012,
    )

    trend = analyze_history(history_dir=history_dir, window=10)
    payload = trend_to_dict(trend)

    assert trend.pass_rate_direction == "improving"
    assert trend.pass_rate_regression is False
    assert trend.avg_latency_ms_direction == "increasing"
    assert trend.avg_latency_regression is True
    assert trend.avg_latency_ms_slope and trend.avg_latency_ms_slope > 0
    assert trend.p95_latency_ms_direction == "increasing"
    assert trend.p95_latency_regression is True
    assert trend.p95_latency_ms_slope and trend.p95_latency_ms_slope > 0
    assert trend.avg_cost_usd_direction == "increasing"
    assert trend.avg_cost_regression is True
    assert trend.avg_cost_usd_slope and trend.avg_cost_usd_slope > 0
    assert trend.any_regression is False
    assert trend.any_trend_regression is True
    assert payload["runs"][0]["p95_latency_ms"] == 1200.0
    assert payload["avg_latency_regression"] is True
    assert payload["p95_latency_regression"] is True
    assert payload["avg_cost_regression"] is True
    assert payload["any_trend_regression"] is True


def test_analyze_history_tolerates_older_history_without_optional_metrics(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    legacy_payload = {
        "run_id": "run-1",
        "timestamp": "2026-04-01T00:00:00+00:00",
        "summary": {
            "pass_rate": 0.90,
            "avg_latency_ms": 780.0,
            "gate_passed": True,
        },
    }
    (history_dir / "run-1.json").write_text(json.dumps(legacy_payload), encoding="utf-8")

    _write_run(
        history_dir,
        "run-2",
        "2026-04-02T00:00:00+00:00",
        0.91,
        avg_latency_ms=800.0,
        p95_latency_ms=1200.0,
        avg_cost_usd=None,
    )
    _write_run(
        history_dir,
        "run-3",
        "2026-04-03T00:00:00+00:00",
        0.92,
        avg_latency_ms=820.0,
        p95_latency_ms=1300.0,
        avg_cost_usd=None,
    )
    _write_run(
        history_dir,
        "run-4",
        "2026-04-04T00:00:00+00:00",
        0.93,
        avg_latency_ms=840.0,
        p95_latency_ms=1400.0,
        avg_cost_usd=None,
    )

    trend = analyze_history(history_dir=history_dir, window=10)

    assert trend.p95_latency_ms_direction == "increasing"
    assert trend.p95_latency_regression is True
    assert trend.avg_cost_usd_slope is None
    assert trend.avg_cost_usd_direction == "insufficient_data"
    assert trend.avg_cost_regression is False


def test_analyze_history_ignores_non_run_json_files(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    _write_run(history_dir, "run-1", "2026-04-01T00:00:00+00:00", 0.91)
    _write_run(history_dir, "run-2", "2026-04-02T00:00:00+00:00", 0.92)
    _write_run(history_dir, "run-3", "2026-04-03T00:00:00+00:00", 0.93)

    (history_dir / "trend-report.json").write_text(
        json.dumps({"window": 10, "runs": []}),
        encoding="utf-8",
    )
    (history_dir / "incomplete.json").write_text("", encoding="utf-8")

    trend = analyze_history(history_dir=history_dir, window=10)

    assert len(trend.runs) == 3
    assert [run.run_id for run in trend.runs] == ["run-1", "run-2", "run-3"]
    assert trend.pass_rate_direction == "improving"
