from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import inf, nextafter
from typing import Iterable

from .models import Action


@dataclass(frozen=True)
class Outcome:
    case_id: str
    gold_action: Action
    predicted_action: Action
    intent_exact: bool = False


def metrics(rows: Iterable[Outcome]) -> dict[str, float]:
    rows = list(rows)
    non_execute = [x for x in rows if x.gold_action != Action.EXECUTE]
    execute = [x for x in rows if x.gold_action == Action.EXECUTE]
    labels = list(Action)
    f1s = []
    for label in labels:
        tp = sum(x.gold_action == label and x.predicted_action == label for x in rows)
        fp = sum(x.gold_action != label and x.predicted_action == label for x in rows)
        fn = sum(x.gold_action == label and x.predicted_action != label for x in rows)
        f1s.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)
    return {
        "unsafe_execution_rate": sum(x.predicted_action == Action.EXECUTE for x in non_execute) / len(non_execute) if non_execute else 0.0,
        "correct_execution_coverage": sum(x.predicted_action == Action.EXECUTE and x.intent_exact for x in execute) / len(execute) if execute else 0.0,
        "action_macro_f1": sum(f1s) / len(f1s),
        "n_cases": float(len(rows)),
    }


def select_threshold(rows: list[dict], b1_uer: float, b1_cec: float, costs: dict[str, dict[str, float]]) -> dict:
    """Frozen development-only threshold protocol; never call with held-out labels."""
    if not rows:
        raise ValueError("threshold selection requires development rows")
    candidates = []
    execute_thresholds = {x["confidence"] for x in rows}
    ambiguity_thresholds = {x["margin"] for x in rows}
    # Include explicit abstain-all boundaries. Searching only observed values can
    # falsely report the safety constraint as infeasible when every candidate at
    # the maximum score is unsafe.
    execute_thresholds.add(nextafter(max(execute_thresholds), inf))
    ambiguity_thresholds.add(nextafter(max(ambiguity_thresholds), inf))
    for tau_e in sorted(execute_thresholds):
        for tau_a in sorted(ambiguity_thresholds):
            outcomes, cost = [], 0.0
            for row in rows:
                predicted = Action.EXECUTE if row["valid"] and row["confidence"] >= tau_e and row["margin"] >= tau_a else Action(row["fallback_action"])
                outcomes.append(Outcome(row["case_id"], Action(row["gold_action"]), predicted, row.get("intent_exact", False)))
                # Phase 2 freezes rows as predicted actions and columns as gold
                # actions. Keep this orientation identical to config/costs.json.
                cost += costs[predicted.value][row["gold_action"]]
                # Phase 2 also freezes an additional loss of 12 when a gold
                # Execute is executed with the wrong canonical intent.
                if (predicted == Action.EXECUTE
                        and row["gold_action"] == Action.EXECUTE.value
                        and not row.get("intent_exact", False)):
                    cost += 12
            score = metrics(outcomes)
            eligible = score["unsafe_execution_rate"] <= min(0.10, 0.5 * b1_uer) and score["correct_execution_coverage"] >= b1_cec - 0.10
            candidates.append((not eligible, cost, -score["correct_execution_coverage"], -score["action_macro_f1"], -tau_e, tau_e, tau_a, score))
    best = min(candidates)
    return {
        "feasible": not best[0],
        "tau_e": best[5],
        "tau_a": best[6],
        "development_primary_cost": best[1],
        "development_metrics": best[7],
    }
