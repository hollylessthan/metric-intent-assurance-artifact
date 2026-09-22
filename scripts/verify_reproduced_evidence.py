#!/usr/bin/env python3
"""Verify regenerated quantitative evidence against frozen reader-facing records."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def close(a,b,tol=1e-12):
    if a is None or b is None:
        if a!=b: raise AssertionError(f"{a!r} != {b!r}")
    elif not math.isclose(float(a),float(b),rel_tol=0,abs_tol=tol):
        raise AssertionError(f"{a} != {b}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--generated",type=Path,required=True)
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    args=ap.parse_args()
    g=args.generated; root=args.repo_root
    hist=load(root/"evidence/historical-controlled-results.json")
    final_ref=load(root/"evidence/mia-v2-regression-summary.json")
    topn_ref=load(root/"evidence/topn-defect-sensitivity.json")
    chal_ref=load(root/"evidence/challenge-v2-summary.json")

    # Historical Table 2 rows.
    for provider in ("gpt","claude"):
        got=load(g/f"historical-{provider}.json")
        for sid in ("b0","b1","b2","b3","b4","mia"):
            gs=got["systems"][sid]["summary"]
            rs=hist["primary"][provider]["systems"][sid]["summary"]
            for k in ("unsafe_execution_rate","correct_execution_coverage","action_macro_f1"):
                close(gs[k],rs[k])

    # Final MIA row and bootstrap source recomputation.
    final=load(g/"final-v2/mia-v2-regression-evaluation.json")
    for provider in ("gpt","claude"):
        got=final["providers"][provider]["v2_summary"]
        ref=final_ref["providers"][provider]["v2"]
        close(got["unsafe_execution_rate"],ref["uer"])
        close(got["correct_execution_coverage"],ref["cec"])
        close(got["action_macro_f1"],ref["action_macro_f1"])

    # Matched controls (Table 3).
    expected={
      "gpt":{"b2":(0.17026378896882495,0.8316831683168316,0.5883217563843668),
             "b4":(0.06235011990407674,0.8316831683168316,0.805077441802567)},
      "claude":{"b2":(0.19424460431654678,0.7986798679867987,0.6046172106823815),
                "b4":(0.04316546762589928,0.7821782178217822,0.8024102140823077)}
    }
    for provider in ("gpt","claude"):
        for sid in ("b2","b4"):
            rep=load(g/f"{sid}-{provider}/evaluation.json")
            only=next(iter(rep["systems"].values()))["summary"]
            exp=expected[provider][sid]
            for got,want in zip((only["unsafe_execution_rate"],only["correct_execution_coverage"],only["action_macro_f1"]),exp):
                close(got,want,1e-10)

    # Prompt sensitivity (§6.7).
    clean_expected={"gpt":(0.007194244604316547,0.014388489208633094),
                    "claude":(0.047961630695443645,0.05995203836930456)}
    for provider,(base,clean) in clean_expected.items():
        rep=load(g/f"clean-{provider}.json")
        close(rep["final_summary"]["unsafe_execution_rate"],base)
        close(rep["clean_summary"]["unsafe_execution_rate"],clean)

    # Component evidence.
    comp_expected={"gpt":(0.06235011990407674,0.05755395683453238,0.007194244604316547),
                   "claude":(0.2446043165467626,0.11510791366906475,0.047961630695443645)}
    for provider,(ignore_u,all_off,grain_only) in comp_expected.items():
        rep=load(g/f"component-{provider}.json")
        close(rep["summaries"]["ignore-unresolved-slots"]["unsafe_execution_rate"],ignore_u,1e-10)
        close(rep["summaries"]["all-validators-off"]["unsafe_execution_rate"],all_off,1e-10)
        close(rep["summaries"]["grain-only"]["unsafe_execution_rate"],grain_only,1e-10)

    # Figure 3 / H2 source record.
    h2=load(g/"h2.json")
    close(h2["gpt"]["paired_cluster_visibility_difference"]["estimate"],0.11956521739130432)
    close(h2["claude"]["paired_cluster_visibility_difference"]["estimate"],0.25)

    # Top-N sensitivity.
    topn=load(g/"topn.json")
    for provider in ("gpt","claude"):
        got=topn["providers"][provider]["h2_without_topn"]
        ref=topn_ref["h2_without_topn"][provider]
        close(got["paired_cluster_visibility_difference"]["estimate"],ref["gain"])
        close(got["paired_cluster_visibility_difference"]["low"],ref["ci_low"])
        close(got["paired_cluster_visibility_difference"]["high"],ref["ci_high"])

    # Challenge-v2 (§6.6).
    chal=load(g/"challenge-v2.json")
    for provider in ("gpt","claude"):
        ref=chal_ref["providers"][provider]
        got=chal["providers"][provider]
        if got["action_exact"]["correct"]!=ref["action_exact"]["num"] or got["action_exact"]["n"]!=ref["action_exact"]["den"]:
            raise AssertionError(f"{provider}: challenge action exact mismatch")
        if got["uer"]["count"]!=ref["uer"]["num"] or got["uer"]["n"]!=ref["uer"]["den"]:
            raise AssertionError(f"{provider}: challenge UER mismatch")
        if got["cec"]["correct"]!=ref["cec"]["num"] or got["cec"]["n"]!=ref["cec"]["den"]:
            raise AssertionError(f"{provider}: challenge CEC mismatch")
    print(json.dumps({"status":"pass","scope":"paper quantitative evidence","provider_calls":0},sort_keys=True))

if __name__=="__main__": main()
