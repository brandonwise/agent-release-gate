from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

import yaml

from .models import (
    CaseResult,
    GateCase,
    GateReport,
    GateSummary,
    ScoredCase,
    parse_results,
    parse_spec,
)


def load_yaml(path: Union[str, Path]) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(path: Union[str, Path]) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def score_case(case: GateCase, result: CaseResult) -> ScoredCase:
    response = normalize(result.response)
    notes: list[str] = []
    score = 0.0

    # expected_all: 0.6 total weight
    if case.expected_all:
        per_term = 0.6 / len(case.expected_all)
        for term in case.expected_all:
            t = normalize(term)
            if t in response:
                score += per_term
            else:
                notes.append(f"Missing expected_all term: '{term}'")
    else:
        score += 0.6

    # expected_any: 0.25 weight if any term matches
    if case.expected_any:
        if any(normalize(term) in response for term in case.expected_any):
            score += 0.25
        else:
            notes.append("No expected_any terms found")
    else:
        score += 0.25

    # forbidden: -0.2 each (up to -0.6)
    forbidden_hits = 0
    for term in case.forbidden:
        t = normalize(term)
        if t in response:
            forbidden_hits += 1
            notes.append(f"Forbidden term detected: '{term}'")
    score -= min(0.2 * forbidden_hits, 0.6)

    # floor and clamp
    score = max(0.0, min(score, 1.0))
    passed = score >= case.min_score and forbidden_hits == 0

    if passed and not notes:
        notes.append("Looks good")

    return ScoredCase(id=case.id, score=round(score, 4), passed=passed, notes=notes)


def evaluate(
    spec_path: Union[str, Path],
    results_path: Union[str, Path],
    baseline_path: Optional[Union[str, Path]] = None,
) -> GateReport:
    spec = parse_spec(load_yaml(spec_path))
    results = parse_results(load_json(results_path))
    result_map = {r.id: r for r in results}

    scored: list[ScoredCase] = []
    for case in spec.cases:
        case_result = result_map.get(case.id)
        if not case_result:
            scored.append(
                ScoredCase(
                    id=case.id,
                    score=0.0,
                    passed=False,
                    notes=["Missing case result"],
                )
            )
            continue
        scored.append(score_case(case, case_result))

    total = len(scored)
    passed = sum(1 for c in scored if c.passed)
    pass_rate = (passed / total) if total else 0.0

    latencies = [r.latency_ms for r in results if r.latency_ms is not None]
    costs = [r.cost_usd for r in results if r.cost_usd is not None]
    avg_latency = (sum(latencies) / len(latencies)) if latencies else None
    avg_cost = (sum(costs) / len(costs)) if costs else None

    reasons: list[str] = []
    gate_passed = True

    if pass_rate < spec.minimum_pass_rate:
        gate_passed = False
        reasons.append(
            f"Pass rate {pass_rate:.2%} is below minimum {spec.minimum_pass_rate:.2%}"
        )

    if spec.max_avg_latency_ms is not None and avg_latency is not None and avg_latency > spec.max_avg_latency_ms:
        gate_passed = False
        reasons.append(
            f"Average latency {avg_latency:.1f}ms exceeds limit {spec.max_avg_latency_ms}ms"
        )

    if spec.max_avg_cost_usd is not None and avg_cost is not None and avg_cost > spec.max_avg_cost_usd:
        gate_passed = False
        reasons.append(
            f"Average cost ${avg_cost:.4f} exceeds limit ${spec.max_avg_cost_usd:.4f}"
        )

    if baseline_path:
        baseline = load_json(baseline_path)
        baseline_pass_rate = float(baseline.get("summary", {}).get("pass_rate", 0.0))
        if pass_rate < (baseline_pass_rate - spec.allowed_regression):
            gate_passed = False
            reasons.append(
                f"Regression detected: current {pass_rate:.2%}, baseline {baseline_pass_rate:.2%}, allowed drop {spec.allowed_regression:.2%}"
            )

    if gate_passed:
        reasons.append("Gate passed")

    summary = GateSummary(
        total_cases=total,
        passed_cases=passed,
        pass_rate=round(pass_rate, 4),
        avg_latency_ms=round(avg_latency, 2) if avg_latency is not None else None,
        avg_cost_usd=round(avg_cost, 6) if avg_cost is not None else None,
        gate_passed=gate_passed,
        gate_reasons=reasons,
    )

    return GateReport(summary=summary, cases=scored)


def to_dict(report: GateReport) -> dict:
    return {
        "summary": {
            "total_cases": report.summary.total_cases,
            "passed_cases": report.summary.passed_cases,
            "pass_rate": report.summary.pass_rate,
            "avg_latency_ms": report.summary.avg_latency_ms,
            "avg_cost_usd": report.summary.avg_cost_usd,
            "gate_passed": report.summary.gate_passed,
            "gate_reasons": report.summary.gate_reasons,
        },
        "cases": [
            {"id": c.id, "score": c.score, "passed": c.passed, "notes": c.notes}
            for c in report.cases
        ],
    }


def to_markdown(report: GateReport) -> str:
    s = report.summary
    lines = [
        "# Agent Release Gate Report",
        "",
        f"- Gate passed: {'✅' if s.gate_passed else '❌'}",
        f"- Pass rate: {s.pass_rate:.2%} ({s.passed_cases}/{s.total_cases})",
    ]
    if s.avg_latency_ms is not None:
        lines.append(f"- Avg latency: {s.avg_latency_ms:.2f}ms")
    if s.avg_cost_usd is not None:
        lines.append(f"- Avg cost: ${s.avg_cost_usd:.6f}")

    lines.extend(["", "## Gate reasons"])
    for reason in s.gate_reasons:
        lines.append(f"- {reason}")

    lines.extend(["", "## Case details", ""])
    for c in report.cases:
        lines.append(f"### {c.id} {'✅' if c.passed else '❌'}")
        lines.append(f"- Score: {c.score:.2f}")
        for note in c.notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)
