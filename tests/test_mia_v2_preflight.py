import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mia_v2_preflight


def test_full_mia_v2_preflight_is_credential_free_and_covers_all_heldout_utterances():
    report = mia_v2_preflight.preflight(ROOT)
    assert report["status"] == "pass"
    assert report["provider_calls_permitted"] is False
    assert report["cases"] == 240
    assert report["utterances"] == 720
    assert report["providers"]["gpt"]["calls"] == 720
    assert report["providers"]["claude"]["calls"] == 720
    assert report["total_future_provider_calls"] == 1440
    assert sum(report["domain_utterances"].values()) == 720
