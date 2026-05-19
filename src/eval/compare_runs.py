"""
Compare two eval report JSON files side by side.

Usage:
  python eval/compare_runs.py \
    eval/reports/eval_no_reranker.json \
    eval/reports/eval_cross_encoder.json
"""

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def flatten_scores(scores: dict, prefix: str = "") -> dict[str, float | None]:
    flat = {}
    for key, value in scores.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            flat.update(flatten_scores(value, full_key))
        elif isinstance(value, (int, float)):
            flat[full_key] = float(value)
    return flat


def main():
    if len(sys.argv) != 3:
        print("Usage: compare_runs.py <report_a> <report_b>")
        sys.exit(1)

    a = load(sys.argv[1])
    b = load(sys.argv[2])

    flat_a = flatten_scores(a.get("scores", {}))
    flat_b = flatten_scores(b.get("scores", {}))

    print(f"\n{'Metric':<40} {'Run A':>10} {'Run B':>10} {'Delta':>10}")
    print("-" * 75)

    all_metrics = sorted(set(flat_a) | set(flat_b))
    for m in all_metrics:
        va = flat_a.get(m)
        vb = flat_b.get(m)
        if va is None or vb is None:
            delta = None
            delta_str = "     N/A"
        else:
            delta = vb - va
            sign = "+" if delta > 0 else ""
            delta_str = f"{sign}{delta:>9.4f}"

        va_str = f"{va:>10.4f}" if va is not None else "       N/A"
        vb_str = f"{vb:>10.4f}" if vb is not None else "       N/A"
        print(f"{m:<40} {va_str} {vb_str} {delta_str}")

    print(f"\nRun A: {a.get('run_at', '?')}  ({a.get('num_queries', '?')} queries)  config={a.get('config', {})}")
    print(f"Run B: {b.get('run_at', '?')}  ({b.get('num_queries', '?')} queries)  config={b.get('config', {})}")

    if a.get("error_rate") is not None or b.get("error_rate") is not None:
        print(f"\nError rate A: {a.get('error_rate', 'N/A')}  |  Error rate B: {b.get('error_rate', 'N/A')}")

    if a.get("scores", {}).get("answer_success_rate") is not None or b.get("scores", {}).get("answer_success_rate") is not None:
        print(f"Success rate A: {a.get('scores', {}).get('answer_success_rate', 'N/A')}  |  Success rate B: {b.get('scores', {}).get('answer_success_rate', 'N/A')}")


if __name__ == "__main__":
    main()
