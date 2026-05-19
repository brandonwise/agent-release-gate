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
- Calculates pass rate, average latency, p95 latency, and average cost
- Fails if quality drops below your threshold
- Groups results by optional case tags so failure clusters are obvious in JSON and Markdown reports
- Optionally compares against a baseline report and blocks regressions
- Optionally enforces baseline latency/cost drift caps so slower or pricier runs fail fast
- Optionally enforces a global p95 latency limit to catch long-tail slow responses
- Optionally records run summaries and detects cross-run pass-rate, latency, p95 latency, and cost drift across releases
- Supports per-case latency/cost limits to catch outliers hidden by averages
- Enforces telemetry presence when global average latency/cost limits are configured
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

## Track trend drift across runs

Single-baseline checks catch point-in-time regressions. Trend analysis catches slow degradation over many runs.

```bash
# Record this run in a history folder
argate evaluate \
  --spec examples/spec.yaml \
  --results examples/results.json \
  --record-history .gate-history

# Analyze the latest 10 runs and print trend JSON
argate trend --history .gate-history --window 10

# CI mode: fail when pass-rate trend is declining
argate trend --history .gate-history --fail-on-regression

# Optional CI mode: fail when average latency, p95 latency, or cost is trending up
argate trend --history .gate-history --fail-on-latency-regression
argate trend --history .gate-history --fail-on-p95-regression
argate trend --history .gate-history --fail-on-cost-regression

# Fail on any tracked regression across pass rate, latency, p95 latency, or cost
argate trend --history .gate-history --fail-on-any-regression
```

`argate evaluate --record-history ...` stores pass rate, average latency, p95 latency, and average cost in each history file when that telemetry is available in the evaluation report.

`argate trend` keeps the existing pass-rate output and now also includes slope, direction, and regression booleans for:

- `avg_latency_ms`
- `p95_latency_ms`
- `avg_cost_usd`

Older history files that predate these metrics are still supported. When there are fewer than three runs with a given metric inside the analysis window, that metric reports `insufficient_data` instead of forcing a regression.

## Spec format

```yaml
global:
  minimum_pass_rate: 0.8
  allowed_regression: 0.02
  max_avg_latency_ms: 1500
  max_p95_latency_ms: 2000
  max_avg_cost_usd: 0.03
  max_avg_latency_regression_pct: 0.15
  max_avg_cost_regression_pct: 0.10

cases:
  - id: refund_status
    tags: ["billing", "support"]
    expected_all: ["refund", "3-5 business days"]
    expected_any: ["order", "transaction"]
    forbidden: ["cannot help", "policy not found"]
    min_score: 0.72
    max_latency_ms: 1200
    max_cost_usd: 0.02
```

`max_latency_ms` and `max_cost_usd` are optional per-case guardrails. If set, that case fails when telemetry is missing or exceeds the limit.

`tags` is optional per case. Use it to group failures by workflow, surface area, or owner-adjacent bucket (for example `["onboarding", "activation"]`). Reports include a tag summary so PMs and engineers can see where regressions cluster instead of reading every case one by one.

When `max_avg_latency_ms` or `max_avg_cost_usd` is configured globally, the gate also fails if the corresponding telemetry is missing across the run.

When `max_p95_latency_ms` is configured globally, the gate fails if p95 latency is above the threshold or latency telemetry is missing.

When `--baseline` is provided, you can also set `max_avg_latency_regression_pct` and/or `max_avg_cost_regression_pct` to fail if average latency or cost regresses beyond the allowed percentage increase vs baseline.

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
