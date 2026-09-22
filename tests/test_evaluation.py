import unittest

from mia.evaluation import select_threshold


class ThresholdCalibrationTest(unittest.TestCase):
    def test_cost_matrix_is_indexed_by_prediction_then_gold(self):
        rows = [
            {"case_id": "unsafe", "gold_action": "reject", "fallback_action": "reject",
             "valid": True, "confidence": .9, "margin": .9, "intent_exact": False},
            {"case_id": "gold", "gold_action": "execute", "fallback_action": "reject",
             "valid": True, "confidence": .8, "margin": .8, "intent_exact": True},
        ]
        rows += [
            {"case_id": f"safe-{i}", "gold_action": "reject", "fallback_action": "reject",
             "valid": False, "confidence": .8, "margin": .8, "intent_exact": False}
            for i in range(9)
        ]
        costs = {
            "execute": {"execute": 0, "clarify": 0, "reject": 1, "coverage_gap": 0},
            "clarify": {a: 0 for a in ("execute", "clarify", "reject", "coverage_gap")},
            "reject": {"execute": 100, "clarify": 0, "reject": 0, "coverage_gap": 0},
            "coverage_gap": {a: 0 for a in ("execute", "clarify", "reject", "coverage_gap")},
        }
        selected = select_threshold(rows, b1_uer=1.0, b1_cec=0.1, costs=costs)
        # The frozen row=prediction orientation favors executing both (cost 1)
        # over rejecting the gold Execute row (cost 100).
        self.assertEqual(selected["tau_e"], .8)

    def test_threshold_search_includes_execute_nothing_boundary(self):
        rows = [
            {"case_id": "unsafe", "gold_action": "reject", "fallback_action": "reject",
             "valid": True, "confidence": 1.0, "margin": 1.0, "intent_exact": False},
        ]
        actions = ("execute", "clarify", "reject", "coverage_gap")
        costs = {gold: {predicted: 0 for predicted in actions} for gold in actions}
        selected = select_threshold(rows, b1_uer=1.0, b1_cec=0.0, costs=costs)
        self.assertTrue(selected["feasible"])
        self.assertGreater(selected["tau_e"], 1.0)

    def test_wrong_intent_execution_adds_frozen_primary_loss(self):
        rows = [
            {"case_id": "wrong", "gold_action": "execute", "fallback_action": "clarify",
             "valid": True, "confidence": .9, "margin": .9, "intent_exact": False},
        ]
        actions = ("execute", "clarify", "reject", "coverage_gap")
        costs = {predicted: {gold: 0 for gold in actions} for predicted in actions}
        costs["clarify"]["execute"] = 20
        selected = select_threshold(rows, b1_uer=1.0, b1_cec=1.0, costs=costs)
        self.assertEqual(selected["development_primary_cost"], 12)


if __name__ == "__main__":
    unittest.main()
