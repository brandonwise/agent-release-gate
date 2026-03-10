from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .evaluator import evaluate, to_dict, to_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate AI agent outputs and enforce a release gate.")
    sub = parser.add_subparsers(dest="command", required=True)

    eval_cmd = sub.add_parser("evaluate", help="Run gate checks")
    eval_cmd.add_argument("--spec", required=True, help="Path to YAML gate spec")
    eval_cmd.add_argument("--results", required=True, help="Path to JSON case results")
    eval_cmd.add_argument("--baseline", help="Optional baseline report JSON")
    eval_cmd.add_argument("--output", help="Write report JSON to this path")
    eval_cmd.add_argument("--markdown", help="Write markdown report to this path")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "evaluate":
        report = evaluate(spec_path=args.spec, results_path=args.results, baseline_path=args.baseline)
        payload = to_dict(report)

        print(json.dumps(payload, indent=2))

        if args.output:
            Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if args.markdown:
            Path(args.markdown).write_text(to_markdown(report), encoding="utf-8")

        return 0 if report.summary.gate_passed else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
