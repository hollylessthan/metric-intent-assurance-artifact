#!/usr/bin/env python3
"""Credential-free paired audit: sealed final MIA vs clean-prompt sensitivity."""

from __future__ import annotations
import argparse, json, math, random
from collections import Counter, defaultdict
from pathlib import Path

from mia.benchmark import load_jsonl
from mia.study_metrics import Prediction, scored_rows, summarize
from repro_stats import fast_paired_delta


def action_value(x):
    return x.value if hasattr(x, "value") else str(x)


def read_jsonl(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def idx(rows):
    out={}
    for r in rows:
        k=(r["case_id"],r["utterance_id"])
        if k in out: raise RuntimeError(f"duplicate prediction {k}")
        out[k]=r
    return out


def exact_binom_two_sided(a_only:int,b_only:int)->float:
    n=a_only+b_only
    if n==0: return 1.0
    k=min(a_only,b_only)
    p=sum(math.comb(n,i) for i in range(k+1))/(2**n)
    return min(1.0,2*p)


def cluster_delta(a_rows,b_rows,field,samples=10000,seed=20260919):
    metric_name={
        "uer":"unsafe_execution_rate",
        "cec":"correct_execution_coverage",
    }[field]
    # Historical function returns clean - final, so reverse the generic
    # left-minus-right helper arguments.
    return fast_paired_delta(b_rows, a_rows, metric_name, samples=samples, seed=seed)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--provider",choices=["gpt","claude"],required=True)
    ap.add_argument("--final-artifact",type=Path,required=True)
    ap.add_argument("--clean-artifact",type=Path,required=True)
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()

    root=args.repo_root.resolve()
    benchmark=load_jsonl(root/"benchmark/canonical_cases.v1.1.jsonl")
    final_preds=[Prediction.from_dict(x) for x in read_jsonl(args.final_artifact/"predictions.jsonl")]
    clean_preds=[Prediction.from_dict(x) for x in read_jsonl(args.clean_artifact/"predictions.jsonl")]
    final_sc=[r for r in scored_rows(final_preds,benchmark) if r["split"]=="test"]
    clean_sc=[r for r in scored_rows(clean_preds,benchmark) if r["split"]=="test"]
    A={(r["case_id"],r["utterance_id"]):r for r in final_sc}
    B={(r["case_id"],r["utterance_id"]):r for r in clean_sc}
    if set(A)!=set(B) or len(A)!=720: raise RuntimeError("expected identical 720 test rows")

    action_changed=[]
    improved=[]; worsened=[]
    for k in sorted(A):
        a,b=A[k],B[k]
        if a["predicted_action"]!=b["predicted_action"]:
            action_changed.append({
                "case_id":k[0],"utterance_id":k[1],
                "gold_action":action_value(a["gold_action"]),
                "final_action":action_value(a["predicted_action"]),
                "clean_action":action_value(b["predicted_action"]),
            })
        ac=action_value(a["predicted_action"])==action_value(a["gold_action"])
        bc=action_value(b["predicted_action"])==action_value(b["gold_action"])
        if (not ac) and bc: improved.append(k)
        if ac and (not bc): worsened.append(k)

    nonexec=[k for k,r in A.items() if r["gold_action"]!="execute"]
    final_unsafe={k for k in nonexec if A[k]["predicted_action"]=="execute"}
    clean_unsafe={k for k in nonexec if B[k]["predicted_action"]=="execute"}
    final_case={k[0] for k in final_unsafe}
    clean_case={k[0] for k in clean_unsafe}
    fonly=len(final_case-clean_case); conly=len(clean_case-final_case)

    failures=read_jsonl(args.clean_artifact/"failures.jsonl") if (args.clean_artifact/"failures.jsonl").exists() else []
    report={
        "provider":args.provider,
        "evidence_class":"secondary_posthoc_prompt_robustness_changed_case_audit",
        "provider_calls":0,
        "final_summary":summarize(final_sc),
        "clean_summary":summarize(clean_sc),
        "paired_delta_clean_minus_final":{
            "unsafe_execution_rate":cluster_delta(final_sc,clean_sc,"uer"),
            "correct_execution_coverage":cluster_delta(final_sc,clean_sc,"cec"),
        },
        "action_changed_utterances":len(action_changed),
        "action_transition_counts":{f"{a}->{b}": n for (a,b),n in Counter((x["final_action"],x["clean_action"]) for x in action_changed).items()},
        "action_correct_improved":len(improved),
        "action_correct_worsened":len(worsened),
        "unsafe_utterances_final":len(final_unsafe),
        "unsafe_utterances_clean":len(clean_unsafe),
        "new_unsafe_utterances":sorted([{"case_id":k[0],"utterance_id":k[1]} for k in clean_unsafe-final_unsafe],key=lambda x:(x["case_id"],x["utterance_id"])),
        "removed_unsafe_utterances":sorted([{"case_id":k[0],"utterance_id":k[1]} for k in final_unsafe-clean_unsafe],key=lambda x:(x["case_id"],x["utterance_id"])),
        "unsafe_cases_final":len(final_case),
        "unsafe_cases_clean":len(clean_case),
        "unsafe_case_mcnemar":{"final_only":fonly,"clean_only":conly,"discordant":fonly+conly,"exact_two_sided_p":exact_binom_two_sided(fonly,conly)},
        "clean_failures":failures,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
