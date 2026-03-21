from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class GateCase:
    id: str
    expected_all: list[str] = field(default_factory=list)
    expected_any: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    min_score: float = 0.7
    max_latency_ms: Optional[int] = None
    max_cost_usd: Optional[float] = None


@dataclass
class GateSpec:
    minimum_pass_rate: float = 0.8
    allowed_regression: float = 0.02
    max_avg_latency_ms: Optional[int] = None
    max_avg_cost_usd: Optional[float] = None
    cases: list[GateCase] = field(default_factory=list)


@dataclass
class CaseResult:
    id: str
    response: str
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None


@dataclass
class ScoredCase:
    id: str
    score: float
    passed: bool
    notes: list[str]


@dataclass
class GateSummary:
    total_cases: int
    passed_cases: int
    pass_rate: float
    avg_latency_ms: Optional[float]
    avg_cost_usd: Optional[float]
    gate_passed: bool
    gate_reasons: list[str]


@dataclass
class GateReport:
    summary: GateSummary
    cases: list[ScoredCase]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def parse_spec(data: dict[str, Any]) -> GateSpec:
    global_cfg = data.get("global", {}) or {}
    raw_cases = data.get("cases", []) or []
    cases = [
        GateCase(
            id=str(c["id"]),
            expected_all=_as_list(c.get("expected_all")),
            expected_any=_as_list(c.get("expected_any")),
            forbidden=_as_list(c.get("forbidden")),
            min_score=float(c.get("min_score", 0.7)),
            max_latency_ms=(
                int(c["max_latency_ms"]) if c.get("max_latency_ms") is not None else None
            ),
            max_cost_usd=(
                float(c["max_cost_usd"]) if c.get("max_cost_usd") is not None else None
            ),
        )
        for c in raw_cases
    ]

    return GateSpec(
        minimum_pass_rate=float(global_cfg.get("minimum_pass_rate", 0.8)),
        allowed_regression=float(global_cfg.get("allowed_regression", 0.02)),
        max_avg_latency_ms=(
            int(global_cfg["max_avg_latency_ms"])
            if global_cfg.get("max_avg_latency_ms") is not None
            else None
        ),
        max_avg_cost_usd=(
            float(global_cfg["max_avg_cost_usd"])
            if global_cfg.get("max_avg_cost_usd") is not None
            else None
        ),
        cases=cases,
    )


def parse_results(data: dict[str, Any]) -> list[CaseResult]:
    raw_cases = data.get("cases", []) or []
    return [
        CaseResult(
            id=str(c["id"]),
            response=str(c.get("response", "")),
            latency_ms=(int(c["latency_ms"]) if c.get("latency_ms") is not None else None),
            cost_usd=(float(c["cost_usd"]) if c.get("cost_usd") is not None else None),
        )
        for c in raw_cases
    ]
