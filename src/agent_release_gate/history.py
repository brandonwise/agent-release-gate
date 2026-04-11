from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from .models import GateReport


@dataclass
class GateRunSummary:
    run_id: str
    timestamp: str
    pass_rate: float
    avg_latency_ms: Optional[float]
    avg_cost_usd: Optional[float]
    gate_passed: bool


@dataclass
class GateTrendReport:
    window: int
    runs: list[GateRunSummary]
    pass_rate_slope: float
    pass_rate_direction: str
    any_regression: bool


def _timestamp_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_payload(run: GateRunSummary) -> dict:
    return {
        "run_id": run.run_id,
        "timestamp": run.timestamp,
        "summary": {
            "pass_rate": run.pass_rate,
            "avg_latency_ms": run.avg_latency_ms,
            "avg_cost_usd": run.avg_cost_usd,
            "gate_passed": run.gate_passed,
        },
    }


def _run_from_payload(data: dict, fallback_run_id: str) -> GateRunSummary:
    summary = data.get("summary", data) or {}
    return GateRunSummary(
        run_id=str(data.get("run_id") or fallback_run_id),
        timestamp=str(data.get("timestamp") or ""),
        pass_rate=float(summary.get("pass_rate", 0.0)),
        avg_latency_ms=(
            float(summary["avg_latency_ms"])
            if summary.get("avg_latency_ms") is not None
            else None
        ),
        avg_cost_usd=(
            float(summary["avg_cost_usd"])
            if summary.get("avg_cost_usd") is not None
            else None
        ),
        gate_passed=bool(summary.get("gate_passed", False)),
    )


def _sort_key(run: GateRunSummary) -> tuple[str, str]:
    return (run.timestamp, run.run_id)


def _ols_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0

    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    denominator = sum((x - x_mean) ** 2 for x in range(n))
    if denominator == 0:
        return 0.0

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in enumerate(values))
    return numerator / denominator


def summary_from_report(report: GateReport, run_id: Optional[str] = None) -> GateRunSummary:
    return GateRunSummary(
        run_id=run_id or _timestamp_id(),
        timestamp=_iso_utc_now(),
        pass_rate=report.summary.pass_rate,
        avg_latency_ms=report.summary.avg_latency_ms,
        avg_cost_usd=report.summary.avg_cost_usd,
        gate_passed=report.summary.gate_passed,
    )


def record_history(
    report: GateReport,
    history_dir: Union[str, Path],
    run_id: Optional[str] = None,
) -> Path:
    run = summary_from_report(report=report, run_id=run_id)
    history_path = Path(history_dir)
    history_path.mkdir(parents=True, exist_ok=True)

    file_path = history_path / f"{run.run_id}.json"
    if file_path.exists():
        file_path = history_path / f"{run.run_id}-{int(datetime.now(timezone.utc).timestamp())}.json"

    file_path.write_text(json.dumps(_run_payload(run), indent=2), encoding="utf-8")
    return file_path


def load_recent_runs(history_dir: Union[str, Path], window: int = 10) -> list[GateRunSummary]:
    history_path = Path(history_dir)
    if not history_path.exists():
        return []

    runs: list[GateRunSummary] = []
    for file_path in history_path.glob("*.json"):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        runs.append(_run_from_payload(data, fallback_run_id=file_path.stem))

    runs.sort(key=_sort_key)
    if window > 0:
        return runs[-window:]
    return runs


def analyze_history(history_dir: Union[str, Path], window: int = 10) -> GateTrendReport:
    runs = load_recent_runs(history_dir=history_dir, window=window)
    slope = _ols_slope([r.pass_rate for r in runs]) if len(runs) >= 3 else 0.0

    if slope < -0.001:
        direction = "declining"
    elif slope > 0.001:
        direction = "improving"
    else:
        direction = "stable"

    return GateTrendReport(
        window=window,
        runs=runs,
        pass_rate_slope=round(slope, 6),
        pass_rate_direction=direction,
        any_regression=direction == "declining",
    )


def trend_to_dict(report: GateTrendReport) -> dict:
    return {
        "window": report.window,
        "runs": [
            {
                "run_id": run.run_id,
                "timestamp": run.timestamp,
                "pass_rate": run.pass_rate,
                "avg_latency_ms": run.avg_latency_ms,
                "avg_cost_usd": run.avg_cost_usd,
                "gate_passed": run.gate_passed,
            }
            for run in report.runs
        ],
        "pass_rate_slope": report.pass_rate_slope,
        "pass_rate_direction": report.pass_rate_direction,
        "any_regression": report.any_regression,
    }
