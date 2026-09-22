#!/usr/bin/env python3
"""Zero-cost sensitivity for the frozen top_n surface-template defect.

Does not modify frozen benchmark labels. It:
1) verifies the affected test family;
2) recomputes historical H2 after excluding any contrastive group containing top_n;
3) recomputes final-MIA / B2-Matched / B4-Matched CEC and strict execution
   precision after excluding the 36 affected utterances.
"""
from __future__ import annotations

import argparse, json, math, random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mia.benchmark import load_jsonl
from mia.models import Action
from mia.study_metrics import Prediction, benchmark_index, intent_scores, scored_rows, summarize
from mia.registry import Registry
from mia.v2_matched_baselines import normalize_b2_matched


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def exact_mcnemar(left: list[bool], right: list[bool]) -> dict[str, Any]:
    left_only=sum(a and not b for a,b in zip(left,right))
    right_only=sum(b and not a for a,b in zip(left,right))
    n=left_only+right_only
    if n==0:
        p=1.0
    else:
        k=min(left_only,right_only)
        tail=sum(math.comb(n,i) for i in range(k+1))/(2**n)
        p=min(1.0,2*tail)
    return {"left_only":left_only,"right_only":right_only,"discordant":n,"p_value":p}


def cluster_bootstrap_diff(rows: list[dict[str, Any]], samples=10000, seed=20260919):
    rng=random.Random(seed)
    def stat(block):
        return (
            sum(x["intent_visibility"] for x in block)/len(block)
            - sum(x["execution_visibility"] for x in block)/len(block)
        )
    est=stat(rows)
    vals=[]
    for _ in range(samples):
        draw=[rng.choice(rows) for _ in rows]
        vals.append(stat(draw))
    vals.sort()
    return {
        "estimate":est,
        "low":vals[math.floor(.025*(samples-1))],
        "high":vals[math.ceil(.975*(samples-1))],
    }


def identify_topn(root: Path, benchmark: list[dict[str, Any]]):
    utterances=read_jsonl(root/"benchmark/utterances.jsonl")
    affected=[u for u in utterances if u.get("split")=="test" and str(u.get("template_family","")).endswith("/top_n")]
    case_ids=sorted({u["canonical_case_id"] for u in affected})
    surface_utterance_ids=sorted({u["utterance_id"] for u in affected})
    prediction_utterance_ids=sorted(
        f"{cid}#u{pos}" for cid in case_ids for pos in range(3)
    )
    bidx={x["case_id"]:x for x in benchmark}
    if len(case_ids)!=12 or len(surface_utterance_ids)!=36 or len(prediction_utterance_ids)!=36:
        raise RuntimeError(
            f"expected 12 top_n cases / 36 utterances, got "
            f"{len(case_ids)} / {len(surface_utterance_ids)} / {len(prediction_utterance_ids)}"
        )
    defects=[]
    prohibited_tokens=(" top ","top "," top","rank","highest","largest","lowest","smallest","first ","limit ")
    for cid in case_ids:
        case=bidx[cid]
        gold=case["gold_intents"][0]
        if gold.get("limit")!=10 or not gold.get("ordering"):
            raise RuntimeError(f"{cid}: expected gold ordering plus limit=10")
        rows=[u for u in affected if u["canonical_case_id"]==cid]
        surfaced=[]
        for u in rows:
            t=" "+u["text"].lower()+" "
            surfaced.append(any(tok in t for tok in prohibited_tokens))
        defects.append({
            "case_id":cid,
            "contrastive_group":case.get("contrastive_group"),
            "utterances":[u["text"] for u in rows],
            "gold_ordering":gold.get("ordering"),
            "gold_limit":gold.get("limit"),
            "surface_mentions_top_or_ranking":surfaced,
            "annotation_status":case.get("annotation_status"),
        })
    if any(any(x["surface_mentions_top_or_ranking"]) for x in defects):
        raise RuntimeError("at least one affected utterance appears to express top/ranking semantics")
    groups=sorted({x["contrastive_group"] for x in defects if x["contrastive_group"]})
    if len(groups)!=12:
        raise RuntimeError(f"expected 12 affected contrastive groups, got {len(groups)}")
    return {
        "case_ids":case_ids,
        "surface_utterance_ids":surface_utterance_ids,
        "prediction_utterance_ids":prediction_utterance_ids,
        "contrastive_groups":groups,
        "details":defects,
    }


def h2_sensitivity(h2: dict[str, Any], excluded_groups: set[str]):
    details=h2["details"]
    by_group=defaultdict(list)
    for row in details:
        if row["cluster_id"] not in excluded_groups:
            by_group[row["cluster_id"]].append(row)
    pairs=[]
    for gid,block in sorted(by_group.items()):
        pairs.append({
            "cluster_id":gid,
            "execution_visibility":any(not r["execution_correct"] for r in block),
            "intent_visibility":any(not r["intent_correct"] for r in block),
            "hidden_disagreement":any(r["execution_correct"] and not r["intent_correct"] for r in block),
        })
    execution=[x["execution_visibility"] for x in pairs]
    intent=[x["intent_visibility"] for x in pairs]
    apparently=[r for r in details if r["cluster_id"] not in excluded_groups and r["execution_correct"]]
    disagree=[r for r in apparently if not r["intent_correct"]]
    original_pairs=[]
    all_by=defaultdict(list)
    for row in details:
        all_by[row["cluster_id"]].append(row)
    for gid,block in sorted(all_by.items()):
        original_pairs.append({
            "cluster_id":gid,
            "execution_visibility":any(not r["execution_correct"] for r in block),
            "intent_visibility":any(not r["intent_correct"] for r in block),
        })
    original_discordant=[
        x["cluster_id"] for x in original_pairs if (not x["execution_visibility"]) and x["intent_visibility"]
    ]
    affected_discordant=sorted(set(original_discordant)&excluded_groups)
    return {
        "groups_remaining":len(pairs),
        "attempted_b1_executions":sum(len(v) for v in by_group.values()),
        "apparently_execution_correct":len(apparently),
        "execution_correct_but_intent_wrong":len(disagree),
        "disagreement_rate":len(disagree)/len(apparently) if apparently else None,
        "execution_visible_groups":sum(execution),
        "intent_visible_groups":sum(intent),
        "visibility_gain":sum(intent)/len(intent)-sum(execution)/len(execution),
        "bootstrap_95":cluster_bootstrap_diff(pairs),
        "mcnemar":exact_mcnemar(execution,intent),
        "original_canonical_only_discordant_groups":len(original_discordant),
        "topn_among_original_canonical_only":len(affected_discordant),
        "topn_canonical_only_group_ids":affected_discordant,
    }


def load_final_mia(path: Path) -> list[Prediction]:
    return [Prediction.from_dict(x) for x in read_jsonl(path/"predictions.jsonl")]


def load_b4(path: Path) -> list[Prediction]:
    out=[]
    for x in read_jsonl(path/"predictions.jsonl"):
        y=dict(x)
        y["system_id"]="mia"
        out.append(Prediction.from_dict(y))
    return out


def regenerate_b2(root: Path, mia_dir: Path, provider: str) -> list[Prediction]:
    requests=read_jsonl(mia_dir/"requests.jsonl")
    raw={x["request_id"]:x["raw"] for x in read_jsonl(mia_dir/"raw_outputs.jsonl") if x.get("system_id")=="mia-v2"}
    out=[]
    for adapter in requests:
        case=adapter["case"]
        registry=Registry.load(root/f"registries/{case['domain']}.json")
        pred,_=normalize_b2_matched(
            raw[case["request_id"]],case,registry,
            run_id=f"topn-sensitivity-b2-{provider}",
            model_id=adapter["model_id"],
        )
        pred=dict(pred)
        pred["system_id"]="mia"
        out.append(Prediction.from_dict(pred))
    return out


def strict_metrics(preds: list[Prediction], benchmark: list[dict[str, Any]], excluded_utterances: set[str]):
    idx=benchmark_index(benchmark)
    kept=[p for p in preds if idx[(p.case_id,p.utterance_id)]["split"]=="test" and p.utterance_id not in excluded_utterances]
    answerable=[p for p in kept if idx[(p.case_id,p.utterance_id)]["gold_action"]=="execute"]
    execs=[p for p in kept if p.predicted_action==Action.EXECUTE]
    cec_num=0
    strict_num=0
    wrong_answerable=0
    for p in answerable:
        if p.predicted_action!=Action.EXECUTE:
            continue
        case=idx[(p.case_id,p.utterance_id)]
        exact,_,_=intent_scores(p.predicted_intent,case.get("gold_intents",[]))
        if exact:
            cec_num+=1
        else:
            wrong_answerable+=1
    for p in execs:
        case=idx[(p.case_id,p.utterance_id)]
        if case["gold_action"]!="execute":
            continue
        exact,_,_=intent_scores(p.predicted_intent,case.get("gold_intents",[]))
        strict_num+=int(exact)
    return {
        "rows_remaining":len(kept),
        "answerable_denominator":len(answerable),
        "correct_execution_coverage":cec_num/len(answerable) if answerable else None,
        "correct_exact_intent_executions":cec_num,
        "wrong_intent_executions_on_answerable":wrong_answerable,
        "predicted_execute_denominator":len(execs),
        "strict_execution_precision":strict_num/len(execs) if execs else None,
        "strict_execution_precision_numerator":strict_num,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--confirmatory",type=Path,required=True)
    ap.add_argument("--gpt-mia",type=Path,required=True)
    ap.add_argument("--claude-mia",type=Path,required=True)
    ap.add_argument("--gpt-b4",type=Path,required=True)
    ap.add_argument("--claude-b4",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    root=args.repo_root.resolve()
    benchmark=load_jsonl(root/"benchmark/canonical_cases.v1.1.jsonl")
    defect=identify_topn(root,benchmark)
    excluded_groups=set(defect["contrastive_groups"])
    excluded_utts=set(defect["prediction_utterance_ids"])
    h2src=read_json(args.confirmatory/"h2-contrastive-visibility.json")
    providers={}
    for provider,mia_dir,b4_dir in (
        ("gpt",args.gpt_mia,args.gpt_b4),
        ("claude",args.claude_mia,args.claude_b4),
    ):
        providers[provider]={
            "h2_without_topn":h2_sensitivity(h2src[provider],excluded_groups),
            "final_mia_without_topn":strict_metrics(load_final_mia(mia_dir),benchmark,excluded_utts),
            "b2_matched_without_topn":strict_metrics(regenerate_b2(root,mia_dir,provider),benchmark,excluded_utts),
            "b4_matched_without_topn":strict_metrics(load_b4(b4_dir),benchmark,excluded_utts),
        }
    report={
        "schema_version":"1.0.0",
        "study_id":"topn-template-defect-sensitivity",
        "evidence_class":"posthoc_zero_cost_benchmark_defect_sensitivity",
        "provider_calls":0,
        "frozen_gold_modified":False,
        "defect":defect,
        "providers":providers,
        "interpretation":[
            "The top_n family is retained in frozen gold but excluded only for sensitivity estimates.",
            "H2 sensitivity removes the entire contrastive group whenever either member is a top_n case.",
            "CEC and strict execution precision sensitivity remove all 36 affected utterances from denominators and numerators.",
        ],
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
