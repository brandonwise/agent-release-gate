from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from .models import GateReport

MIN_TREND_POINTS = 3
PASS_RATE_TREND_EPSILON = 0.001
LATENCY_TREND_EPSILON_MS = 1.0
COST_TREND_EPSILON_USD = 0.000001


@dataclass
class GateRunSummary:
    run_id: str
    timestamp: str
    pass_rate: float
    avg_latency_ms: Optional[float]
    p95_latency_ms: Optional[float]
    avg_cost_usd: Optional[float]
    gate_passed: bool


@dataclass
class MetricTrend:
    slope: Optional[float]
    direction: str
    regression: bool


@dataclass
class GateTrendReport:
    window: int
    runs: list[GateRunSummary]
    pass_rate_slope: float
    pass_rate_direction: str
    pass_rate_regression: bool
    avg_latency_ms_slope: Optional[float]
    avg_latency_ms_direction: str
    avg_latency_regression: bool
    p95_latency_ms_slope: Optional[float]
    p95_latency_ms_direction: str
    p95_latency_regression: bool
    avg_cost_usd_slope: Optional[float]
    avg_cost_usd_direction: str
    avg_cost_regression: bool
    any_regression: bool
    any_trend_regression: bool


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
            "p95_latency_ms": run.p95_latency_ms,
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
        p95_latency_ms=(
            float(summary["p95_latency_ms"])
            if summary.get("p95_latency_ms") is not None
            else None
        ),
        avg_cost_usd=(
            float(summary["avg_cost_usd"])
            if summary.get("avg_cost_usd") is not None
            else None
        ),
        gate_passed=bool(summary.get("gate_passed", False)),
    )


def _looks_like_run_payload(data: dict) -> bool:
    summary = data.get("summary")
    if isinstance(summary, dict) and summary.get("pass_rate") is not None:
        return True

    return data.get("pass_rate") is not None


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


def _trend_direction(
    slope: float,
    *,
    positive_direction: str,
    negative_direction: str,
    epsilon: float,
) -> str:
    if slope > epsilon:
        return positive_direction
    if slope < -epsilon:
        return negative_direction
    return "stable"


def _available_metric_values(runs: list[GateRunSummary], field_name: str) -> list[float]:
    values: list[float] = []
    for run in runs:
        value = getattr(run, field_name)
        if value is not None:
            values.append(float(value))
    return values


def _analyze_optional_metric(
    values: list[float],
    *,
    epsilon: float,
    positive_direction: str,
    negative_direction: str,
    regression_direction: str,
) -> MetricTrend:
    if len(values) < MIN_TREND_POINTS:
        return MetricTrend(
            slope=None,
            direction="insufficient_data",
            regression=False,
        )

    slope = _ols_slope(values)
    direction = _trend_direction(
        slope,
        positive_direction=positive_direction,
        negative_direction=negative_direction,
        epsilon=epsilon,
    )
    return MetricTrend(
        slope=round(slope, 6),
        direction=direction,
        regression=direction == regression_direction,
    )


def summary_from_report(report: GateReport, run_id: Optional[str] = None) -> GateRunSummary:
    return GateRunSummary(
        run_id=run_id or _timestamp_id(),
        timestamp=_iso_utc_now(),
        pass_rate=report.summary.pass_rate,
        avg_latency_ms=report.summary.avg_latency_ms,
        p95_latency_ms=report.summary.p95_latency_ms,
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
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        if not isinstance(data, dict) or not _looks_like_run_payload(data):
            continue

        runs.append(_run_from_payload(data, fallback_run_id=file_path.stem))

    runs.sort(key=_sort_key)
    if window > 0:
        return runs[-window:]
    return runs


def analyze_history(history_dir: Union[str, Path], window: int = 10) -> GateTrendReport:
    runs = load_recent_runs(history_dir=history_dir, window=window)
    pass_rate_trend = _analyze_optional_metric(
        [r.pass_rate for r in runs],
        epsilon=PASS_RATE_TREND_EPSILON,
        positive_direction="improving",
        negative_direction="declining",
        regression_direction="declining",
    )
    avg_latency_trend = _analyze_optional_metric(
        _available_metric_values(runs, "avg_latency_ms"),
        epsilon=LATENCY_TREND_EPSILON_MS,
        positive_direction="increasing",
        negative_direction="decreasing",
        regression_direction="increasing",
    )
    p95_latency_trend = _analyze_optional_metric(
        _available_metric_values(runs, "p95_latency_ms"),
        epsilon=LATENCY_TREND_EPSILON_MS,
        positive_direction="increasing",
        negative_direction="decreasing",
        regression_direction="increasing",
    )
    avg_cost_trend = _analyze_optional_metric(
        _available_metric_values(runs, "avg_cost_usd"),
        epsilon=COST_TREND_EPSILON_USD,
        positive_direction="increasing",
        negative_direction="decreasing",
        regression_direction="increasing",
    )
    pass_rate_regression = pass_rate_trend.regression
    any_trend_regression = any(
        (
            pass_rate_regression,
            avg_latency_trend.regression,
            p95_latency_trend.regression,
            avg_cost_trend.regression,
        )
    )

    return GateTrendReport(
        window=window,
        runs=runs,
        pass_rate_slope=pass_rate_trend.slope or 0.0,
        pass_rate_direction=pass_rate_trend.direction
        if pass_rate_trend.slope is not None
        else "stable",
        pass_rate_regression=pass_rate_regression,
        avg_latency_ms_slope=avg_latency_trend.slope,
        avg_latency_ms_direction=avg_latency_trend.direction,
        avg_latency_regression=avg_latency_trend.regression,
        p95_latency_ms_slope=p95_latency_trend.slope,
        p95_latency_ms_direction=p95_latency_trend.direction,
        p95_latency_regression=p95_latency_trend.regression,
        avg_cost_usd_slope=avg_cost_trend.slope,
        avg_cost_usd_direction=avg_cost_trend.direction,
        avg_cost_regression=avg_cost_trend.regression,
        any_regression=pass_rate_regression,
        any_trend_regression=any_trend_regression,
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
                "p95_latency_ms": run.p95_latency_ms,
                "avg_cost_usd": run.avg_cost_usd,
                "gate_passed": run.gate_passed,
            }
            for run in report.runs
        ],
        "pass_rate_slope": report.pass_rate_slope,
        "pass_rate_direction": report.pass_rate_direction,
        "pass_rate_regression": report.pass_rate_regression,
        "avg_latency_ms_slope": report.avg_latency_ms_slope,
        "avg_latency_ms_direction": report.avg_latency_ms_direction,
        "avg_latency_regression": report.avg_latency_regression,
        "p95_latency_ms_slope": report.p95_latency_ms_slope,
        "p95_latency_ms_direction": report.p95_latency_ms_direction,
        "p95_latency_regression": report.p95_latency_regression,
        "avg_cost_usd_slope": report.avg_cost_usd_slope,
        "avg_cost_usd_direction": report.avg_cost_usd_direction,
        "avg_cost_regression": report.avg_cost_regression,
        "any_regression": report.any_regression,
        "any_trend_regression": report.any_trend_regression,
    }
