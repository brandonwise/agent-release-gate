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
