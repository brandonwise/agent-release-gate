# agent-release-gate

Ship AI agents with a seatbelt on.

`agent-release-gate` is a lightweight CI gate for AI systems. It checks agent outputs against expected behavior, catches regressions against a baseline, and returns a hard pass/fail signal so bad runs don't sneak into production.

## Why this exists

Most AI failures don't look like crashes. They look like:

- Confident nonsense
- Slower responses and higher cost over time
- A prompt tweak that quietly made outcomes worse

This tool makes those problems visible before release.

## What it does

- Scores each test case using expected + forbidden phrases
- Calculates pass rate, average latency, and average cost
- Fails if quality drops below your threshold
- Optionally compares against a baseline report and blocks regressions
- Supports per-case latency/cost limits to catch outliers hidden by averages
- Outputs both JSON (for machines) and Markdown (for humans)

## Install

```bash
pip install -e .
```

## Quick start

```bash
argate evaluate \
  --spec examples/spec.yaml \
  --results examples/results.json \
  --output gate-report.json \
  --markdown gate-report.md
```

The command exits with:

- `0` when the gate passes
- `1` when the gate fails

Perfect for CI pipelines.

## Spec format

```yaml
global:
  minimum_pass_rate: 0.8
  allowed_regression: 0.02
  max_avg_latency_ms: 1500
  max_avg_cost_usd: 0.03

cases:
  - id: refund_status
    expected_all: ["refund", "3-5 business days"]
    expected_any: ["order", "transaction"]
    forbidden: ["cannot help", "policy not found"]
    min_score: 0.72
    max_latency_ms: 1200
    max_cost_usd: 0.02
```

`max_latency_ms` and `max_cost_usd` are optional per-case guardrails. If set, that case fails when telemetry is missing or exceeds the limit.

## Repo layout

- `src/agent_release_gate/`: scoring + gate logic
- `examples/`: runnable demo spec and results
- `tests/`: unit tests
- `.github/workflows/ci.yml`: CI example

## Development

```bash
pip install -e . pytest
pytest
```

## License

MIT
