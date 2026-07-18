#!/usr/bin/env python3
"""Re-score an existing benchmark/smoke JSON with the current scorer (no LLM calls)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lingjing_ai.evaluation.loader import load_dataset
from lingjing_ai.evaluation.models import CaseScore
from lingjing_ai.evaluation.reporter import build_report, write_report
from lingjing_ai.evaluation.scoring import score_case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_json", type=Path)
    parser.add_argument("--dataset", type=Path, default=PROJECT_ROOT / "evaluation/datasets/lingjing_qa_v1.json")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports/qa_eval")
    parser.add_argument("--mode-suffix", default="rescored")
    args = parser.parse_args()

    raw = json.loads(args.report_json.read_text(encoding="utf-8"))
    dataset = load_dataset(args.dataset)
    by_id = {case.case_id: case for case in dataset.cases}
    scores: list[CaseScore] = []
    for item in raw.get("cases", []):
        case = by_id[item["case_id"]]
        response = item.get("response") or {}
        # Preserve latency metrics from the original run.
        response = {
            **response,
            "first_token_ms": (item.get("metrics") or {}).get("first_token_ms"),
            "total_ms": (item.get("metrics") or {}).get("total_ms"),
        }
        scores.append(score_case(case, response))

    mode = f"{raw.get('mode', 'benchmark')}_{args.mode_suffix}"
    runtime = {
        **(raw.get("runtime") or {}),
        "rescored_from": str(args.report_json),
        "note": "Reused model answers; only scoring policy changed.",
    }
    report = build_report(dataset, scores, mode=mode, runtime=runtime)
    json_path, markdown_path = write_report(report, args.output_dir, create_baseline=False)
    summary = report["summary"]
    print(
        f"重打分完成：{len(scores)}题，总分 {summary['deterministic_score']}，"
        f"通过 {summary['passed_cases']}，景区事实准确率 {summary.get('scenic_factual_accuracy')}%。"
    )
    print(f"JSON报告：{json_path}")
    print(f"Markdown报告：{markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
