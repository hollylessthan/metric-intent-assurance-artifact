import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mia_v2_readiness_audit


def test_v2_readiness_audit_covers_entire_frozen_heldout_set():
    report = mia_v2_readiness_audit.audit(ROOT)
    assert report["heldout_cases"] == 240
    assert report["heldout_utterances"] == 720
    assert report["audited_gold_intents"] == 101
    assert report["provider_calls_permitted"] is False


def test_v2_readiness_audit_has_no_structural_blockers():
    report = mia_v2_readiness_audit.audit(ROOT)
    assert report["status"] == "pass"
    assert report["unexpected_error_count"] == 0
    assert report["mismatch_count"] == 0
    assert report["blocker_count"] == 0


def test_frozen_gold_has_no_mixed_entity_intent_dependency():
    report = mia_v2_readiness_audit.audit(ROOT)
    assert report["status_counts"].get("mixed_entity_deferred", 0) == 0
    assert report["mixed_entity_deferred_by_gold_action"] == {}
