#!/usr/bin/env python3
"""Recompute historical B0-B4 and earlier-MIA held-out metrics from normalized predictions."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import defaultdict
from mia.benchmark import load_jsonl
from mia.study_metrics import Prediction, scored_rows, summarize, confusion_matrix
from repro_stats import fast_cluster_interval

def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--benchmark",default="benchmark/canonical_cases.v1.1.jsonl")
    ap.add_argument("--predictions",required=True)
    ap.add_argument("--provider",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    cases=load_jsonl(args.benchmark)
    preds=[Prediction.from_dict(x) for x in read_jsonl(args.predictions)]
    groups=defaultdict(list)
    for r in scored_rows(preds,cases):
        if r["split"]=="test": groups[r["system_id"]].append(r)
    report={"schema_version":"1.0.0","provider":args.provider,"provider_calls":0,"systems":{}}
    for sid,rows in sorted(groups.items()):
        if len(rows)!=720: raise RuntimeError(f"{sid}: expected 720 test rows, got {len(rows)}")
        report["systems"][sid]={
            "summary":summarize(rows),
            "confusion_matrix":confusion_matrix(rows),
            "confidence_intervals": ({
                m: fast_cluster_interval(rows, m, samples=10000, seed=20260801)
                for m in ("unsafe_execution_rate", "correct_execution_coverage")
            } if sid in {"b1", "b4"} else {})
        }
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,sort_keys=True))
if __name__=="__main__": main()
