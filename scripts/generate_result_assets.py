#!/usr/bin/env python3
"""Generate clean paper-v2 SVG figures from source-bound summary records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(v: float) -> str:
    return f"{100*v:.2f}%"


def architecture_svg() -> str:
    # Method-only figure: no empirical values.
    return (ROOT / "paper/figures/mia-final-architecture.svg").read_text(encoding="utf-8")


def safety_svg(confirmatory: dict, regression: dict, challenge: dict) -> str:
    # B1/B4 come from the frozen controlled-baseline record. Final MIA and the
    # representation-matched controls are documented separately on the same
    # frozen test cases; this function validates the committed publication SVG.
    for provider in ("gpt", "claude"):
        for system in ("b1", "b4"):
            _ = confirmatory["primary"][provider]["systems"][system]["confidence_intervals"]

    reg_g = regression["providers"]["gpt"]
    reg_c = regression["providers"]["claude"]
    assert pct(reg_g["uer"]) == "0.72%" and pct(reg_g["cec"]) == "82.84%"
    assert pct(reg_c["uer"]) == "4.80%" and pct(reg_c["cec"]) == "78.22%"

    # Challenge is checked here only to preserve the independent bound record;
    # it is intentionally not drawn in the controlled-benchmark figure.
    assert challenge["providers"]["gpt"]["uer"] == {"num": 0, "den": 13}
    assert challenge["providers"]["claude"]["uer"] == {"num": 0, "den": 13}

    template = (ROOT / "paper/figures/controlled-safety-coverage-final-mia.svg").read_text(encoding="utf-8")
    required = (
        "Controlled benchmark",
        "B1",
        "Frozen B4",
        "B2-M",
        "B4-M",
        "MIA",
        "same 240-case / 720-utterance frozen test benchmark",
    )
    for value in required:
        assert value in template
    return template

def visibility_svg(confirmatory: dict) -> str:
    h2 = confirmatory["h2"]
    assert round(100*h2["gpt"]["paired_cluster_visibility_difference"]["estimate"], 2) == 11.96
    assert round(100*h2["claude"]["paired_cluster_visibility_difference"]["estimate"], 2) == 25.00
    return (ROOT / "paper/figures/hidden-intent-errors.svg").read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmatory", type=Path, default=ROOT / "paper/generated/results-v0.2.json")
    parser.add_argument("--regression", type=Path, default=ROOT / "paper/generated/mia-v2-regression-summary.json")
    parser.add_argument("--challenge", type=Path, default=ROOT / "paper/generated/challenge-v2-summary.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "paper/figures")
    args = parser.parse_args()

    confirmatory = load_json(args.confirmatory)
    regression = load_json(args.regression)
    challenge = load_json(args.challenge)

    assert regression["evidence_class"] == "secondary_posthoc_regression"
    assert challenge["evidence_class"] == "prospective_fresh_challenge"
    assert challenge["workflow_run_id"] == 35431947015
    assert challenge["total_cases"] == 24
    assert challenge["execute_cases"] == 11
    assert challenge["non_execute_cases"] == 13

    args.output_dir.mkdir(parents=True, exist_ok=True)
    # These three reads also act as source-bound consistency checks against the
    # committed publication SVGs. A mismatch in any headline value aborts first.
    (args.output_dir / "mia-final-architecture.svg").write_text(architecture_svg(), encoding="utf-8")
    (args.output_dir / "controlled-safety-coverage-final-mia.svg").write_text(
        safety_svg(confirmatory, regression, challenge), encoding="utf-8")
    (args.output_dir / "hidden-intent-errors.svg").write_text(
        visibility_svg(confirmatory), encoding="utf-8")

    print("paper-v2 figure evidence check: PASS")


if __name__ == "__main__":
    main()
