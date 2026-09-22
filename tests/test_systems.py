import json
from math import inf, nextafter
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mia.assurance import Assurer
from mia.models import Action
from mia.phase5 import Prediction
from mia.phase5_systems import (
    CALLABLE_SYSTEMS,
    GOLD_KEYS,
    build_adapter_input,
    build_model_case,
    decode_provider_output,
    derive_b3,
    normalize_baseline_output,
    normalize_mia_output,
    output_schema,
    PROMPT_VERSIONS,
    split_cached_case,
)
from mia.registry import Registry


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import phase5_anthropic_adapter
import phase5_build_requests
import phase5_openai_adapter
import phase5_prepare
import phase5_provider_smoke


class Phase5SystemsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = [json.loads(line) for line in
            (ROOT / "benchmarks/phase4/final/canonical_cases.v1.1.jsonl").read_text().splitlines()]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            phase5_prepare.prepare(ROOT, ROOT / "benchmarks/phase4/final/canonical_cases.v1.1.jsonl", output)
            cls.inputs = [json.loads(line) for line in (output / "development.jsonl").read_text().splitlines()]
        cls.record = cls.inputs[0]
        cls.registry = Registry.load(ROOT / cls.record["registry_path"])
        cls.intent = next(case for case in cls.cases if case["case_id"] == cls.record["case_id"])["gold_intents"][0]

    def test_every_callable_system_has_strict_schema_and_prompt(self):
        def assert_closed_objects(schema):
            if isinstance(schema, dict):
                schema_type = schema.get("type")
                if schema_type == "object" or (
                        isinstance(schema_type, list) and "object" in schema_type):
                    self.assertFalse(schema.get("additionalProperties", True))
                    self.assertEqual(set(schema.get("required", [])),
                        set(schema.get("properties", {})))
                for child in schema.values():
                    assert_closed_objects(child)
            elif isinstance(schema, list):
                for child in schema:
                    assert_closed_objects(child)

        for system in CALLABLE_SYSTEMS:
            schema = output_schema(system)
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
            assert_closed_objects(schema)
            adapter_input = build_adapter_input(system, self.record, self.registry,
                provider="gpt", model_id="gpt-5.4-mini-2026-03-17",
                decoding={"max_output_tokens": 1800, "reasoning_effort": "none", "temperature": 0},
                prompts_root=ROOT / "prompts/phase5")
            self.assertFalse(phase5_build_requests.forbidden_paths(adapter_input))

    def test_intent_prompts_freeze_nested_canonical_shapes(self):
        self.assertEqual(PROMPT_VERSIONS["b0"], "phase5-b0-v1")
        for system in ("b1", "b2", "b4"):
            self.assertEqual(PROMPT_VERSIONS[system], f"phase5-{system}-v4")
            prompt = (ROOT / "prompts/phase5" / f"{system}.txt").read_text()
            self.assertIn("provenance: array of unique registry ID strings", prompt)
            self.assertIn("output_grain: object with exactly entity and temporal", prompt)
            self.assertIn("metric_versions: array of objects", prompt)
            self.assertIn("direct portable JSON object", prompt)
            self.assertIn("Q1 2026", prompt)
            self.assertIn("Otherwise use month when month is supported", prompt)
            self.assertIn("Do not infer output cadence from a metric name", prompt)
            self.assertIn("Construct entity mechanically", prompt)
            self.assertIn("output_grain.entity must be account", prompt)
            self.assertIn("every filter attribute ID", prompt)
        self.assertEqual(PROMPT_VERSIONS["mia"], "phase5-mia-v5")
        mia_prompt = (ROOT / "prompts/phase5/mia.txt").read_text()
        self.assertIn("unique applicable version ID", mia_prompt)
        self.assertIn("entity must exactly equal the entity", mia_prompt)
        self.assertIn("Temporal grain is the output cadence", mia_prompt)
        self.assertIn("Q1 2026", mia_prompt)
        self.assertIn("Otherwise use month when month is supported", mia_prompt)
        self.assertIn("Do not infer output cadence from a metric name", mia_prompt)
        self.assertIn("Construct entity mechanically", mia_prompt)
        self.assertIn("output_grain.entity must be account", mia_prompt)

    def test_portable_wire_intent_decodes_without_semantic_change(self):
        canonical = json.loads(json.dumps(self.intent))
        wire = {
            "metrics": canonical["metrics"],
            "dimensions": canonical["dimensions"],
            "filters": [{
                "attribute": item["attribute"],
                "operator": item["operator"],
                "value_json": json.dumps(item["value"], sort_keys=True, separators=(",", ":")),
                "value_type": item["value_type"],
                "scope": item["scope"],
            } for item in canonical["filters"]],
            "time": canonical["time"],
            "output_grain": canonical["output_grain"],
            "comparison_json": (None if canonical["comparison"] is None else
                json.dumps(canonical["comparison"], sort_keys=True, separators=(",", ":"))),
            "ordering": canonical["ordering"],
            "limit": canonical["limit"],
            "version_policy": canonical["version_policy"],
            "metric_versions": [
                {"metric_id": key, "version_id": value}
                for key, value in canonical["metric_versions"].items()
            ],
            "subject_scope": [
                {"key": key, "value_json": json.dumps(value, sort_keys=True, separators=(",", ":"))}
                for key, value in canonical["subject_scope"].items()
            ],
            "provenance": canonical["provenance"],
        }
        decoded = decode_provider_output("b2", {
            "decision": "execute", "intent": wire, "confidence": .9, "evidence": [],
        })
        self.assertNotIn("intent", decoded)
        self.assertEqual(json.loads(decoded["intent_json"]), canonical)

    def test_cache_split_is_information_preserving_and_gold_free(self):
        case = build_model_case("b2", self.record, self.registry)
        stable, dynamic = split_cached_case(case)
        self.assertEqual({**stable, **dynamic}, case)
        self.assertEqual(set(stable), {"domain", "registry_hash", "registry"})
        self.assertNotIn("request", stable)
        self.assertFalse(phase5_build_requests.forbidden_paths([stable, dynamic]))

    def test_b0_receives_physical_view_and_other_systems_receive_registry(self):
        b0 = build_model_case("b0", self.record, self.registry)
        b2 = build_model_case("b2", self.record, self.registry)
        self.assertIn("backends", b0["registry"]["metrics"][0])
        self.assertNotIn("aliases", b0["registry"]["metrics"][0])
        self.assertIn("aliases", b2["registry"]["metrics"][0])

    def test_gold_fields_fail_closed_at_any_depth(self):
        poisoned = {**self.record, "nested": {"gold_action": "execute"}}
        with self.assertRaises(ValueError):
            build_model_case("b2", poisoned, self.registry)

    def test_baselines_preserve_causal_output_boundaries(self):
        encoded = json.dumps(self.intent)
        b1 = normalize_baseline_output("b1", {"decision": "execute", "intent_json": encoded,
            "confidence": .8, "evidence": []}, self.record, run_id="r", model_id="m")
        self.assertEqual(b1["predicted_action"], "execute")
        self.assertIsNotNone(b1["predicted_intent"])
        b3 = derive_b3({**b1, "system_id": "b2"}, threshold=.9)
        self.assertEqual(b3["predicted_action"], "clarify")
        self.assertIsNone(b3["predicted_intent"])
        b4 = normalize_baseline_output("b4", {"action": "coverage_gap", "reason_code": "missing",
            "intent_json": None, "clarification_question": None, "missing_concept": "x",
            "confidence": .7, "evidence": []}, self.record, run_id="r", model_id="m")
        self.assertEqual(b4["predicted_action"], "coverage_gap")

    def test_mia_model_generates_candidates_but_local_assurer_decides(self):
        raw = {"candidates": [{"intent_json": json.dumps(self.intent), "support": .95,
            "evidence": [self.intent["metrics"][0]]}], "missing_capability": None,
            "outside_contract": False}
        prediction, trace = normalize_mia_output(raw, self.record, self.registry,
            run_id="r", model_id="m", execute_threshold=.8, ambiguity_margin=.15)
        self.assertEqual(prediction["predicted_action"], "execute")
        self.assertEqual(trace["decision"]["reason_code"], "EXE_UNIQUE_SUPPORTED")

    def test_assurer_replays_execute_nothing_boundary(self):
        raw = {"candidates": [{"intent_json": json.dumps(self.intent), "support": 1.0,
            "evidence": [self.intent["metrics"][0]]}], "missing_capability": None,
            "outside_contract": False}
        prediction, trace = normalize_mia_output(raw, self.record, self.registry,
            run_id="r", model_id="m", execute_threshold=nextafter(1.0, inf),
            ambiguity_margin=0.0)
        self.assertEqual(prediction["predicted_action"], "clarify")
        replayed = Assurer().replay(trace["decision"]["trace"], self.registry)
        self.assertEqual(replayed.action, Action.CLARIFY)

    def test_prediction_contract_requires_b0_query(self):
        value = {"run_id": "r", "system_id": "b0", "model_id": "m", "case_id": "c",
            "utterance_id": "c#u0", "predicted_action": "execute", "confidence": .9}
        with self.assertRaises(ValueError):
            Prediction.from_dict(value)
        parsed = Prediction.from_dict({**value, "generated_query": "SELECT 1"})
        self.assertEqual(parsed.predicted_action, Action.EXECUTE)

    def test_held_out_requests_require_a_bound_threshold_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            phase5_prepare.prepare(ROOT, ROOT / "benchmarks/phase4/final/canonical_cases.v1.1.jsonl", output)
            with self.assertRaises(ValueError):
                phase5_build_requests.build(ROOT, output / "test.jsonl", output / "requests",
                    provider="gpt", model_id="gpt-5.4-mini-2026-03-17",
                    decoding={"max_output_tokens": 1800, "reasoning_effort": "none", "temperature": 0},
                    systems=("b2",), threshold_lock=None)

    def test_threshold_lock_binds_the_held_out_model(self):
        study = json.loads((ROOT / "config/phase5-study.json").read_text())
        value = {
            "status": "locked", "study_id": study["study_id"],
            "benchmark_git_blob_sha": study["benchmark"]["git_blob_sha"],
            "models": {
                "gpt": {"model_id": "gpt-5.4-mini-2026-03-17",
                    "b3_execute_threshold": .8, "mia_execute_threshold": .9,
                    "mia_ambiguity_margin": .1},
                "claude": {"model_id": "claude-sonnet-5",
                    "b3_execute_threshold": .8, "mia_execute_threshold": .9,
                    "mia_ambiguity_margin": .1},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "lock.json"
            lock.write_text(json.dumps(value))
            parsed = phase5_build_requests.verify_threshold_lock(
                lock, study, provider="gpt", model_id="gpt-5.4-mini-2026-03-17")
            self.assertEqual(parsed["status"], "locked")
            with self.assertRaises(ValueError):
                phase5_build_requests.verify_threshold_lock(
                    lock, study, provider="gpt", model_id="unfrozen-model")

    def test_provider_payload_builders_are_network_free_and_frozen(self):
        openai_input = build_adapter_input("b2", self.record, self.registry,
            provider="gpt", model_id="gpt-5.4-mini-2026-03-17",
            decoding={"max_output_tokens": 1800, "reasoning_effort": "none", "temperature": 0},
            prompts_root=ROOT / "prompts/phase5")
        openai_payload = phase5_openai_adapter.build_payload(openai_input)
        self.assertFalse(openai_payload["store"])
        self.assertTrue(openai_payload["text"]["format"]["strict"])
        self.assertEqual(openai_payload["input"][0]["role"], "developer")
        self.assertEqual(openai_payload["input"][1]["role"], "user")
        self.assertIn("prompt_cache_key", openai_payload)
        self.assertLessEqual(len(openai_payload["prompt_cache_key"]), 64)
        self.assertEqual(openai_payload["prompt_cache_key"],
            phase5_openai_adapter.build_payload(openai_input)["prompt_cache_key"])
        schema = openai_payload["text"]["format"]["schema"]
        self.assertIn("intent", schema["properties"])
        self.assertNotIn("intent_json", schema["properties"])
        claude_input = build_adapter_input("mia", self.record, self.registry,
            provider="claude", model_id="claude-sonnet-5",
            decoding={"max_output_tokens": 1800, "reasoning_effort": "low", "temperature": None},
            prompts_root=ROOT / "prompts/phase5")
        claude_payload = phase5_anthropic_adapter.build_payload(claude_input)
        self.assertEqual(claude_payload["thinking"], {"type": "adaptive"})
        self.assertEqual(claude_payload["output_config"]["effort"], "low")
        self.assertEqual(claude_payload["system"][-1]["cache_control"], {"type": "ephemeral"})

    def test_non_scored_smoke_fixture_is_isolated(self):
        record, registry = phase5_provider_smoke.smoke_record(ROOT)
        self.assertEqual(record["split"], "non_scored_smoke")
        self.assertTrue(record["case_id"].startswith("phase5-smoke-"))
        self.assertEqual(record["registry_hash"], registry.snapshot_hash)

    def test_provider_smoke_has_fixed_independent_hard_caps(self):
        self.assertEqual(phase5_provider_smoke.SETTINGS["gpt"]["hard_cap_usd"], .25)
        self.assertEqual(phase5_provider_smoke.SETTINGS["claude"]["hard_cap_usd"], .50)
        self.assertEqual(sum(
            item["hard_cap_usd"] for item in phase5_provider_smoke.SETTINGS.values()), .75)
        workflow = (ROOT / ".github/workflows/phase5-provider-smoke.yml").read_text()
        self.assertIn('default: "0.75"', workflow)
        self.assertIn('== 0.75', workflow)

    def test_smoke_records_one_semantic_failure_and_finishes_all_calls(self):
        calls = []

        def fake_run(command, *, input, text, capture_output, env, check):
            adapter_input = json.loads(input)
            system = adapter_input["system_id"]
            calls.append(system)
            evidence = {"system_id": system, "outcome": "success", "cost_usd": 0,
                "usage": {"input_tokens": 1, "cached_input_tokens": 0,
                    "cache_write_input_tokens": 0, "output_tokens": 1}}
            with Path(env["MIA_PROVIDER_EVIDENCE_LOG"]).open("a") as stream:
                stream.write(json.dumps(evidence) + "\n")
            intent = json.loads(json.dumps(self.intent))
            if system == "b0":
                raw = {"decision": "execute", "sql": "SELECT 1", "confidence": .9,
                    "evidence": []}
            elif system in {"b1", "b2"}:
                if system == "b1":
                    intent["provenance"] = {"invalid": "shape"}
                raw = {"decision": "execute", "intent_json": json.dumps(intent),
                    "confidence": .9, "evidence": []}
            elif system == "b4":
                raw = {"action": "execute", "reason_code": "model_execute",
                    "intent_json": json.dumps(intent), "clarification_question": None,
                    "missing_concept": None, "confidence": .9, "evidence": []}
            else:
                raw = {"candidates": [{"intent_json": json.dumps(intent), "support": .9,
                    "evidence": []}], "missing_capability": None, "outside_contract": False}
            return mock.Mock(returncode=0, stdout=json.dumps(raw), stderr="")

        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(phase5_provider_smoke.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(sys, "argv", ["phase5_provider_smoke.py", "--provider", "claude",
                    "--repo-root", str(ROOT), "--output-root", directory]), \
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}, clear=False):
            self.assertEqual(phase5_provider_smoke.main(), 2)
            report = json.loads((Path(directory) / "smoke_report.json").read_text())
        self.assertEqual(calls, list(CALLABLE_SYSTEMS))
        self.assertEqual(report["provider_successes"], len(CALLABLE_SYSTEMS))
        self.assertEqual(report["failures"][0]["system_id"], "b1")
        self.assertIn("b3", report["actions"])


if __name__ == "__main__":
    unittest.main()
