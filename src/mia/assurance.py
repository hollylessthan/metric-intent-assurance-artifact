from __future__ import annotations

from dataclasses import asdict, replace
from math import inf, isfinite, nextafter
from typing import Iterable

from .clarification import reason_for_slot, targeted_question
from .compilers import DuckDBCompiler, MetricFlowCompiler, UnsupportedIntentError
from .models import Action, Candidate, Context, Decision, Intent, MissingCapability, Violation
from .registry import Registry
from .validation import Validator


class Assurer:
    def __init__(
        self,
        execute_threshold: float = 0.8,
        ambiguity_margin: float = 0.15,
        compilers: Iterable[object] | None = None,
    ):
        # The development grid includes nextafter(1, +inf) as the explicit
        # execute-nothing boundary. Accept only that single representable value
        # above one; ordinary confidence thresholds remain in [0, 1].
        upper = nextafter(1.0, inf)
        if (not isfinite(execute_threshold) or not 0 <= execute_threshold <= upper
                or not isfinite(ambiguity_margin) or not 0 <= ambiguity_margin <= upper):
            raise ValueError("assurance thresholds must be in [0, nextafter(1, +inf)]")
        self.execute_threshold = execute_threshold
        self.ambiguity_margin = ambiguity_margin
        self.validator = Validator()
        self.compilers = tuple(compilers or (MetricFlowCompiler(), DuckDBCompiler()))

    def decide_generation(self, result, registry: Registry, context: Context, *, request_id: str | None = None) -> Decision:
        """Assure a frozen generation result while retaining its replay identity."""
        return self.decide(
            list(result.candidates), registry, context,
            missing_capability=result.missing_capability,
            outside_contract=result.outside_contract,
            generator_id=result.generator_id,
            request_id=request_id or result.request_id,
        )

    def decide(
        self,
        candidates: list[Candidate],
        registry: Registry,
        context: Context,
        *,
        missing_capability: MissingCapability | None = None,
        outside_contract: bool = False,
        generator_id: str = "unknown",
        request_id: str | None = None,
    ) -> Decision:
        classes = self._merge_equivalence_classes(candidates)
        evaluated = []
        for candidate in classes:
            violations = self.validator.validate(candidate.intent, registry, context)
            if not violations:
                violations = self._capability_violations(candidate.intent, registry)
            evaluated.append((candidate, violations))

        class_violations = {candidate.intent.equivalence_key: violations for candidate, violations in evaluated}
        trace = {
            "registry_hash": registry.snapshot_hash,
            "context": {
                "role": context.role,
                "org_scope": list(context.org_scope),
                "calendar_default": context.calendar_default,
                "timezone": context.timezone,
            },
            "generator": {"id": generator_id, "request_id": request_id},
            "thresholds": {"execute": self.execute_threshold, "ambiguity_margin": self.ambiguity_margin},
            "outside_contract": outside_contract,
            "candidates": [
                {
                    "support": candidate.support,
                    "equivalence_key": candidate.intent.equivalence_key,
                    "audit_hash": candidate.intent.audit_hash,
                    "intent": candidate.intent.canonical(),
                    "evidence": list(candidate.evidence),
                    "violations": [asdict(v) for v in class_violations.get(candidate.intent.equivalence_key, ())],
                }
                for candidate in sorted(candidates, key=lambda item: item.support, reverse=True)
            ],
            "equivalence_classes": [
                {
                    "support": candidate.support,
                    "equivalence_key": candidate.intent.equivalence_key,
                    "merged_audit_hash": candidate.intent.audit_hash,
                    "merged_provenance": list(candidate.intent.provenance),
                    "merged_evidence": list(candidate.evidence),
                    "violations": [asdict(v) for v in violations],
                }
                for candidate, violations in evaluated
            ],
        }
        if missing_capability:
            trace["missing_capability"] = asdict(missing_capability)

        if outside_contract:
            return Decision(Action.REJECT, "REJ_OUTSIDE_CONTRACT", trace=trace)

        all_violations = tuple(v for _, violations in evaluated for v in violations)

        # The most-supported semantic class is causally authoritative. Evidence
        # is merged within the class, but a lower-support meaning is never used
        # as an implicit substitute for an invalid leading meaning.
        if evaluated and evaluated[0][1]:
            leading = evaluated[0][0]
            return self._decision_for_violations(evaluated[0][1], leading.support, trace)

        valid = [candidate for candidate, violations in evaluated if not violations]
        if not valid:
            if missing_capability:
                return Decision(
                    Action.COVERAGE_GAP, missing_capability.code,
                    missing_concept=missing_capability.concept, violations=all_violations, trace=trace,
                )
            if all_violations:
                return self._decision_for_violations(all_violations, 0.0, trace)
            return Decision(
                Action.CLARIFY, "CLR_METRIC_IDENTITY",
                question="Which governed metric did you mean?", trace=trace,
            )

        if missing_capability:
            return Decision(
                Action.COVERAGE_GAP, missing_capability.code,
                missing_concept=missing_capability.concept, trace=trace,
            )

        if len(valid) > 1 and valid[0].support - valid[1].support < self.ambiguity_margin:
            slot, question = targeted_question([item.intent for item in valid])
            trace["distinguishing_slot"] = slot
            return Decision(
                Action.CLARIFY, reason_for_slot(slot), question=question,
                confidence=valid[0].support, trace=trace,
            )
        if valid[0].support < self.execute_threshold:
            return Decision(
                Action.CLARIFY, "CLR_METRIC_IDENTITY",
                question="Which governed metric and business scope did you mean?",
                confidence=valid[0].support, trace=trace,
            )
        return Decision(
            Action.EXECUTE, "EXE_UNIQUE_SUPPORTED", intent=valid[0].intent,
            confidence=valid[0].support, trace=trace,
        )

    def replay(self, trace: dict, registry: Registry) -> Decision:
        """Recompute a decision from its complete stored trace."""
        if trace.get("registry_hash") != registry.snapshot_hash:
            raise ValueError("trace was produced against a different registry snapshot")
        context = Context.from_dict(trace["context"])
        candidates = [
            Candidate(Intent.from_dict(item["intent"]), item["support"], tuple(item.get("evidence", [])))
            for item in trace.get("candidates", [])
        ]
        missing = trace.get("missing_capability")
        missing_capability = (
            MissingCapability(missing["code"], missing["concept"], tuple(missing.get("evidence", [])))
            if missing else None
        )
        generator = trace.get("generator", {})
        thresholds = trace["thresholds"]
        replay_assurer = Assurer(thresholds["execute"], thresholds["ambiguity_margin"], self.compilers)
        return replay_assurer.decide(
            candidates, registry, context,
            missing_capability=missing_capability,
            outside_contract=bool(trace.get("outside_contract", False)),
            generator_id=generator.get("id", "unknown"),
            request_id=generator.get("request_id"),
        )

    def _capability_violations(self, intent: Intent, registry: Registry) -> tuple[Violation, ...]:
        unsupported = []
        for compiler in self.compilers:
            try:
                compiler.compile(intent, registry)
            except UnsupportedIntentError as exc:
                unsupported.append(
                    Violation(
                        "backend_capability", "GAP_COMPOSITION",
                        f"{compiler.backend} cannot preserve this canonical intent: {exc}",
                        Action.COVERAGE_GAP, (compiler.backend,),
                    )
                )
        return tuple(unsupported)

    @staticmethod
    def _decision_for_violations(violations, confidence: float, trace: dict) -> Decision:
        rejects = tuple(v for v in violations if v.action == Action.REJECT)
        if rejects:
            reason = "REJ_OPERATION_INVALID" if rejects[0].code.startswith("INT_") else rejects[0].code
            return Decision(Action.REJECT, reason, violations=rejects, confidence=confidence, trace=trace)
        gaps = tuple(v for v in violations if v.action == Action.COVERAGE_GAP)
        if gaps:
            missing = gaps[0].object_ids[0] if gaps[0].object_ids else gaps[0].message
            return Decision(
                Action.COVERAGE_GAP, gaps[0].code, missing_concept=missing,
                violations=gaps, confidence=confidence, trace=trace,
            )
        clarifications = tuple(v for v in violations if v.action == Action.CLARIFY)
        if clarifications:
            return Decision(
                Action.CLARIFY, clarifications[0].code,
                question=Assurer._question_for_violation(clarifications[0].code),
                violations=clarifications, confidence=confidence, trace=trace,
            )
        raise AssertionError("violation set has no actionable violation")

    @staticmethod
    def _merge_equivalence_classes(candidates: list[Candidate]) -> list[Candidate]:
        grouped: dict[str, list[Candidate]] = {}
        for candidate in candidates:
            grouped.setdefault(candidate.intent.equivalence_key, []).append(candidate)
        merged = []
        for members in grouped.values():
            representative = max(members, key=lambda item: item.support)
            provenance = tuple(sorted({ref for item in members for ref in item.intent.provenance}))
            evidence = tuple(sorted({ref for item in members for ref in item.evidence}))
            merged_intent = replace(representative.intent, provenance=provenance)
            merged.append(Candidate(merged_intent, representative.support, evidence))
        return sorted(merged, key=lambda item: item.support, reverse=True)

    @staticmethod
    def _question_for_violation(code: str) -> str:
        questions = {
            "CLR_CALENDAR": "Which business calendar should be used?",
            "CLR_TIME_RANGE": "What exact time interval should be analyzed?",
            "CLR_GRAIN": "Should the result be daily, weekly, monthly, or quarterly?",
            "CLR_ENTITY_SCOPE": "Which business entity or population should the result cover?",
            "CLR_VERSION_POLICY": "Should this use effective-time, restated, or a named metric version?",
        }
        return questions.get(code, "Which supported interpretation did you mean?")
