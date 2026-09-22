import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mia_v2_regression
import mia_v2_postpilot_smoke
from mia.phase5 import Prediction
from mia.registry import Registry
from mia.v2_system import decode_provider_output_v2


def test_v2_regression_preflight_is_720_calls_per_provider_and_no_auth():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        gpt = mia_v2_regression.prepare_only(ROOT, root / "gpt", "gpt")
        claude = mia_v2_regression.prepare_only(ROOT, root / "claude", "claude")
    assert gpt["provider_calls_permitted"] is False
    assert claude["provider_calls_permitted"] is False
    assert gpt["expected_provider_calls"] == 720
    assert claude["expected_provider_calls"] == 720
    assert gpt["hard_cap_usd"] == 4.0
    assert claude["hard_cap_usd"] == 8.0
    assert gpt["combined_hard_cap_usd"] == 12.0
    assert claude["combined_hard_cap_usd"] == 12.0


def test_v2_regression_uses_frozen_v1_thresholds_for_comparability():
    gpt = mia_v2_regression.threshold_config(ROOT, "gpt")
    claude = mia_v2_regression.threshold_config(ROOT, "claude")
    assert gpt == {"execute_threshold": 0.96, "ambiguity_margin": 1.0}
    assert claude == {"execute_threshold": 0.6, "ambiguity_margin": 0.0}


def test_mia_v2_system_id_is_prediction_compatible():
    registry = Registry.load(ROOT / "registries/saas/v1.json")
    record = {
        "request_id": "v2-regression-test#u0",
        "case_id": "v2-regression-test",
        "utterance_id": "v2-regression-test#u0",
        "domain": "saas",
        "request": "Show monthly recurring revenue by region for Q1 2026.",
        "context": {"role": "finance", "calendar_default": "calendar", "timezone": "UTC"},
        "registry_hash": registry.snapshot_hash,
    }
    raw = decode_provider_output_v2({
        "candidates": [{
            "semantic_intent": {
                "metrics": ["mrr"],
                "dimensions": ["region"],
                "filters": [],
                "time": {
                    "start": "2026-01-01",
                    "end": "2026-03-31",
                    "temporal_grain": "month",
                    "calendar_id": None,
                },
                "explicit_metric_versions": [],
                "unresolved_explicit_version_metrics": [],
                "ordering": [],
                "limit": None,
            },
            "support": 0.99,
            "evidence": [],
        }],
        "missing_capability": None,
        "outside_contract": False,
    })
    adapter = mia_v2_regression.build_adapter_input_v2(
        record,
        registry,
        provider="gpt",
        model_id=mia_v2_regression.SETTINGS["gpt"]["model_id"],
        decoding=mia_v2_regression.SETTINGS["gpt"]["decoding"],
        prompts_root=ROOT / "prompts/v2",
    )
    prediction, _ = mia_v2_regression.normalize_success(
        "gpt", adapter, raw,
        {"usage": {}, "cost_usd": 0},
        0.0, ROOT,
    )
    parsed = Prediction.from_dict(prediction)
    assert parsed.system_id == "mia-v2"


def test_v2_regression_workflow_requires_manual_authorization_and_fixed_cap():
    workflow = (ROOT / ".github/workflows/mia-v2-regression.yml").read_text()
    assert "I AUTHORIZE THE MIA-V2 REGRESSION" in workflow
    assert 'float(os.environ["AUTHORIZED_CAP"]) == 12.0' in workflow
    assert "--maximum-spend-usd 4.0" in workflow
    assert "--maximum-spend-usd 8.0" in workflow
    assert "workflow_dispatch" in workflow


def test_postpilot_smoke_preflight_is_small_and_credential_free():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        gpt = mia_v2_postpilot_smoke.prepare_only(ROOT, root / "gpt", "gpt")
        claude = mia_v2_postpilot_smoke.prepare_only(ROOT, root / "claude", "claude")
    assert gpt["provider_calls_permitted"] is False
    assert claude["provider_calls_permitted"] is False
    assert gpt["request_count"] == 8
    assert claude["request_count"] == 8
    assert gpt["hard_cap_usd"] == 0.25
    assert claude["hard_cap_usd"] == 0.75
    assert gpt["request_ids"] == list(mia_v2_postpilot_smoke.SMOKE_REQUEST_IDS)


def test_postpilot_smoke_workflow_has_unescaped_actions_expressions():
    workflow = (ROOT / ".github/workflows/mia-v2-postpilot-smoke.yml").read_text()
    assert "\\${{" not in workflow
    assert "I AUTHORIZE THE MIA-V2 HARDENING SMOKE" in workflow
    assert "--maximum-spend-usd 0.25" in workflow
    assert "--maximum-spend-usd 0.75" in workflow
