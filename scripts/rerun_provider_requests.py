#!/usr/bin/env python3
"""Re-execute frozen MIA-v2 or B4-Matched requests with reviewer-supplied provider credentials.

This is optional: published paper-number reproduction uses sealed outputs and makes no provider calls.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from mia.registry import Registry
from mia.v2_system import normalize_mia_v2_output
from mia.v2_matched_baselines import normalize_b4_matched

def read_jsonl(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]

def write_jsonl(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in rows),encoding="utf-8")

def thresholds(root,provider):
    j=json.loads((root/"evaluation/threshold_lock.json").read_text(encoding="utf-8"))["models"][provider]
    return float(j["mia_execute_threshold"]),float(j["mia_ambiguity_margin"])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--provider",choices=["gpt","claude"],required=True)
    ap.add_argument("--system",choices=["mia-v2","b4-matched"],required=True)
    ap.add_argument("--requests",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    ap.add_argument("--sealed-mia-raw",type=Path,help="Required for B4-Matched normalization.")
    ap.add_argument("--max-calls",type=int,default=720)
    args=ap.parse_args()
    root=args.repo_root.resolve(); out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    requests=read_jsonl(args.requests)
    if len(requests)>args.max_calls: raise RuntimeError("request count exceeds --max-calls")
    if args.provider=="gpt":
        adapter=root/"scripts"/("provider_mia_openai.py" if args.system=="mia-v2" else "provider_b4_openai.py")
        evidence_env="MIA_V2_OPENAI_EVIDENCE_LOG" if args.system=="mia-v2" else "MIA_OPENAI_EVIDENCE_LOG"
        if not os.environ.get("OPENAI_API_KEY"): raise RuntimeError("OPENAI_API_KEY is not set")
    else:
        adapter=root/"scripts"/("provider_mia_anthropic.py" if args.system=="mia-v2" else "provider_b4_anthropic.py")
        evidence_env="MIA_V2_ANTHROPIC_EVIDENCE_LOG" if args.system=="mia-v2" else "MIA_PROVIDER_EVIDENCE_LOG"
        if not os.environ.get("ANTHROPIC_API_KEY"): raise RuntimeError("ANTHROPIC_API_KEY is not set")
    env=dict(os.environ); env[evidence_env]=str(out/f"{args.provider}_provider_evidence.jsonl")
    if args.provider=="gpt":
        env.setdefault("MIA_OPENAI_PRICING_CONFIG",str(root/"evaluation/openai-pricing.json"))
    else:
        env.setdefault("MIA_PROVIDER_PRICING_CONFIG",str(root/"evaluation/anthropic-pricing.json"))
    mia_raw={}
    if args.system=="b4-matched":
        if args.sealed_mia_raw is None: raise RuntimeError("--sealed-mia-raw is required for B4-Matched")
        mia_raw={x["request_id"]:x["raw"] for x in read_jsonl(args.sealed_mia_raw) if x.get("system_id")=="mia-v2"}
    te,ta=thresholds(root,args.provider)
    raws=[]; preds=[]; traces=[]; failures=[]
    for idx,r in enumerate(requests,1):
        start=time.monotonic()
        p=subprocess.run([sys.executable,str(adapter)],input=json.dumps(r),text=True,capture_output=True,env=env,cwd=root)
        rid=r["case"]["request_id"]
        if p.returncode:
            failures.append({"request_id":rid,"returncode":p.returncode,"stderr":p.stderr[-4000:]})
            continue
        raw=json.loads(p.stdout)
        case=r["case"]; reg=Registry.load(root/f"registries/{case['domain']}.json")
        if args.system=="mia-v2":
            pred,trace=normalize_mia_v2_output(raw,case,reg,run_id=f"artifact-rerun-{args.provider}",model_id=r["model_id"],execute_threshold=te,ambiguity_margin=ta)
        else:
            pred,trace=normalize_b4_matched(raw,mia_raw[rid],case,reg,run_id=f"artifact-rerun-b4-{args.provider}",model_id=r["model_id"])
        pred["latency_ms"]=(time.monotonic()-start)*1000
        raws.append({"request_id":rid,"system_id":args.system,"raw":raw})
        preds.append(pred); traces.append({"request_id":rid,**trace})
        if idx%50==0: print(f"completed {idx}/{len(requests)}",file=sys.stderr)
    write_jsonl(out/"raw_outputs.jsonl",raws)
    write_jsonl(out/"predictions.jsonl",preds)
    write_jsonl(out/"traces.jsonl",traces)
    write_jsonl(out/"failures.jsonl",failures)
    print(json.dumps({"provider":args.provider,"system":args.system,"requests":len(requests),"successes":len(preds),"failures":len(failures)},sort_keys=True))
    return 0 if not failures else 2
if __name__=="__main__": raise SystemExit(main())
