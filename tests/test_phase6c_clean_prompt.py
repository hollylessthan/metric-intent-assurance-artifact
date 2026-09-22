from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "scripts" / "phase6c_clean_prompt_sensitivity.py"
    spec = importlib.util.spec_from_file_location("phase6c_clean_prompt_sensitivity_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_clean_prepare_requests_uses_original_builder_when_base_is_monkeypatched(tmp_path, monkeypatch):
    module = load_module()
    prompt_dir = tmp_path / "prompts" / "v2"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "mia_clean_sensitivity.txt").write_text("clean prompt\n", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()

    calls = []

    def fake_original(root, out, provider):
        calls.append((root, out, provider))
        return [{
            "prompt_version": "old",
            "system_prompt": "old prompt",
            "case": {"request_id": "req-1"},
        }]

    monkeypatch.setattr(module, "ORIGINAL_PREPARE_REQUESTS", fake_original)
    monkeypatch.setattr(module.base, "prepare_requests", module.clean_prepare_requests)

    rows = module.clean_prepare_requests(tmp_path, output, "gpt")

    assert len(calls) == 1
    assert rows[0]["prompt_version"] == module.CLEAN_PROMPT_VERSION
    assert rows[0]["system_prompt"] == "clean prompt\n"
    assert (output / "requests.jsonl").exists()
