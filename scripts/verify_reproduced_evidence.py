#!/usr/bin/env python3
"""Verify regenerated paper evidence against the machine-readable paper-number contract."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def close(actual, expected, tol=1e-12, label="value"):
    if actual is None or expected is None:
        if actual != expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")
        return
    if not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tol):
        raise AssertionError(f"{label}: {actual} != {expected}")


def pct2(value):
    return round(100.0 * float(value) + 1e-12, 2)


def assert_pct(actual, expected, label):
    got = pct2(actual)
    if got != float(expected):
        raise AssertionError(f"{label}: {got:.2f}% != {float(expected):.2f}%")


def summary_from_eval(report):
    return next(iter(report["systems"].values()))["summary"]


def ci_from_eval(report):
    return next(iter(report["systems"].values()))["confidence_intervals"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generated", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, default=Path("."))
    args = ap.parse_args()

    g = args.generated
    root = args.repo_root.resolve()
    numbers = load(root / "paper_numbers.json")
    hist_ref = load(root / "evidence/historical-controlled-results.json")
    final_ref = load(root / "evidence/mia-v2-regression-summary.json")
    topn_ref = load(root / "evidence/topn-defect-sensitivity.json")
    challenge_v2_ref = load(root / "evidence/challenge-v2-summary.json")
    challenge_v1 = load(root / "evidence/challenge-evaluation.run35403416152.json")

    hist = {p: load(g / f"historical-{p}.json") for p in ("gpt", "claude")}
    final = load(g / "final-v2/mia-v2-regression-evaluation.json")
    b2 = {p: load(g / f"b2-{p}/evaluation.json") for p in ("gpt", "claude")}
    b4 = {p: load(g / f"b4-{p}/evaluation.json") for p in ("gpt", "claude")}
    mechanism = {p: load(g / f"mechanism-{p}/report.json") for p in ("gpt", "claude")}
    component = {p: load(g / f"component-{p}.json") for p in ("gpt", "claude")}
    clean = {p: load(g / f"clean-{p}.json") for p in ("gpt", "claude")}
    topn = load(g / "topn.json")
    challenge_v2 = load(g / "challenge-v2.json")
    h2 = load(g / "h2.json")

    # Tables 2 and 3 point estimates.
    for provider in ("gpt", "claude"):
        for sid in ("b0", "b1", "b2", "b3", "b4", "mia"):
            got = hist[provider]["systems"][sid]["summary"]
            ref = hist_ref["primary"][provider]["systems"][sid]["summary"]
            for key in ("unsafe_execution_rate", "correct_execution_coverage", "action_macro_f1"):
                close(got[key], ref[key], label=f"historical {provider}/{sid}/{key}")

        got = final["providers"][provider]["v2_summary"]
        ref = final_ref["providers"][provider]["v2"]
        close(got["unsafe_execution_rate"], ref["uer"], label=f"final {provider} UER")
        close(got["correct_execution_coverage"], ref["cec"], label=f"final {provider} CEC")
        close(got["action_macro_f1"], ref["action_macro_f1"], label=f"final {provider} Macro-F1")

    matched_expected = {
        "gpt": {
            "b2": (0.17026378896882495, 0.8316831683168316, 0.5883217563843668),
            "b4": (0.06235011990407674, 0.8316831683168316, 0.805077441802567),
        },
        "claude": {
            "b2": (0.19424460431654678, 0.7986798679867987, 0.6046172106823815),
            "b4": (0.04316546762589928, 0.7821782178217822, 0.8024102140823077),
        },
    }
    for provider in ("gpt", "claude"):
        for sid, report in (("b2", b2[provider]), ("b4", b4[provider])):
            s = summary_from_eval(report)
            for key, expected in zip(
                ("unsafe_execution_rate", "correct_execution_coverage", "action_macro_f1"),
                matched_expected[provider][sid],
            ):
                close(s[key], expected, 1e-10, f"matched {provider}/{sid}/{key}")

    # Final-v2 95% CIs reported in Results.
    for provider in ("gpt", "claude"):
        ci = final["providers"][provider]["v2_bootstrap"]
        spec = numbers["final_mia_ci"][provider]
        assert_pct(ci["unsafe_execution_rate"]["low"], spec["uer_95"][0], f"{provider} final UER CI low")
        assert_pct(ci["unsafe_execution_rate"]["high"], spec["uer_95"][1], f"{provider} final UER CI high")
        assert_pct(ci["correct_execution_coverage"]["low"], spec["cec_95"][0], f"{provider} final CEC CI low")
        assert_pct(ci["correct_execution_coverage"]["high"], spec["cec_95"][1], f"{provider} final CEC CI high")

    # Table 4 deterministic replay rows.
    for provider in ("gpt", "claude"):
        spec = numbers["table4_replay_uer_percent"][provider]
        for variant in ("full", "no-margin", "no-tau-e", "drop-grain"):
            assert_pct(
                mechanism[provider]["summaries"][variant]["unsafe_execution_rate"],
                spec[variant],
                f"Table 4 {provider}/{variant}",
            )
        for variant in ("all-validators-off", "grain-only", "ignore-unresolved-slots"):
            assert_pct(
                component[provider]["summaries"][variant]["unsafe_execution_rate"],
                spec[variant],
                f"Table 4 {provider}/{variant}",
            )

    # Figure 2 / paired final-MIA minus B4-Matched effect and case-level McNemar.
    for provider in ("gpt", "claude"):
        paired = mechanism[provider]["paired"]["mia_minus_b4_matched"]
        spec = numbers["matched_assurer_effect"][provider]
        uer = paired["unsafe_execution_rate"]
        assert_pct(uer["estimate"], spec["uer_delta_pp"], f"{provider} paired UER delta")
        assert_pct(uer["low"], spec["uer_ci_95_pp"][0], f"{provider} paired UER CI low")
        assert_pct(uer["high"], spec["uer_ci_95_pp"][1], f"{provider} paired UER CI high")
        mc = paired["unsafe_case_mcnemar"]
        if mc["a_only_unsafe"] != spec["mia_only_unsafe_cases"]:
            raise AssertionError(f"{provider}: MIA-only unsafe cases mismatch")
        if mc["b_only_unsafe"] != spec["b4_only_unsafe_cases"]:
            raise AssertionError(f"{provider}: B4-only unsafe cases mismatch")
        close(mc["exact_two_sided_p"], spec["mcnemar_p"], 1e-12, f"{provider} matched McNemar p")

    # Heterogeneity claim: GPT B4-Matched Reject->Execute errors.
    gpt_b4_conf = next(iter(b4["gpt"]["systems"].values()))["confusion_matrix"]
    spec = numbers["matched_assurer_effect"]["gpt"]
    reject_execute = gpt_b4_conf["reject"]["execute"]
    unsafe_total = sum(
        row["execute"] for gold, row in gpt_b4_conf.items() if gold != "execute"
    )
    if reject_execute != spec["reject_to_execute_utterances_b4"]:
        raise AssertionError(f"GPT B4-Matched Reject->Execute: {reject_execute}")
    if unsafe_total != spec["total_unsafe_utterances_b4"]:
        raise AssertionError(f"GPT B4-Matched unsafe total: {unsafe_total}")

    # Clean-prompt UER and CEC.
    for provider in ("gpt", "claude"):
        spec = numbers["clean_prompt"][provider]
        assert_pct(clean[provider]["clean_summary"]["unsafe_execution_rate"], spec["uer_percent"], f"{provider} clean UER")
        assert_pct(clean[provider]["clean_summary"]["correct_execution_coverage"], spec["cec_percent"], f"{provider} clean CEC")

    # Top-N defect-excluded final-MIA CEC, strict precision, and wrong-intent execution.
    for provider in ("gpt", "claude"):
        got = topn["providers"][provider]["final_mia_without_topn"]
        spec = numbers["topn_defect_excluded_final_mia"][provider]
        assert_pct(got["correct_execution_coverage"], spec["cec_percent"], f"{provider} top-N excluded CEC")
        assert_pct(got["strict_execution_precision"], spec["strict_execution_precision_percent"], f"{provider} strict precision")
        if got["wrong_intent_executions_on_answerable"] != spec["wrong_intent_execute"]["num"]:
            raise AssertionError(f"{provider}: wrong-intent numerator mismatch")
        if got["answerable_denominator"] != spec["wrong_intent_execute"]["den"]:
            raise AssertionError(f"{provider}: wrong-intent denominator mismatch")

    # Defect-excluded H2 is recomputed from the frozen per-row confirmatory H2 record.
    for provider in ("gpt", "claude"):
        got = topn["providers"][provider]["h2_without_topn"]
        spec = numbers["h2"]["topn_excluded"][provider]
        if got["groups_remaining"] != spec["groups"]:
            raise AssertionError(f"{provider}: H2 group count mismatch")
        if got["execution_visible_groups"] != spec["execution_visible"]:
            raise AssertionError(f"{provider}: H2 execution-visible mismatch")
        if got["intent_visible_groups"] != spec["intent_visible"]:
            raise AssertionError(f"{provider}: H2 intent-visible mismatch")
        assert_pct(got["visibility_gain"], spec["gain_pp"], f"{provider} H2 gain")
        assert_pct(got["bootstrap_95"]["low"], spec["ci_95_pp"][0], f"{provider} H2 CI low")
        assert_pct(got["bootstrap_95"]["high"], spec["ci_95_pp"][1], f"{provider} H2 CI high")
        close(got["mcnemar"]["p_value"], spec["mcnemar_p"], 1e-12, f"{provider} H2 McNemar")

        ref = topn_ref["h2_without_topn"][provider]
        close(got["visibility_gain"], ref["gain"], label=f"{provider} top-N H2 frozen summary")

    # Original H2 is a frozen confirmatory record (not reconstructed from historical predictions).
    for provider in ("gpt", "claude"):
        spec = numbers["h2"]["original"][provider]
        if len({x["cluster_id"] for x in h2[provider]["details"]}) != spec["groups"]:
            raise AssertionError(f"{provider}: original H2 group count mismatch")
        assert_pct(
            h2[provider]["paired_cluster_visibility_difference"]["estimate"],
            spec["gain_pp"],
            f"{provider} original H2 gain",
        )

    # Challenge-v2 including Reject exact counts.
    for provider in ("gpt", "claude"):
        got = challenge_v2["providers"][provider]
        ref = challenge_v2_ref["providers"][provider]
        if got["action_exact"]["correct"] != ref["action_exact"]["num"] or got["action_exact"]["n"] != ref["action_exact"]["den"]:
            raise AssertionError(f"{provider}: challenge-v2 action exact mismatch")
        if got["uer"]["count"] != ref["uer"]["num"] or got["uer"]["n"] != ref["uer"]["den"]:
            raise AssertionError(f"{provider}: challenge-v2 UER mismatch")
        if got["cec"]["correct"] != ref["cec"]["num"] or got["cec"]["n"] != ref["cec"]["den"]:
            raise AssertionError(f"{provider}: challenge-v2 CEC mismatch")
        spec = numbers["challenge_v2"][provider]["reject_correct"]
        if got["reject_correct"]["num"] != spec["num"] or got["reject_correct"]["den"] != spec["den"]:
            raise AssertionError(f"{provider}: challenge-v2 Reject exact mismatch")

    # Challenge-v1 negative development evidence.
    if challenge_v1["resolved_n"] != numbers["challenge_v1"]["resolved_cases"]:
        raise AssertionError("challenge-v1 resolved denominator mismatch")
    for provider in ("gpt", "claude"):
        spec = numbers["challenge_v1"][provider]
        mia = challenge_v1["providers"][provider]["mia"]["resolved_action_exact"]
        b4c = challenge_v1["providers"][provider]["b4"]["resolved_action_exact"]
        if (mia["correct"], mia["n"]) != (spec["earlier_mia_correct"], numbers["challenge_v1"]["resolved_cases"]):
            raise AssertionError(f"{provider}: challenge-v1 earlier-MIA mismatch")
        if (b4c["correct"], b4c["n"]) != (spec["b4_correct"], numbers["challenge_v1"]["resolved_cases"]):
            raise AssertionError(f"{provider}: challenge-v1 B4 mismatch")

    # Reviewer-facing regenerated tables and Figures 2-3 must exist and be non-empty.
    assets = load(g / "paper-assets/paper-assets-values.json")
    for name in ("tables.md", "controlled-safety-coverage-final-mia.svg", "hidden-intent-errors.svg"):
        path = g / "paper-assets" / name
        if not path.exists() or path.stat().st_size == 0:
            raise AssertionError(f"missing regenerated paper asset: {name}")

    # Sanity-bind generated table values to recomputed reports.
    for provider in ("gpt", "claude"):
        for sid in ("b0", "b1", "b2", "b3", "b4", "mia"):
            got = assets["table2"][provider][sid]
            source = (
                final["providers"][provider]["v2_summary"]
                if sid == "mia"
                else hist[provider]["systems"][sid]["summary"]
            )
            close(got["uer"], source["unsafe_execution_rate"], label=f"asset table2 {provider}/{sid} UER")
            if sid != "b0":
                close(got["cec"], source["correct_execution_coverage"], label=f"asset table2 {provider}/{sid} CEC")

    print(json.dumps({
        "status": "pass",
        "scope": "paper quantitative evidence + all Round-2 listed claims + regenerated tables/figures",
        "provider_calls": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
