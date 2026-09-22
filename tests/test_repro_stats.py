import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from repro_stats import fast_paired_delta


def _row(case_id, utterance_id, predicted_action="reject"):
    return {
        "case_id": case_id,
        "utterance_id": utterance_id,
        "gold_action": "reject",
        "predicted_action": predicted_action,
        "intent_exact": False,
    }


class FastPairedDeltaIdentityTest(unittest.TestCase):
    def test_rejects_different_row_identity_with_same_case_set(self):
        left = [_row("c1", "u1"), _row("c1", "u2")]
        right = [_row("c1", "u1"), _row("c1", "u3")]
        with self.assertRaisesRegex(ValueError, "identical \\(case_id, utterance_id\\) rows"):
            fast_paired_delta(left, right, "unsafe_execution_rate", samples=10)

    def test_accepts_same_rows_in_different_order(self):
        left = [_row("c1", "u1"), _row("c2", "u2")]
        right = [_row("c2", "u2"), _row("c1", "u1")]
        out = fast_paired_delta(left, right, "unsafe_execution_rate", samples=10)
        self.assertEqual(out["estimate"], 0.0)


if __name__ == "__main__":
    unittest.main()
