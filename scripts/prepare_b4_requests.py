#!/usr/bin/env python3
"""Prepare B4-Matched provider requests from the exact final-MIA requests and sealed semantic generations."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from mia.registry import Registry
from mia.v2_matched_baselines import build_b4_matched_adapter_input

def read_jsonl(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--provider",choices=["gpt","claude"],required=True)
    ap.add_argument("--final-requests",type=Path,required=True)
    ap.add_argument("--final-raw",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    root=args.repo_root.resolve()
    req=read_jsonl(args.final_requests)
    raw={x["request_id"]:x["raw"] for x in read_jsonl(args.final_raw) if x.get("system_id")=="mia-v2"}
    if len(req)!=720 or len(raw)!=720: raise RuntimeError("expected 720 final requests and raw generations")
    rows=[]
    for r in req:
        case=r["case"]; rid=case["request_id"]
        reg=Registry.load(root/f"registries/{case['domain']}.json")
        rows.append(build_b4_matched_adapter_input(
            raw[rid],case,reg,provider=args.provider,model_id=r["model_id"],
            decoding=r["decoding"],prompts_root=root/"prompts/v2"))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text("".join(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n" for x in rows),encoding="utf-8")
    print(json.dumps({"provider":args.provider,"requests":len(rows),"provider_calls":0},sort_keys=True))
if __name__=="__main__": main()
