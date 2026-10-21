# Tracebench

### Turn a browser capture into an actionable API performance report.

An offline HTTP Archive (HAR) analyzer that groups common resource-ID routes, calculates nearest-rank latency percentiles, reports failed requests, and enforces per-route performance budgets. Python 3.11+, no external dependencies.

## Run the included example

```bash
python tracebench.py examples/sample.har
python tracebench.py examples/sample.har --format json
python tracebench.py examples/sample.har --max-p95 500 --max-error-rate 0.05
```

The final command intentionally exits with status **1**: the synthetic capture exceeds the example budgets. See [example report](examples/report.md).

## Why it is useful

A single slow request can disappear inside a global average. Tracebench preserves per-route sample counts, p50, p95, maximum latency, and the error fraction so a report shows both distribution and context.

| Behavior | Detail |
|---|---|
| Route grouping | Numeric and UUID path segments normalize to `:id` |
| Report hygiene | Headers, bodies, credentials, query strings, and fragments are not copied into output |
| Latency | Nearest-rank p50/p95 over recorded HAR `time` values |
| Failed requests | HTTP status 0 or 400–599 |
| Output | Markdown for review, JSON for automation |
| Invalid entries | Counted as skipped; produce nonzero exit status |
| Budgets | Per-route p95 limit in milliseconds and error-rate fraction |

## Automation contract

| Exit code | Meaning |
|---|---|
| `0` | Capture analyzed; configured budgets satisfied |
| `1` | At least one route exceeded a budget |
| `2` | Invalid input, skipped entries, empty capture, or CLI error |

```bash
python tracebench.py capture.har --max-p95 300 --max-error-rate 0 > performance.md
```

HAR captures can contain sensitive data. The analyzer does not emit request headers or bodies, but literal path segments may still contain names or other sensitive values. Review reports before sharing them. The tool never sends the capture to a service.

## Design decisions and limits

- **Nearest rank:** transparent for discrete samples. Small samples make p95 noisy; always inspect the count.
- **Route normalization:** merges common resource IDs without needing an API schema. Numeric path segments such as years or API versions can also merge; hostnames are deliberately omitted, so captures spanning hosts may aggregate similarly named routes.
- **Observed traffic only:** HAR timing includes the browser's recorded request duration; this is not a server profiler or load generator.
- **No silent green:** malformed and empty captures fail even when no numeric budget is exceeded.

## Verification

```bash
python -m unittest discover -s tests -v
```

Tests cover percentile calculation, route grouping, query exclusion, UUID normalization, malformed entries, escaped Markdown, and CLI exit codes. CI is configured for Python 3.11–3.13.

## Repository guide

| Path | Purpose |
|---|---|
| `tracebench.py` | Parsing, aggregation, output, and budget enforcement |
| `tests/` | Analysis and CLI checks |
| `examples/` | Synthetic capture and generated report |
| `.github/workflows/` | CI |
