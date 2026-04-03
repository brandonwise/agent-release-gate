from pathlib import Path

from agent_release_gate.evaluator import evaluate


def test_evaluate_happy_path(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 0.5
cases:
  - id: case_1
    expected_all: ["refund", "days"]
    expected_any: ["order", "ticket"]
    forbidden: ["cannot help"]
    min_score: 0.7
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text(
        """
{
  "cases": [
    {
      "id": "case_1",
      "response": "Your refund for order 123 is processing and will land in 3-5 business days.",
      "latency_ms": 800,
      "cost_usd": 0.012
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    report = evaluate(spec, results)
    assert report.summary.gate_passed is True
    assert report.summary.pass_rate == 1.0
    assert report.cases[0].passed is True


def test_evaluate_regression(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 0.5
  allowed_regression: 0.05
cases:
  - id: case_1
    expected_all: ["refund"]
    min_score: 0.9
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text('{"cases":[{"id":"case_1","response":"unknown"}]}', encoding="utf-8")

    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        '{"summary":{"pass_rate":1.0},"cases":[]}',
        encoding="utf-8",
    )

    report = evaluate(spec, results, baseline)
    assert report.summary.gate_passed is False
    assert any("Regression detected" in r for r in report.summary.gate_reasons)


def test_case_limits_fail_on_latency_and_cost_outliers(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 1.0
cases:
  - id: case_1
    expected_all: ["refund"]
    min_score: 0.7
    max_latency_ms: 1200
    max_cost_usd: 0.02
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text(
        """
{
  "cases": [
    {
      "id": "case_1",
      "response": "refund confirmed",
      "latency_ms": 1900,
      "cost_usd": 0.031
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    report = evaluate(spec, results)
    assert report.summary.gate_passed is False
    assert report.cases[0].passed is False
    assert any("Latency 1900ms exceeds case max 1200ms" in n for n in report.cases[0].notes)
    assert any("Cost $0.031000 exceeds case max $0.020000" in n for n in report.cases[0].notes)


def test_case_limits_require_telemetry_when_configured(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 1.0
cases:
  - id: case_1
    expected_all: ["refund"]
    min_score: 0.7
    max_latency_ms: 1200
    max_cost_usd: 0.02
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text(
        """
{
  "cases": [
    {
      "id": "case_1",
      "response": "refund confirmed"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    report = evaluate(spec, results)
    assert report.summary.gate_passed is False
    assert report.cases[0].passed is False
    assert "Missing latency_ms for case with max_latency_ms set" in report.cases[0].notes
    assert "Missing cost_usd for case with max_cost_usd set" in report.cases[0].notes


def test_global_latency_limit_requires_telemetry_when_configured(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 1.0
  max_avg_latency_ms: 1000
cases:
  - id: case_1
    expected_all: ["refund"]
    min_score: 0.7
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text(
        '{"cases":[{"id":"case_1","response":"refund confirmed"}]}',
        encoding="utf-8",
    )

    report = evaluate(spec, results)
    assert report.summary.gate_passed is False
    assert any(
        "Average latency limit is configured, but no latency telemetry was provided" in r
        for r in report.summary.gate_reasons
    )


def test_global_cost_limit_requires_telemetry_when_configured(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 1.0
  max_avg_cost_usd: 0.01
cases:
  - id: case_1
    expected_all: ["refund"]
    min_score: 0.7
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text(
        '{"cases":[{"id":"case_1","response":"refund confirmed"}]}',
        encoding="utf-8",
    )

    report = evaluate(spec, results)
    assert report.summary.gate_passed is False
    assert any(
        "Average cost limit is configured, but no cost telemetry was provided" in r
        for r in report.summary.gate_reasons
    )


def test_baseline_latency_regression_limit_blocks_slowdown(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 1.0
  max_avg_latency_regression_pct: 0.10
cases:
  - id: case_1
    expected_all: ["refund"]
    min_score: 0.7
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text(
        '{"cases":[{"id":"case_1","response":"refund confirmed","latency_ms":1300}]}',
        encoding="utf-8",
    )

    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        '{"summary":{"pass_rate":1.0,"avg_latency_ms":1000},"cases":[]}',
        encoding="utf-8",
    )

    report = evaluate(spec, results, baseline)
    assert report.summary.gate_passed is False
    assert any("Latency regression detected" in r for r in report.summary.gate_reasons)


def test_baseline_cost_regression_limit_blocks_spend_drift(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 1.0
  max_avg_cost_regression_pct: 0.20
cases:
  - id: case_1
    expected_all: ["refund"]
    min_score: 0.7
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text(
        '{"cases":[{"id":"case_1","response":"refund confirmed","cost_usd":0.018}]}',
        encoding="utf-8",
    )

    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        '{"summary":{"pass_rate":1.0,"avg_cost_usd":0.01},"cases":[]}',
        encoding="utf-8",
    )

    report = evaluate(spec, results, baseline)
    assert report.summary.gate_passed is False
    assert any("Cost regression detected" in r for r in report.summary.gate_reasons)


def test_baseline_regression_limits_require_current_and_baseline_telemetry(tmp_path: Path):
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        """
global:
  minimum_pass_rate: 1.0
  max_avg_latency_regression_pct: 0.15
  max_avg_cost_regression_pct: 0.15
cases:
  - id: case_1
    expected_all: ["refund"]
    min_score: 0.7
""".strip(),
        encoding="utf-8",
    )

    results = tmp_path / "results.json"
    results.write_text(
        '{"cases":[{"id":"case_1","response":"refund confirmed"}]}',
        encoding="utf-8",
    )

    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        '{"summary":{"pass_rate":1.0},"cases":[]}',
        encoding="utf-8",
    )

    report = evaluate(spec, results, baseline)
    assert report.summary.gate_passed is False
    assert any("Latency regression limit is configured" in r for r in report.summary.gate_reasons)
    assert any("Cost regression limit is configured" in r for r in report.summary.gate_reasons)
