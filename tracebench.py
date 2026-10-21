"""Offline HAR analysis with route aggregation and enforceable latency budgets."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


def percentile(values, quantile):
    """Nearest-rank percentile; suitable for a discrete observed sample."""
    if not values:
        return 0
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)]


def route_key(url):
    """Discard credentials, queries and fragments; normalize common resource IDs."""
    path = urlsplit(url).path or "/"
    segments = []
    for part in path.split("/"):
        if part.isdigit() or re.fullmatch(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", part):
            part = ":id"
        segments.append(part)
    return "/".join(segments)


def analyze(document):
    entries = document.get("log", {}).get("entries")
    if not isinstance(entries, list):
        raise ValueError("Expected HAR log.entries to be an array")
    groups = defaultdict(list)
    skipped = 0
    for entry in entries:
        try:
            duration = entry["time"]
            status = entry["response"]["status"]
            method = entry["request"]["method"]
            url = entry["request"]["url"]
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
                raise ValueError("Invalid duration")
            if isinstance(status, bool) or not isinstance(status, int) or not 0 <= status <= 599:
                raise ValueError("Invalid status")
            if not isinstance(method, str) or not re.fullmatch(r"[A-Za-z]+", method):
                raise ValueError("Invalid method")
            if not isinstance(url, str) or not urlsplit(url).hostname:
                raise ValueError("Invalid URL")
            groups[(method.upper(), route_key(url))].append((duration, status))
        except (KeyError, TypeError, ValueError):
            skipped += 1
    routes = []
    for (method, path), samples in groups.items():
        times = [item[0] for item in samples]
        errors = sum(status == 0 or status >= 400 for _, status in samples)
        routes.append({"method": method, "path": path, "requests": len(samples),
                       "p50_ms": percentile(times, .5), "p95_ms": percentile(times, .95),
                       "max_ms": max(times), "error_rate": errors / len(samples)})
    routes.sort(key=lambda route: (-route["p95_ms"], route["method"], route["path"]))
    return {"requests": sum(route["requests"] for route in routes), "skipped": skipped, "routes": routes}


def render_markdown(report):
    lines = ["# HTTP performance report", "", f"Requests: {report['requests']} · Skipped: {report['skipped']}", "",
             "| Method | Route | Requests | p50 (ms) | p95 (ms) | Errors |",
             "|---|---|---:|---:|---:|---:|"]
    for row in report["routes"]:
        path = row['path'].replace('|', '&#124;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '')
        lines.append(f"| {row['method']} | {path} | {row['requests']} | {row['p50_ms']:.1f} | {row['p95_ms']:.1f} | {row['error_rate']:.1%} |")
    return "\n".join(lines) + "\n"


def positive_number(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("Expected a finite non-negative number")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("har", type=Path)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--max-p95", type=positive_number, help="Fail if any route exceeds this latency in ms")
    parser.add_argument("--max-error-rate", type=positive_number, help="Maximum fraction of failed requests per route (0..1)")
    args = parser.parse_args(argv)
    if args.max_error_rate is not None and args.max_error_rate > 1:
        parser.error("--max-error-rate must be between 0 and 1")
    try:
        report = analyze(json.loads(args.har.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print(f"tracebench: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.format == "json" else render_markdown(report), end="\n" if args.format == "json" else "")
    if not report["requests"] or report["skipped"]:
        print("tracebench: incomplete or empty capture", file=sys.stderr)
        return 2
    return int(any((args.max_p95 is not None and row["p95_ms"] > args.max_p95) or
                   (args.max_error_rate is not None and row["error_rate"] > args.max_error_rate)
                   for row in report["routes"]))


if __name__ == "__main__":
    sys.exit(main())
