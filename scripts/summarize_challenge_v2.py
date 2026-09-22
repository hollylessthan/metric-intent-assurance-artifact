#!/usr/bin/env python3
"""Regenerate reader-facing challenge-v2 summary from the frozen scored evaluation artifact."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--evaluation",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    e=json.loads(Path(args.evaluation).read_text(encoding="utf-8"))
    out={"schema_version":"1.0.0","study":"mia-v2-challenge-v2","total_cases":e["case_count"],
         "execute_cases":e["execute_cases"],"non_execute_cases":e["nonexecute_cases"],"providers":{}}
    for provider in ("gpt","claude"):
        p=e["providers"][provider]["mia-v2"]
        conf=p["confusion"]
        reject_correct=conf["reject"]["reject"]
        reject_total=sum(conf["reject"].values())
        out["providers"][provider]={
            "action_exact":p["action_exact"],
            "uer":p["unsafe_execution_rate"],
            "cec":p["correct_execution_coverage"],
            "reject_correct":{"num":reject_correct,"den":reject_total},
        }
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out,indent=2,sort_keys=True))
if __name__=="__main__": main()
