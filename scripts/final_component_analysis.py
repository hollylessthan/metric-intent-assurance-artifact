#!/usr/bin/env python3
"""Credential-free final-MIA component analysis for the consolidated PVLDB review.

Uses sealed final-v2 generations only. No provider calls.
"""
from __future__ import annotations

import argparse, json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from mia.assurance import Assurer
from mia.benchmark import load_jsonl
from mia.generation import GenerationResult
from mia.models import Action, Context, Intent
from mia.study_metrics import INTENT_SLOT_WEIGHTS, Prediction, benchmark_index, confusion_matrix, intent_scores, scored_rows, summarize
from mia.registry import Registry
from mia.validation import Validator
from mia.v2_system import parse_generation_v2
from mia.v2_matched_baselines import normalize_b2_matched


def read_jsonl(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def read_first_json(path: Path) -> Any:
    files=sorted(path.rglob("*.json"))
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))


def threshold_config(root: Path, provider: str):
    lock=json.loads((root/"evaluation/threshold_lock.json").read_text(encoding="utf-8"))
    cfg=lock["models"][provider]
    return float(cfg["mia_execute_threshold"]), float(cfg["mia_ambiguity_margin"])


def index_requests(path: Path):
    out={}
    for row in read_jsonl(path):
        out[row["case"]["request_id"]]=row
    assert len(out)==720
    return out


def index_raw(path: Path):
    out={}
    for row in read_jsonl(path):
        if row.get("system_id")=="mia-v2":
            out[row["request_id"]]=row["raw"]
    assert len(out)==720
    return out


def index_predictions(path: Path):
    rows=[Prediction.from_dict(x) for x in read_jsonl(path)]
    return rows

def best_gold_and_mismatches(predicted: Intent, gold_payloads):
    pv=predicted.semantic_canonical()
    candidates=[]
    for payload in gold_payloads:
        gv=Intent.from_dict(payload).semantic_canonical()
        matches={slot: pv.get(slot)==gv.get(slot) for slot in INTENT_SLOT_WEIGHTS}
        weighted=sum(INTENT_SLOT_WEIGHTS[s] for s,v in matches.items() if v)
        candidates.append((weighted,gv,matches))
    if not candidates:
        return None, []
    _,gold,matches=max(candidates,key=lambda x:x[0])
    return gold,[slot for slot,ok in matches.items() if not ok]


def wrong_intent_report(predictions, benchmark):
    case_index=benchmark_index(benchmark)
    test=[p for p in predictions if case_index[(p.case_id,p.utterance_id)]["split"]=="test"]
    gold_execute=[p for p in test if case_index[(p.case_id,p.utterance_id)]["gold_action"]=="execute"]
    all_exec=[p for p in test if p.predicted_action==Action.EXECUTE]
    exact_exec=0
    wrong=[]
    slot_counts=Counter()
    primary_slot_counts=Counter()
    for p in gold_execute:
        if p.predicted_action!=Action.EXECUTE:
            continue
        case=case_index[(p.case_id,p.utterance_id)]
        exact,_,_=intent_scores(p.predicted_intent,case.get("gold_intents",[]))
        if exact:
            exact_exec+=1
            continue
        mismatches=[]
        if p.predicted_intent is not None:
            _,mismatches=best_gold_and_mismatches(p.predicted_intent,case.get("gold_intents",[]))
        for slot in mismatches:
            slot_counts[slot]+=1
        if mismatches:
            primary=max(mismatches,key=lambda s:INTENT_SLOT_WEIGHTS.get(s,0))
            primary_slot_counts[primary]+=1
        wrong.append({
            "case_id":p.case_id,
            "utterance_id":p.utterance_id,
            "mismatched_slots":mismatches,
        })
    exact_all=0
    for p in all_exec:
        case=case_index[(p.case_id,p.utterance_id)]
        if case["gold_action"]!="execute":
            continue
        exact,_,_=intent_scores(p.predicted_intent,case.get("gold_intents",[]))
        exact_all+=int(exact)
    ordering_limit_only=sum(
        bool(x["mismatched_slots"]) and set(x["mismatched_slots"]).issubset({"ordering","limit"})
        for x in wrong
    )
    core_semantic=len(wrong)-ordering_limit_only
    return {
        "gold_execute_utterances":len(gold_execute),
        "executed_gold_execute_utterances":sum(p.predicted_action==Action.EXECUTE for p in gold_execute),
        "exact_intent_executions_on_gold_execute":exact_exec,
        "wrong_intent_executions_on_gold_execute":len(wrong),
        "wrong_intent_execution_rate_on_answerable":len(wrong)/len(gold_execute) if gold_execute else None,
        "ordering_limit_only_wrong_intent_executions":ordering_limit_only,
        "core_semantic_wrong_intent_executions":core_semantic,
        "core_semantic_wrong_intent_rate_on_answerable":core_semantic/len(gold_execute) if gold_execute else None,
        "all_predicted_execute_utterances":len(all_exec),
        "execution_semantic_precision":exact_all/len(all_exec) if all_exec else None,
        "mismatched_slot_counts_nonexclusive":dict(sorted(slot_counts.items())),
        "primary_mismatch_slot_counts":dict(sorted(primary_slot_counts.items())),
        "wrong_rows":wrong,
    }



def ignore_unresolved_fields(raw: dict[str,Any]) -> dict[str,Any]:
    value=deepcopy(raw)
    for item in value.get("candidates",[]):
        s=item.get("semantic_intent_json")
        if not isinstance(s,str):
            continue
        try:
            semantic=json.loads(s)
        except Exception:
            continue
        for k in ("unresolved_dimension_mentions","unresolved_filter_value_attributes","unresolved_explicit_version_metrics"):
            semantic[k]=[]
        item["semantic_intent_json"]=json.dumps(semantic,sort_keys=True,separators=(",",":"))
    return value


def valid_candidates_without_deferred_precedence(raw, *, input_record, registry):
    # Preserve explicit top-level dispositions. Only remove candidate-level
    # "leading deferred interpretation blocks weaker valid candidate" precedence.
    if raw.get("outside_contract") or raw.get("missing_capability") is not None:
        return parse_generation_v2(raw,input_record=input_record,registry=registry)
    valid=[]
    for item in raw.get("candidates",[]):
        one={"outside_contract":False,"missing_capability":None,"candidates":[deepcopy(item)]}
        g=parse_generation_v2(one,input_record=input_record,registry=registry)
        valid.extend(g.candidates)
    if valid:
        return GenerationResult(tuple(valid),None,False,"mia-v2-provider",input_record["request_id"])
    return parse_generation_v2(raw,input_record=input_record,registry=registry)


class FilterValidator:
    def __init__(self, keep: set[str] | None):
        self.base=Validator()
        self.keep=keep
    def validate(self,intent,registry,context):
        vals=self.base.validate(intent,registry,context)
        if self.keep is None:
            return vals
        return tuple(v for v in vals if v.family in self.keep)


class AnalysisAssurer(Assurer):
    def __init__(self, te, ta, keep_families: set[str] | None):
        super().__init__(te,ta)
        self.validator=FilterValidator(keep_families)


def decision_row(*,provider,variant,adapter,generation,registry,te,ta,keep_families=None):
    case=adapter["case"]
    context=Context.from_dict(case["context"])
    decision=AnalysisAssurer(te,ta,keep_families).decide_generation(
        generation,registry,context,request_id=case["request_id"])
    return {
        "prediction":{
            "run_id":f"final-component-{provider}",
            "system_id":f"mia-v2-{variant}",
            "model_id":adapter["model_id"],
            "case_id":case["case_id"],
            "utterance_id":case["utterance_id"],
            "predicted_action":decision.action.value,
            "predicted_reason_code":decision.reason_code,
            "predicted_intent":decision.intent.canonical() if decision.intent else None,
            "confidence":float(decision.confidence or 0),
            "execution_correct":None,"provenance_complete":bool(decision.trace.get("registry_hash")),
            "generated_query":None,"latency_ms":0,"input_tokens":0,"output_tokens":0,"cost_usd":0,
        },
        "decision":decision,
    }


def parser_stage(raw,generation,registry):
    if raw.get("outside_contract"):
        return "model_outside_contract"
    if raw.get("missing_capability") is not None:
        return "model_missing_capability"
    if generation.candidates:
        return None
    sems=[]
    for item in raw.get("candidates",[]):
        if item.get("semantic_decode_error") or not isinstance(item.get("semantic_intent_json"),str):
            return "parser_malformed_or_decode"
        try: sems.append(json.loads(item["semantic_intent_json"]))
        except Exception: return "parser_malformed_or_decode"
    if any(s.get("unresolved_dimension_mentions") or s.get("unresolved_filter_value_attributes") or s.get("unresolved_explicit_version_metrics") for s in sems):
        return "parser_unresolved_slot"
    if generation.missing_capability is not None:
        if generation.missing_capability.code=="GAP_COMPOSITION":
            return "parser_static_composition_gap"
        return "parser_registry_gap"
    return "parser_other_fail_closed"


def provenance_label(raw,generation,decision,registry):
    p=parser_stage(raw,generation,registry)
    if p: return p
    if decision.violations:
        return "validator:"+decision.violations[0].family
    if decision.action==Action.CLARIFY:
        if "distinguishing_slot" in decision.trace:
            return "ambiguity_margin"
        return "execution_threshold_or_no_valid_candidate"
    if decision.action==Action.COVERAGE_GAP:
        return "compiler_capability_or_gap"
    if decision.action==Action.REJECT:
        return "other_reject"
    return "execute"


def b4_prediction_from_value(v):
    return Prediction.from_dict({**v,"system_id":v["system_id"] if str(v["system_id"]).startswith("mia-") else "mia-"+str(v["system_id"])})


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--provider",choices=["gpt","claude"],required=True)
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--mia-artifact",type=Path,required=True)
    ap.add_argument("--b4-artifact",type=Path,required=True)
    ap.add_argument("--b2-eval",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    root=args.repo_root.resolve()
    benchmark=load_jsonl(root/"benchmark/canonical_cases.v1.1.jsonl")
    req=index_requests(args.mia_artifact/"requests.jsonl")
    raw=index_raw(args.mia_artifact/"raw_outputs.jsonl")
    te,ta=threshold_config(root,args.provider)

    variants=defaultdict(list)
    provenance=Counter()
    residual=[]
    for rid,adapter in req.items():
        case=adapter["case"]
        registry=Registry.load(root/f"registries/{case['domain']}.json")
        full_gen=parse_generation_v2(raw[rid],input_record=case,registry=registry)
        full=decision_row(provider=args.provider,variant="full",adapter=adapter,generation=full_gen,registry=registry,te=te,ta=ta)
        variants["full"].append(full["prediction"])
        if full["decision"].action!=Action.EXECUTE:
            provenance[provenance_label(raw[rid],full_gen,full["decision"],registry)]+=1

        ignore_gen=parse_generation_v2(ignore_unresolved_fields(raw[rid]),input_record=case,registry=registry)
        variants["ignore-unresolved-slots"].append(decision_row(provider=args.provider,variant="ignore-unresolved-slots",adapter=adapter,generation=ignore_gen,registry=registry,te=te,ta=ta)["prediction"])

        relaxed=valid_candidates_without_deferred_precedence(raw[rid],input_record=case,registry=registry)
        variants["no-deferred-precedence"].append(decision_row(provider=args.provider,variant="no-deferred-precedence",adapter=adapter,generation=relaxed,registry=registry,te=te,ta=ta)["prediction"])

        variants["all-validators-off"].append(decision_row(provider=args.provider,variant="all-validators-off",adapter=adapter,generation=full_gen,registry=registry,te=te,ta=ta,keep_families=set())["prediction"])
        variants["grain-only"].append(decision_row(provider=args.provider,variant="grain-only",adapter=adapter,generation=full_gen,registry=registry,te=te,ta=ta,keep_families={"grain"})["prediction"])

    scored={}
    summaries={}
    for name,rows in variants.items():
        sr=[r for r in scored_rows([Prediction.from_dict(x) for x in rows],benchmark) if r["split"]=="test"]
        scored[name]=sr
        summaries[name]=summarize(sr)

    sealed_predictions=index_predictions(args.mia_artifact/"predictions.jsonl")
    sealed=[r for r in scored_rows(sealed_predictions,benchmark) if r["split"]=="test"]
    if [r["predicted_action"] for r in sorted(scored["full"],key=lambda x:(x["case_id"],x["utterance_id"]))] != [r["predicted_action"] for r in sorted(sealed,key=lambda x:(x["case_id"],x["utterance_id"]))]:
        raise RuntimeError("full replay does not match sealed actions")

    b4_predictions=[b4_prediction_from_value(x) for x in read_jsonl(args.b4_artifact/"predictions.jsonl")]
    b4=[r for r in scored_rows(b4_predictions,benchmark) if r["split"]=="test"]

    b2_predictions=[]
    for rid,adapter in req.items():
        case=adapter["case"]
        registry=Registry.load(root/f"registries/{case['domain']}.json")
        pred,_=normalize_b2_matched(
            raw[rid],case,registry,
            run_id=f"b2-matched-{args.provider}",
            model_id=adapter["model_id"],
        )
        pred_for_scoring=dict(pred)
        pred_for_scoring["system_id"]="mia"
        b2_predictions.append(Prediction.from_dict(pred_for_scoring))

    wrong_intent={
        "final_mia":wrong_intent_report(sealed_predictions,benchmark),
        "b2_matched":wrong_intent_report(b2_predictions,benchmark),
        "b4_matched":wrong_intent_report(b4_predictions,benchmark),
    }

    # Residual unsafe executions under sealed final MIA.
    raw_by={(r["case_id"],r["utterance_id"]):r for r in sealed}
    for r in sealed:
        if r["gold_action"]=="execute" or r["predicted_action"]!="execute":
            continue
        rid=r["utterance_id"]
        adapter=req[rid]
        registry=Registry.load(root/f"registries/{adapter['case']['domain']}.json")
        g=parse_generation_v2(raw[rid],input_record=adapter["case"],registry=registry)
        supports=sorted([x.support for x in g.candidates],reverse=True)
        residual.append({
            "case_id":r["case_id"],"utterance_id":r["utterance_id"],"gold_action":r["gold_action"],
            "candidate_count":len(g.candidates),"leading_support":supports[0] if supports else None,
            "second_support":supports[1] if len(supports)>1 else None,
        })

    gold_clarify=[r for r in b4 if r["gold_action"]=="clarify"]
    b4_clarify_pred=[r for r in gold_clarify if r["predicted_action"]=="clarify"]
    b4_reason={
        "gold_clarify_n":len(gold_clarify),
        "predicted_clarify_on_gold_clarify_n":len(b4_clarify_pred),
        "reason_exact_n":sum(bool(r["reason_exact"]) for r in b4_clarify_pred),
        "reason_exact_rate_conditional_on_predicted_clarify":(
            sum(bool(r["reason_exact"]) for r in b4_clarify_pred)/len(b4_clarify_pred) if b4_clarify_pred else None
        ),
    }

    report={
        "schema_version":"1.0.0",
        "study_id":"final-component-analysis",
        "evidence_class":"secondary_posthoc_sealed_trace_component_analysis",
        "provider":args.provider,
        "provider_calls":0,
        "summaries":summaries,
        "decision_provenance_non_execute":dict(sorted(provenance.items())),
        "residual_unsafe_executions":residual,
        "residual_unsafe_summary":{
            "utterances":len(residual),
            "with_second_valid_candidate":sum(x["candidate_count"]>=2 for x in residual),
            "single_valid_candidate":sum(x["candidate_count"]==1 for x in residual),
            "gold_action_counts":dict(sorted(Counter(x["gold_action"] for x in residual).items())),
            "leading_support_min":min((x["leading_support"] for x in residual if x["leading_support"] is not None), default=None),
            "leading_support_max":max((x["leading_support"] for x in residual if x["leading_support"] is not None), default=None),
        },
        "wrong_intent_execution":wrong_intent,
        "confusion":{
            "final_mia":confusion_matrix(sealed),
            "b4_matched":confusion_matrix(b4),
        },
        "b4_matched_secondary":{
            "paraphrase_consistency":summarize(b4)["paraphrase_consistency"],
            "reason_code_accuracy":summarize(b4)["reason_code_accuracy"],
            "clarify_reason_alignment":b4_reason,
        },
        "b2_matched_evaluation_artifact":read_first_json(args.b2_eval),
        "interpretation":{
            "ignore_unresolved_slots":"Only dimension, filter-value, and explicit-version unresolved arrays are cleared; other parser behavior is unchanged.",
            "no_deferred_precedence":"Explicit top-level outside-contract/missing-capability dispositions are retained, but a candidate-level deferred parse can no longer block a lower-support valid candidate.",
            "all_validators_off":"The deterministic Validator emits no violations; static downstream compiler-capability checks remain active; thresholds remain frozen.",
            "grain_only":"Only Validator family 'grain' is retained; static downstream compiler-capability checks and thresholds remain active.",
        },
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
