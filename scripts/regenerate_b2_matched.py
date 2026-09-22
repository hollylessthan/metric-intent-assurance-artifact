#!/usr/bin/env python3
"""Regenerate B2-Matched predictions deterministically from sealed final-MIA generations."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from mia.registry import Registry
from mia.v2_matched_baselines import normalize_b2_matched

def read_jsonl(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--provider",choices=["gpt","claude"],required=True)
    ap.add_argument("--mia-artifact",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    root=args.repo_root.resolve()
    requests=read_jsonl(args.mia_artifact/"requests.jsonl")
    raw={x["request_id"]:x["raw"] for x in read_jsonl(args.mia_artifact/"raw_outputs.jsonl") if x.get("system_id")=="mia-v2"}
    if len(requests)!=720 or len(raw)!=720:
        raise RuntimeError(f"expected 720 requests/raw outputs, got {len(requests)}/{len(raw)}")
    rows=[]
    for adapter in requests:
        case=adapter["case"]; rid=case["request_id"]
        registry=Registry.load(root/f"registries/{case['domain']}.json")
        pred,_=normalize_b2_matched(raw[rid],case,registry,
            run_id=f"artifact-b2-matched-{args.provider}",model_id=adapter["model_id"])
        rows.append(pred)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in rows),encoding="utf-8")
    print(json.dumps({"provider":args.provider,"predictions":len(rows),"provider_calls":0},sort_keys=True))
if __name__=="__main__": main()
