#!/usr/bin/env python3
"""Build the frozen, synthetic Phase 4 pilot benchmark seed package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


DOMAIN_SPECS = {
    "saas": {
        "metric_entity": "subscription",
        "entities": ["subscription", "account", "workspace", "invoice"],
        "restricted_role": "finance",
        "ambiguous_alias": "revenue",
        "metrics": [
            "monthly_recurring_revenue", "annual_recurring_revenue", "new_mrr", "expansion_mrr",
            "contraction_mrr", "churned_mrr", "active_subscriptions", "new_subscriptions",
            "canceled_subscriptions", "trial_conversion_rate", "gross_revenue_retention",
            "net_revenue_retention", "average_revenue_per_account", "customer_acquisition_cost",
            "lifetime_value", "logo_churn_rate", "seat_utilization", "support_cost_per_account",
            "days_to_activate", "product_active_users", "feature_adoption_rate",
            "invoice_collection_rate", "overdue_balance", "recognized_revenue",
        ],
        "dimensions": [
            "region", "country", "industry", "company_size", "plan", "billing_cycle", "currency",
            "sales_segment", "acquisition_channel", "account_tier", "workspace_type", "product_edition",
            "contract_term", "renewal_cohort", "signup_cohort", "customer_status", "payment_method",
            "invoice_status", "cancellation_reason", "churn_reason", "feature_bundle", "seat_band",
            "usage_band", "success_plan", "partner_type", "sales_owner", "customer_age_band",
            "risk_band", "data_residency", "legal_entity",
        ],
    },
    "commerce": {
        "metric_entity": "order",
        "entities": ["order", "customer", "product", "shipment"],
        "restricted_role": "finance",
        "ambiguous_alias": "sales",
        "metrics": [
            "gross_sales", "net_sales", "orders", "units_sold", "average_order_value", "gross_margin",
            "discount_amount", "refund_amount", "refund_rate", "return_rate", "conversion_rate",
            "cart_abandonment_rate", "new_customers", "repeat_customers", "repeat_purchase_rate",
            "customer_acquisition_cost", "lifetime_value", "shipping_revenue", "shipping_cost",
            "fulfillment_time", "stockout_rate", "inventory_turnover", "tax_collected",
            "payment_failure_rate",
        ],
        "dimensions": [
            "region", "country", "sales_channel", "store", "brand", "category", "subcategory", "sku",
            "customer_segment", "loyalty_tier", "acquisition_channel", "campaign", "device_type",
            "payment_method", "currency", "promotion_type", "coupon", "order_status", "return_reason",
            "refund_reason", "shipping_method", "carrier", "warehouse", "fulfillment_type", "seller_type",
            "marketplace", "price_band", "customer_cohort", "product_launch_cohort", "tax_region",
        ],
    },
    "support": {
        "metric_entity": "ticket",
        "entities": ["ticket", "customer", "agent", "incident"],
        "restricted_role": "support_manager",
        "ambiguous_alias": "service level",
        "metrics": [
            "tickets_created", "tickets_resolved", "open_backlog", "first_response_time",
            "resolution_time", "sla_attainment", "reopen_rate", "escalation_rate", "deflection_rate",
            "customer_satisfaction", "net_promoter_score", "agent_utilization", "handle_time",
            "transfers_per_ticket", "self_service_sessions", "knowledge_article_views", "incident_count",
            "major_incident_count", "mean_time_to_recovery", "bug_link_rate", "customer_wait_time",
            "reply_count", "containment_rate", "support_cost",
        ],
        "dimensions": [
            "region", "country", "support_tier", "channel", "queue", "priority", "severity", "status",
            "issue_type", "product_area", "feature", "customer_segment", "account_tier", "language",
            "agent_team", "agent_tenure_band", "shift", "resolution_code", "escalation_reason",
            "contact_reason", "sla_policy", "entitlement", "incident_type", "root_cause", "bug_severity",
            "knowledge_category", "deflection_path", "sentiment_band", "customer_cohort", "contract_region",
        ],
    },
}

# Closed, registry-backed value vocabularies for every dimension used by a
# synthetic filter. These make filter support machine-checkable and keep the
# utterances enterprise-like instead of relying on placeholders such as
# ``target``.
FILTER_VALUE_CATALOG = {
    "saas": {
        "region": ["North America", "EMEA", "Asia Pacific"],
        "country": ["United States", "Germany", "Japan"],
        "industry": ["financial services", "healthcare", "software"],
        "company_size": ["small business", "mid-market", "enterprise"],
        "plan": ["Starter", "Growth", "Enterprise"],
        "billing_cycle": ["monthly", "annual"],
        "currency": ["USD", "EUR", "JPY"],
        "sales_segment": ["commercial", "mid-market", "strategic"],
        "acquisition_channel": ["organic", "paid search", "partner"],
        "account_tier": ["standard", "premium", "strategic"],
    },
    "commerce": {
        "region": ["North America", "EMEA", "Asia Pacific"],
        "country": ["United States", "Germany", "Japan"],
        "sales_channel": ["web", "mobile app", "marketplace"],
        "store": ["Seattle flagship", "Berlin Mitte", "Tokyo Shibuya"],
        "brand": ["Northstar", "Juniper", "Atlas"],
        "category": ["electronics", "home", "apparel"],
        "subcategory": ["headphones", "kitchenware", "outerwear"],
        "sku": ["NS-HEAD-100", "JN-KITCH-210", "AT-OUTER-310"],
        "customer_segment": ["new", "returning", "high value"],
        "loyalty_tier": ["silver", "gold", "platinum"],
    },
    "support": {
        "region": ["North America", "EMEA", "Asia Pacific"],
        "country": ["United States", "Germany", "Japan"],
        "support_tier": ["standard", "premium", "enterprise"],
        "channel": ["email", "chat", "phone"],
        "queue": ["billing", "technical", "account access"],
        "priority": ["low", "high", "urgent"],
        "severity": ["SEV-1", "SEV-2", "SEV-3"],
        "status": ["open", "pending", "resolved"],
        "issue_type": ["incident", "how-to", "billing inquiry"],
        "product_area": ["authentication", "reporting", "integrations"],
    },
}

MISSING_FILTER_VALUES = {
    "saas": ["active", "contract correction", "production rollout", "early access"],
    "commerce": ["approved", "executive exception", "holiday bundle", "supplier delay"],
    "support": ["approved", "overflow", "mitigation", "early access"],
}

MISSING_CONCEPTS = {
    "saas": [
        "committed_monthly_recurring_revenue", "product_qualified_accounts", "implementation_revenue", "contracted_seats",
        "parent_account", "reseller_region", "contract_motion", "renewal_manager",
        "promotion_state", "manual_override_reason", "implementation_stage", "feature_flag_cohort",
        "projected_mrr_after_churn", "net_retention_excluding_mergers", "blended_activation_score", "risk_adjusted_lifetime_value",
        "pre_acquisition_mrr_definition", "legacy_board_revenue_definition", "regional_arr_definition", "original_contract_value_version",
    ],
    "commerce": [
        "contribution_margin_after_returns", "marketplace_take_rate", "incremental_promotion_revenue", "committed_inventory_value",
        "parent_merchant", "reseller_market", "omnichannel_journey", "fulfillment_program",
        "fraud_review_state", "manual_price_override", "promotion_stack", "inventory_exception_reason",
        "demand_adjusted_net_sales", "return_adjusted_customer_value", "blended_fulfillment_score", "risk_adjusted_margin",
        "pre_migration_net_sales_definition", "legacy_board_margin_definition", "regional_gmv_definition", "original_refund_rate_version",
    ],
    "support": [
        "contractual_resolution_credit", "preventable_escalations", "engineering_assisted_resolutions", "proactive_incident_avoidance",
        "parent_customer", "outsourcer_region", "support_journey", "entitlement_program",
        "manual_sla_override", "temporary_queue_state", "incident_command_stage", "beta_support_cohort",
        "severity_adjusted_backlog", "business_impact_weighted_mttr", "blended_support_health", "risk_adjusted_support_cost",
        "pre_migration_sla_definition", "legacy_board_csat_definition", "regional_resolution_definition", "original_deflection_rate_version",
    ],
}

MISSING_VERSION_METRIC_INDEXES = {
    "saas": [0, 23, 1, 0],
    "commerce": [1, 5, 0, 8],
    "support": [5, 9, 4, 8],
}

FAMILIES = {
    "execute": [
        "exact_metric_grouped", "exact_metric_filtered", "explicit_version", "top_n",
        "named_version", "calendar_bound", "entity_join", "typed_filter",
        "multi_dimension", "closed_period",
    ],
    "clarify": ["ambiguous_metric", "ambiguous_calendar", "ambiguous_dimension", "ambiguous_filter", "ambiguous_version"],
    "reject": ["unauthorized_metric", "incompatible_dimension", "invalid_grain", "invalid_entity_path", "invalid_version"],
    "coverage_gap": ["missing_metric", "missing_dimension", "missing_filter", "missing_composition", "missing_version"],
}

REASON_CODES = {
    "execute": "EXE_UNIQUE_SUPPORTED",
    "clarify": "CLR_METRIC_IDENTITY",
    "reject": "REJ_AUTHORIZATION",
    "coverage_gap": "GAP_METRIC",
}


def slug_label(value: str) -> str:
    return value.replace("_", " ")


def canonical_hash(payload: dict) -> str:
    clean = {k: v for k, v in payload.items() if k != "snapshot_hash"}
    encoded = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def make_registry(domain: str, spec: dict) -> dict:
    dimensions = []
    for i, dim in enumerate(spec["dimensions"]):
        if i == 29:
            entity = "unlinked_entity"
        else:
            entity = spec["entities"][1 + (i % (len(spec["entities"]) - 1))] if i < 12 else spec["metric_entity"]
        dimensions.append({
            "id": dim,
            "name": slug_label(dim).title(),
            "type": "string",
            "entity": entity,
            **({"allowed_values": FILTER_VALUE_CATALOG[domain][dim]} if dim in FILTER_VALUE_CATALOG[domain] else {}),
            **({"policy_tags": ["sensitive"]} if i in {14, 25} else {}),
            "backends": {
                "metricflow": {"group_by": f"{entity}__{dim}", "filter_name": f"{entity}__{dim}"},
                "duckdb": {"table": f"{entity}_dim", "column": dim},
            },
        })

    metrics = []
    for i, metric in enumerate(spec["metrics"]):
        aliases = [slug_label(metric)]
        if i in {0, 1}:
            aliases.append(spec["ambiguous_alias"])
        versions = [{
            "id": f"{metric}.v1", "effective_from": "2024-01-01",
            "effective_to": None, "restated": False, "default": True,
            "backends": {
                "metricflow": {"metric_name": metric},
                    "duckdb": {"table": f"{domain}_facts", "column": metric, "aggregation": "SUM" if metric_additivity(metric) == "additive" else "AVG", "time_column": "event_date"},
            },
        }]
        if i % 4 == 0:
            versions.append({
                "id": f"{metric}.v2", "effective_from": "2024-01-01", "effective_to": None,
                "published_at": "2025-01-01", "restated": True, "default": False,
                "backends": {
                    "metricflow": {"metric_name": f"{metric}_v2"},
                    "duckdb": {"table": f"{domain}_facts", "column": f"{metric}_v2", "aggregation": "SUM" if metric_additivity(metric) == "additive" else "AVG", "time_column": "event_date"},
                },
            })
        metrics.append({
            "id": metric, "name": slug_label(metric).title(), "aliases": aliases, "active": True,
            "entity": spec["metric_entity"], "additivity": metric_additivity(metric),
            "allowed_dimensions": spec["dimensions"][:12] + [spec["dimensions"][29]],
            "allowed_grains": ["month", "quarter"], "allowed_calendars": ["calendar", "fiscal"],
            "versions": versions,
        })

    paths = []
    for entity in spec["entities"][1:]:
        paths.append({
            "id": f"{spec['metric_entity']}_to_{entity}", "from": spec["metric_entity"], "to": entity, "allowed": True,
            "backends": {"duckdb": {"from_table": f"{domain}_facts", "to_table": f"{entity}_dim", "from_key": f"{entity}_id", "to_key": f"{entity}_id"}},
        })
    restricted = [spec["metrics"][i] for i in range(0, 24, 4)]
    policies = [{
        "id": f"{metric}_{spec['restricted_role']}_only", "object_id": metric, "effect": "allow",
        "roles": [spec["restricted_role"]],
    } for metric in restricted]
    policies += [{
        "id": f"{dim}_sensitive", "object_id": dim, "effect": "allow", "roles": [spec["restricted_role"]],
    } for dim in (spec["dimensions"][14], spec["dimensions"][25])]

    registry = {
        "registry_id": f"{domain}-phase4-pilot", "snapshot_version": "1.1.0",
        "metrics": metrics, "dimensions": dimensions,
        "calendars": [
            {"id": "calendar", "name": "Gregorian calendar", "supported_grains": ["day", "week", "month", "quarter", "year"], "completeness_rules": ["closed"], "backends": {"metricflow": {"executable": True, "time_grains": {grain: f"metric_time__{grain}" for grain in ["day", "week", "month", "quarter", "year"]}}, "duckdb": {"calendar": "gregorian", "executable": True}}},
            {"id": "fiscal", "name": "Corporate fiscal calendar", "supported_grains": ["month", "quarter", "year"], "completeness_rules": ["closed"], "backends": {"metricflow": {"executable": True, "time_grains": {grain: f"metric_time__{grain}" for grain in ["month", "quarter", "year"]}}, "duckdb": {"calendar": "fiscal", "executable": True}}},
        ],
        "entity_paths": paths, "policies": policies,
    }
    registry["snapshot_hash"] = canonical_hash(registry)
    return registry


def metric_additivity(metric: str) -> str:
    """Return a conservative synthetic additivity class for registry realism."""
    non_additive_terms = (
        "rate", "retention", "margin", "average", "per_", "lifetime_value", "utilization",
        "time", "days_to", "csat", "nps", "score", "occupancy", "age",
    )
    snapshot_terms = ("balance", "backlog", "active_", "inventory")
    if any(term in metric for term in non_additive_terms):
        return "non_additive"
    if any(term in metric for term in snapshot_terms):
        return "semi_additive_time"
    return "additive"


def make_intent(metric: str, dimension: str, registry: dict, *, explicit: bool = False, ordering: bool = False) -> dict:
    metric_def = next(m for m in registry["metrics"] if m["id"] == metric)
    dim_def = next(d for d in registry["dimensions"] if d["id"] == dimension)
    version_id = metric_def["versions"][0]["id"]
    return {
        "metrics": [metric], "dimensions": [dimension], "filters": [],
        "time": {"start": "2026-01-01", "end": "2026-03-31", "calendar_id": "calendar", "temporal_grain": "month", "completeness": "closed", "timezone": "UTC"},
        "output_grain": {"entity": dim_def["entity"], "temporal": "month"}, "comparison": None,
        "ordering": [{"key": metric, "direction": "desc"}] if ordering else [],
        "limit": 10 if ordering else None,
        "version_policy": "explicit" if explicit else "effective_time",
        "metric_versions": {metric: version_id} if explicit else {}, "subject_scope": {},
        "provenance": [metric, version_id, dimension, "calendar"],
    }


def paraphrases(metric: str, dimension: str, domain: str, split: str, *, alias: str | None = None) -> list[str]:
    phrase = alias or slug_label(metric)
    dim = slug_label(dimension)
    if split == "development":
        return [
            f"Show {phrase} by {dim} for Q1 2026.",
            f"What was {phrase} in each {dim} during Q1 2026?",
            f"Break down {phrase} across {dim} for Q1 2026 in the {domain} business.",
        ]
    return [
        f"Report Q1 2026 {phrase} grouped by {dim}.",
        f"For Q1 2026, give me {phrase} for every {dim}.",
        f"In the {domain} business, compare {phrase} across {dim} for Q1 2026.",
    ]


def append_clause(utterances: list[str], clause: str) -> list[str]:
    return [text.rstrip(".?") + f" {clause}." for text in utterances]


def replace_clause(utterances: list[str], before: str, after: str) -> list[str]:
    replaced = [text.replace(before, after) for text in utterances]
    if any(old == new for old, new in zip(utterances, replaced)):
        raise ValueError(f"contrastive surface token not found: {before}")
    return replaced


def add_contrastive_pair(source: dict, target: dict, group: str, change: dict) -> None:
    """Attach one explicit, machine-checkable semantic mutation to both cases."""
    metadata = {
        "source_case_id": source["case_id"],
        "target_case_id": target["case_id"],
        "slot": change["slot"],
        "before": change["before"],
        "after": change["after"],
        "affected_paths": change.get("affected_paths", []),
        "alternative_paths": change.get("alternative_paths", []),
        "surface_before": change.get("surface_before"),
        "surface_after": change.get("surface_after"),
    }
    source["contrastive_group"] = group
    target["contrastive_group"] = group
    source["contrastive_change"] = metadata
    target["contrastive_change"] = metadata


def base_case(domain: str, action: str, index: int, family_index: int) -> dict:
    family = FAMILIES[action][family_index]
    split = "development" if family_index == 0 or (action == "execute" and family_index == 5) else "test"
    return {
        "case_id": f"{domain}-{action.replace('_', '')}-{index + 1:03d}", "domain": domain,
        "template_family": f"{domain}/{action}/{family}", "paraphrase_group": f"{domain}-{action}-{index + 1:03d}",
        "surface_template_set": f"{split}-surface-v2",
        "split": split, "gold_action": action, "primary_reason_code": REASON_CODES[action],
        "source_type": "synthetic_registry_derived", "annotation_status": "unadjudicated_seed",
    }


def build_domain_cases(domain: str, spec: dict, registry: dict) -> list[dict]:
    execute = []
    restricted = [spec["metrics"][i] for i in range(0, 24, 4)]
    for i in range(40):
        family_index = i // 4
        row = base_case(domain, "execute", i, family_index)
        if i < 4:
            metric = spec["metrics"][i % 2]
        elif i < 16:
            metric = spec["metrics"][i]
        elif i < 20:
            metric = spec["metrics"][[16, 20, 0, 4][i - 16]]
        elif i < 24:
            metric = spec["metrics"][[0, 4, 8, 12][i - 20]]
        else:
            metric = spec["metrics"][[16, 17, 18, 19, 20, 21, 22, 23, 2, 3, 5, 6, 7, 9, 10, 11][i - 24]]
        dimension = spec["dimensions"][(i + (1 if i >= 20 else 0)) % 10]
        row["context"] = {"role": spec["restricted_role"] if metric in restricted else "analyst", "calendar_default": "calendar", "timezone": "UTC"}
        if i < 4:
            row["context"]["role"] = spec["restricted_role"]
        row["utterances"] = paraphrases(metric, dimension, domain, row["split"])
        intent = make_intent(metric, dimension, registry, explicit=family_index in {2, 4, 7}, ordering=family_index == 3)
        if family_index in {1, 3, 7}:
            filter_dimension = spec["dimensions"][(i + 1) % 10]
            filter_value = FILTER_VALUE_CATALOG[domain][filter_dimension][i % len(FILTER_VALUE_CATALOG[domain][filter_dimension])]
            intent["filters"] = [{"attribute": filter_dimension, "operator": "eq", "value": filter_value, "value_type": "string", "scope": "row"}]
            if filter_dimension not in intent["provenance"]:
                intent["provenance"].append(filter_dimension)
            row["utterances"] = append_clause(
                row["utterances"], f"where {slug_label(filter_dimension)} is {filter_value}"
            )
        if family_index in {2, 4, 7}:
            row["utterances"] = [text.replace(slug_label(metric), f"{slug_label(metric)} version 1") for text in row["utterances"]]
        if family_index == 8:
            first = spec["dimensions"][i % 3]
            second = spec["dimensions"][(i % 3) + 3]
            intent["dimensions"] = [first, second]
            intent["output_grain"]["entity"] = next(d["entity"] for d in registry["dimensions"] if d["id"] == first)
            intent["provenance"][2:3] = [first, second]
            row["utterances"] = paraphrases(metric, f"{first}_and_{second}", domain, row["split"])
        if family_index == 9:
            row["utterances"] = append_clause(row["utterances"], "at monthly grain")
        row["gold_intents"] = [intent]
        row["provenance"] = {"registry_snapshot": f"registries/phase4/{domain}/v1.json", "registry_hash": registry["snapshot_hash"], "construction": "deterministic-template-v2"}
        row["execution_oracle"] = {
            "targets": ["metricflow", "duckdb"],
            "expected_status": "compile_and_execute_on_generated_phase4_fixtures",
        }
        execute.append(row)

    clarify = []
    for i in range(20):
        family_index = i // 4
        paired = execute[i]
        row = base_case(domain, "clarify", i, family_index)
        metric = paired["gold_intents"][0]["metrics"][0]
        dimension = paired["gold_intents"][0]["dimensions"][0]
        other = spec["metrics"][1 if metric == spec["metrics"][0] else 0]
        base_intent = paired["gold_intents"][0]
        alternatives = [json.loads(json.dumps(base_intent)), json.loads(json.dumps(base_intent))]
        row["context"] = dict(paired["context"])
        if family_index == 0:
            row["context"]["role"] = spec["restricted_role"]
            row["utterances"] = paraphrases(metric, dimension, domain, row["split"], alias=spec["ambiguous_alias"])
            alternatives[1]["metrics"] = [other]
            alternatives[1]["metric_versions"] = {}
            alternatives[1]["version_policy"] = "effective_time"
            alternatives[1]["provenance"][0:2] = [other, f"{other}.v1"]
            row["alternatives"] = [metric, other]
            row["distinguishing_slot"] = "metrics"
            row["primary_reason_code"] = "CLR_METRIC_IDENTITY"
            row["clarification_question"] = f"Which governed metric did you mean: {slug_label(metric)} or {slug_label(other)}?"
            change = {
                "slot": "request.metric_expression", "before": metric, "after": spec["ambiguous_alias"],
                "surface_before": slug_label(metric), "surface_after": spec["ambiguous_alias"],
                "alternative_paths": ["intent.metrics.0"],
            }
        elif family_index == 1:
            row["context"].pop("calendar_default", None)
            row["utterances"] = list(paired["utterances"])
            alternatives[1]["time"]["calendar_id"] = "fiscal"
            alternatives[1]["provenance"][-1] = "fiscal"
            row["alternatives"] = ["calendar", "fiscal"]
            row["distinguishing_slot"] = "time.calendar_id"
            row["primary_reason_code"] = "CLR_CALENDAR"
            row["clarification_question"] = "Should the first quarter use the Gregorian or corporate fiscal calendar?"
            change = {
                "slot": "context.calendar_default", "before": "calendar", "after": None,
                "affected_paths": ["context.calendar_default"],
                "alternative_paths": ["intent.time.calendar_id"],
            }
        elif family_index == 2:
            alt_dimension = spec["dimensions"][(i + 1) % 10]
            alternatives[1]["dimensions"] = [alt_dimension]
            alternatives[1]["output_grain"]["entity"] = next(d["entity"] for d in registry["dimensions"] if d["id"] == alt_dimension)
            alternatives[1]["provenance"][2] = alt_dimension
            row["utterances"] = [text.replace(slug_label(dimension), "segment") for text in paired["utterances"]]
            row["alternatives"] = [dimension, alt_dimension]
            row["distinguishing_slot"] = "dimensions"
            row["primary_reason_code"] = "CLR_DIMENSION"
            row["clarification_question"] = f"Which grouping did you mean: {slug_label(dimension)} or {slug_label(alt_dimension)}?"
            change = {
                "slot": "request.dimension_expression", "before": dimension, "after": "segment",
                "surface_before": slug_label(dimension), "surface_after": "segment",
                "alternative_paths": ["intent.dimensions.0"] + (
                    ["intent.output_grain.entity"]
                    if alternatives[0]["output_grain"]["entity"] != alternatives[1]["output_grain"]["entity"]
                    else []
                ),
            }
        elif family_index == 3:
            source_filter = base_intent["filters"][0]
            filter_dimension = source_filter["attribute"]
            values = FILTER_VALUE_CATALOG[domain][filter_dimension]
            source_value = source_filter["value"]
            other_value = next(value for value in values if value != source_value)
            alternatives[1]["filters"][0]["value"] = other_value
            row["utterances"] = replace_clause(paired["utterances"], source_value, "the requested market")
            row["alternatives"] = [source_value, other_value]
            row["distinguishing_slot"] = "filters"
            row["primary_reason_code"] = "CLR_FILTER_VALUE"
            row["clarification_question"] = f"Which {slug_label(filter_dimension)} did you mean: {source_value} or {other_value}?"
            change = {
                "slot": "request.filter.value", "before": source_value, "after": "unresolved",
                "surface_before": source_value, "surface_after": "the requested market",
                "alternative_paths": ["intent.filters.0.value"],
            }
        else:
            alternatives[0]["version_policy"] = "explicit"
            alternatives[0]["metric_versions"] = {metric: f"{metric}.v1"}
            alternatives[1]["version_policy"] = "explicit"
            alternatives[1]["metric_versions"] = {metric: f"{metric}.v2"}
            alternatives[1]["provenance"][1] = f"{metric}.v2"
            row["utterances"] = paraphrases(
                metric, dimension, domain, row["split"],
                alias=f"{slug_label(metric)} using one of the registered definitions",
            )
            row["alternatives"] = [f"{metric}.v1", f"{metric}.v2"]
            row["distinguishing_slot"] = "metric_versions"
            row["primary_reason_code"] = "CLR_VERSION_POLICY"
            row["clarification_question"] = "Which named metric version did you mean: v1 or v2?"
            change = {
                "slot": "request.metric_version_expression", "before": f"{metric}.v1", "after": "unresolved_registered_version",
                "surface_before": "version 1", "surface_after": "using one of the registered definitions",
                "alternative_paths": [f"intent.metric_versions.{metric}"],
            }
        row["candidate_intents"] = alternatives
        row["provenance"] = paired["provenance"]
        group = f"{domain}-contrast-metric-{i + 1:03d}"
        add_contrastive_pair(paired, row, group, change)
        clarify.append(row)

    reject = []
    for i in range(20):
        family_index = i // 4
        paired = execute[[20, 24, 36, 32, 28][family_index] + (i % 4)]
        row = base_case(domain, "reject", i, family_index)
        row["context"] = dict(paired["context"])
        row["utterances"] = list(paired["utterances"])
        metric = paired["gold_intents"][0]["metrics"][0]
        candidate = json.loads(json.dumps(paired["gold_intents"][0]))
        if family_index == 0:
            row["context"]["role"] = "analyst"
            row["primary_reason_code"] = "REJ_AUTHORIZATION"
            row["violated_constraint"] = f"{metric}_{spec['restricted_role']}_only"
            row["machine_checkable_evidence"] = {"object_id": metric, "required_role": spec["restricted_role"], "observed_role": "analyst"}
            change = {
                "slot": "context.role", "before": spec["restricted_role"], "after": "analyst",
                "affected_paths": ["context.role"],
            }
        elif family_index == 1:
            bad_dimension = spec["dimensions"][12]
            good_dimension = paired["gold_intents"][0]["dimensions"][0]
            candidate["dimensions"] = [bad_dimension]
            candidate["output_grain"]["entity"] = spec["metric_entity"]
            candidate["provenance"][2] = bad_dimension
            row["utterances"] = [text.replace(slug_label(good_dimension), slug_label(bad_dimension)) for text in row["utterances"]]
            row["primary_reason_code"] = "REJ_DIMENSION_INCOMPATIBLE"
            row["violated_constraint"] = f"{metric}.allowed_dimensions"
            row["machine_checkable_evidence"] = {"metric": metric, "dimension": bad_dimension, "allowed": False}
            change = {
                "slot": "intent.dimension", "before": good_dimension, "after": bad_dimension,
                "affected_paths": ["intent.dimensions.0", "intent.output_grain.entity"],
                "surface_before": slug_label(good_dimension), "surface_after": slug_label(bad_dimension),
            }
        elif family_index == 2:
            candidate["time"]["temporal_grain"] = "day"
            candidate["output_grain"]["temporal"] = "day"
            row["utterances"] = replace_clause(row["utterances"], "monthly grain", "daily grain")
            row["primary_reason_code"] = "REJ_GRAIN_ADDITIVITY"
            row["violated_constraint"] = f"{metric}.allowed_grains"
            row["machine_checkable_evidence"] = {"metric": metric, "requested_grain": "day", "allowed_grains": ["month", "quarter"]}
            change = {
                "slot": "intent.temporal_grain", "before": "month", "after": "day",
                "affected_paths": ["intent.output_grain.temporal", "intent.time.temporal_grain"],
                "surface_before": "monthly grain", "surface_after": "daily grain",
            }
        elif family_index == 3:
            bad_dimension = spec["dimensions"][29]
            good_dimension = paired["gold_intents"][0]["dimensions"][0]
            candidate["dimensions"] = [bad_dimension, *[value for value in candidate["dimensions"] if value != good_dimension]]
            candidate["output_grain"]["entity"] = "unlinked_entity"
            candidate["provenance"][2] = bad_dimension
            row["utterances"] = [text.replace(slug_label(good_dimension), slug_label(bad_dimension)) for text in row["utterances"]]
            row["primary_reason_code"] = "REJ_ENTITY_PATH"
            row["violated_constraint"] = f"missing:{spec['metric_entity']}_to_unlinked_entity"
            row["machine_checkable_evidence"] = {"from": spec["metric_entity"], "to": "unlinked_entity", "path": None}
            change = {
                "slot": "intent.dimension_entity", "before": good_dimension, "after": bad_dimension,
                "affected_paths": ["intent.dimensions.0", "intent.output_grain.entity"],
                "surface_before": slug_label(good_dimension), "surface_after": slug_label(bad_dimension),
            }
        else:
            candidate["version_policy"] = "explicit"
            candidate["metric_versions"] = {metric: f"{metric}.v99"}
            candidate["provenance"][1] = f"{metric}.v99"
            row["utterances"] = replace_clause(row["utterances"], "version 1", "version 99")
            row["primary_reason_code"] = "REJ_VERSION_INVALID"
            row["violated_constraint"] = f"unknown_version:{metric}.v99"
            row["machine_checkable_evidence"] = {"metric": metric, "requested_version": f"{metric}.v99", "registered": False}
            change = {
                "slot": "intent.metric_version", "before": f"{metric}.v1", "after": f"{metric}.v99",
                "affected_paths": [f"intent.metric_versions.{metric}"],
                "surface_before": "version 1", "surface_after": "version 99",
            }
        row["candidate_intent"] = candidate
        row["provenance"] = paired["provenance"]
        group = f"{domain}-contrast-role-{i + 1:03d}"
        add_contrastive_pair(paired, row, group, change)
        reject.append(row)

    gaps = []
    for i in range(20):
        family_index = i // 4
        row = base_case(domain, "coverage_gap", i, family_index)
        missing = MISSING_CONCEPTS[domain][i]
        dimension = spec["dimensions"][i % 10]
        metric = spec["metrics"][[1, 2, 3, 5][i % 4]]
        row["primary_reason_code"] = ["GAP_METRIC", "GAP_DIMENSION", "GAP_FILTER_CONCEPT", "GAP_COMPOSITION", "GAP_VERSION"][family_index]
        if row["primary_reason_code"] == "GAP_VERSION":
            metric = spec["metrics"][MISSING_VERSION_METRIC_INDEXES[domain][i % 4]]
        row["context"] = {
            "role": spec["restricted_role"] if metric in restricted else "analyst",
            "calendar_default": "calendar", "timezone": "UTC",
        }
        if row["primary_reason_code"] == "GAP_METRIC":
            row["utterances"] = paraphrases(missing, dimension, domain, row["split"])
        elif row["primary_reason_code"] == "GAP_DIMENSION":
            row["utterances"] = paraphrases(metric, missing, domain, row["split"])
        elif row["primary_reason_code"] == "GAP_FILTER_CONCEPT":
            missing_filter_value = MISSING_FILTER_VALUES[domain][i % 4]
            row["utterances"] = append_clause(
                paraphrases(metric, dimension, domain, row["split"]),
                f"where {slug_label(missing)} is {missing_filter_value}",
            )
        elif row["primary_reason_code"] == "GAP_COMPOSITION":
            row["utterances"] = paraphrases(missing, dimension, domain, row["split"])
        else:
            row["utterances"] = paraphrases(
                metric, dimension, domain, row["split"], alias=f"{slug_label(metric)} using {slug_label(missing)}",
            )
        row["missing_capability"] = {"code": row["primary_reason_code"], "concept": missing, "registry_search_evidence": ["metric_ids:complete", "aliases:complete", "versions:complete"]}
        row["provenance"] = {"registry_snapshot": f"registries/phase4/{domain}/v1.json", "registry_hash": registry["snapshot_hash"], "construction": "deterministic-template-v2"}
        gaps.append(row)
    return execute + clarify + reject + gaps


def intent_violations(intent: dict, context: dict, registry: dict) -> set[str]:
    """Return governed-constraint violations for a candidate canonical intent."""
    violations = set()
    metrics = {row["id"]: row for row in registry["metrics"]}
    dimensions = {row["id"]: row for row in registry["dimensions"]}
    calendars = {row["id"]: row for row in registry["calendars"]}
    paths = {(row["from"], row["to"]) for row in registry["entity_paths"] if row["allowed"]}
    metric_ids = intent.get("metrics", [])
    dimension_ids = intent.get("dimensions", [])
    if not metric_ids or any(metric not in metrics for metric in metric_ids):
        violations.add("metric")
        return violations
    for metric_id in metric_ids:
        metric = metrics[metric_id]
        for dimension_id in dimension_ids:
            if dimension_id not in dimensions:
                violations.add("dimension_missing")
                continue
            if dimension_id not in metric["allowed_dimensions"]:
                violations.add("dimension_incompatible")
            entity = dimensions[dimension_id]["entity"]
            if entity != metric["entity"] and (metric["entity"], entity) not in paths:
                violations.add("entity_path")
        time = intent.get("time", {})
        grain = time.get("temporal_grain")
        if grain not in metric["allowed_grains"]:
            violations.add("grain")
        calendar_id = time.get("calendar_id")
        if calendar_id not in calendars or calendar_id not in metric["allowed_calendars"]:
            violations.add("calendar")
        elif not all(target.get("executable", True) for target in calendars[calendar_id]["backends"].values()):
            violations.add("calendar_backend")
        if intent.get("version_policy") == "explicit":
            requested = intent.get("metric_versions", {}).get(metric_id)
            version = next((row for row in metric["versions"] if row["id"] == requested), None)
            if version is None:
                violations.add("version")
            else:
                query_start = date.fromisoformat(time["start"])
                query_end = date.fromisoformat(time["end"])
                effective_from = date.fromisoformat(version["effective_from"])
                effective_to = date.fromisoformat(version["effective_to"]) if version.get("effective_to") else None
                if effective_from > query_end or (effective_to and effective_to < query_start):
                    violations.add("version_time")
        for policy in registry["policies"]:
            if policy["object_id"] == metric_id and policy["effect"] == "allow" and context.get("role") not in policy["roles"]:
                violations.add("authorization")
    for filter_ in intent.get("filters", []):
        attribute = filter_.get("attribute")
        if attribute not in dimensions:
            violations.add("filter_dimension")
        elif filter_.get("value") not in dimensions[attribute].get("allowed_values", []):
            violations.add("filter_value")
    return violations


def deep_diff_paths(left: object, right: object, prefix: str = "") -> set[str]:
    """Return leaf paths that differ, using stable dotted JSON paths."""
    if type(left) is not type(right):
        return {prefix}
    if isinstance(left, dict):
        paths = set()
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                paths.add(path)
            else:
                paths.update(deep_diff_paths(left[key], right[key], path))
        return paths
    if isinstance(left, list):
        paths = set()
        for index in range(max(len(left), len(right))):
            path = f"{prefix}.{index}" if prefix else str(index)
            if index >= len(left) or index >= len(right):
                paths.add(path)
            else:
                paths.update(deep_diff_paths(left[index], right[index], path))
        return paths
    return set() if left == right else {prefix}


def contrastive_errors(cases: list[dict]) -> list[str]:
    """Verify that each contrastive pair contains exactly its declared mutation."""
    errors = []
    groups = defaultdict(list)
    for case in cases:
        if case.get("contrastive_group"):
            groups[case["contrastive_group"]].append(case)
    for group, rows in groups.items():
        if len(rows) != 2:
            errors.append(f"{group} must contain exactly two cases")
            continue
        source = next((row for row in rows if row["gold_action"] == "execute"), None)
        target = next((row for row in rows if row["gold_action"] != "execute"), None)
        if source is None or target is None:
            errors.append(f"{group} must pair Execute with one non-Execute action")
            continue
        change = source.get("contrastive_change")
        if not change or change != target.get("contrastive_change"):
            errors.append(f"{group} lacks identical structural change metadata")
            continue
        if change.get("source_case_id") != source["case_id"] or change.get("target_case_id") != target["case_id"]:
            errors.append(f"{group} structural metadata identifies the wrong pair")
        if not change.get("slot") or "before" not in change or "after" not in change:
            errors.append(f"{group} structural metadata lacks slot/before/after")

        surface_before = change.get("surface_before")
        surface_after = change.get("surface_after")
        if surface_before is None and surface_after is None:
            if source["utterances"] != target["utterances"]:
                errors.append(f"{group} changes surface text without declaring a surface mutation")
        elif not surface_before or not surface_after:
            errors.append(f"{group} must declare both surface_before and surface_after")
        else:
            expected = [text.replace(surface_before, surface_after) for text in source["utterances"]]
            if any(surface_before not in text for text in source["utterances"]) or expected != target["utterances"]:
                errors.append(f"{group} surface text differs beyond the declared replacement")

        source_intent = source["gold_intents"][0]
        expected_paths = set(change.get("affected_paths", []))
        if target["gold_action"] == "clarify":
            candidates = target.get("candidate_intents", [])
            if source_intent not in candidates:
                errors.append(f"{group} Clarify candidates do not preserve the source intent")
            else:
                alternatives = [candidate for candidate in candidates if candidate != source_intent]
                if len(alternatives) != 1:
                    errors.append(f"{group} must add exactly one alternate supported intent")
                else:
                    source_semantic_intent = {
                        key: value for key, value in source_intent.items() if key != "provenance"
                    }
                    alternate_semantic_intent = {
                        key: value for key, value in alternatives[0].items() if key != "provenance"
                    }
                    actual_alternative_paths = {
                        f"intent.{path}"
                        for path in deep_diff_paths(source_semantic_intent, alternate_semantic_intent)
                    }
                    expected_alternative_paths = set(change.get("alternative_paths", []))
                    if actual_alternative_paths != expected_alternative_paths:
                        errors.append(
                            f"{group} alternate intent changes {sorted(actual_alternative_paths)} "
                            f"!= declared {sorted(expected_alternative_paths)}"
                        )
            actual_context_paths = {
                f"context.{path}" for path in deep_diff_paths(source["context"], target["context"])
            }
            if actual_context_paths != expected_paths:
                errors.append(
                    f"{group} context changes {sorted(actual_context_paths)} != declared {sorted(expected_paths)}"
                )
        elif target["gold_action"] == "reject":
            source_semantic_intent = {key: value for key, value in source_intent.items() if key != "provenance"}
            target_semantic_intent = {
                key: value for key, value in target["candidate_intent"].items() if key != "provenance"
            }
            actual_paths = {
                f"intent.{path}" for path in deep_diff_paths(source_semantic_intent, target_semantic_intent)
            }
            actual_paths |= {
                f"context.{path}" for path in deep_diff_paths(source["context"], target["context"])
            }
            if actual_paths != expected_paths:
                errors.append(
                    f"{group} semantic changes {sorted(actual_paths)} != declared {sorted(expected_paths)}"
                )
        else:
            errors.append(f"{group} has unsupported target action {target['gold_action']}")
    return errors


def semantic_errors(cases: list[dict], utterances: list[dict], registries: dict[str, dict]) -> list[str]:
    errors = []
    expected_reject_violation = {
        "REJ_AUTHORIZATION": "authorization",
        "REJ_DIMENSION_INCOMPATIBLE": "dimension_incompatible",
        "REJ_GRAIN_ADDITIVITY": "grain",
        "REJ_ENTITY_PATH": "entity_path",
        "REJ_VERSION_INVALID": "version",
    }
    case_by_id = {case["case_id"]: case for case in cases}
    utterance_ids = set()
    for row in utterances:
        case = case_by_id.get(row.get("canonical_case_id"))
        if case is None:
            errors.append(f"{row.get('utterance_id')} references an unknown canonical case")
            continue
        expected_id = f"{case['case_id']}-u{row.get('paraphrase_index')}"
        if row.get("utterance_id") != expected_id or row["utterance_id"] in utterance_ids:
            errors.append(f"invalid or duplicate utterance_id: {row.get('utterance_id')}")
        utterance_ids.add(row["utterance_id"])
        index = row.get("paraphrase_index")
        if not isinstance(index, int) or index not in range(3) or row.get("text") != case["utterances"][index]:
            errors.append(f"{row.get('utterance_id')} does not match its canonical utterance")
        for field in ("domain", "split", "template_family", "gold_action", "surface_template_set"):
            if row.get(field) != case.get(field):
                errors.append(f"{row.get('utterance_id')} disagrees on {field}")

    for case in cases:
        registry = registries[case["domain"]]
        if case.get("provenance", {}).get("registry_hash") != registry["snapshot_hash"]:
            errors.append(f"{case['case_id']} has stale registry provenance")
        action = case["gold_action"]
        if action == "execute":
            if len(case.get("gold_intents", [])) != 1:
                errors.append(f"{case['case_id']} must have exactly one gold intent")
            else:
                violations = intent_violations(case["gold_intents"][0], case["context"], registry)
                if violations:
                    errors.append(f"{case['case_id']} execute intent violates {sorted(violations)}")
        elif action == "clarify":
            candidates = case.get("candidate_intents", [])
            if len(candidates) != 2 or candidates[0] == candidates[1]:
                errors.append(f"{case['case_id']} needs two distinct candidate intents")
            for index, candidate in enumerate(candidates):
                violations = intent_violations(candidate, case["context"], registry)
                if violations:
                    errors.append(f"{case['case_id']} candidate {index} violates {sorted(violations)}")
        elif action == "reject":
            violations = intent_violations(case.get("candidate_intent", {}), case["context"], registry)
            expected = expected_reject_violation.get(case["primary_reason_code"])
            if expected not in violations or len(violations) != 1:
                errors.append(f"{case['case_id']} reject evidence is not isolated: {sorted(violations)}")
        else:
            concept = slug_label(case["missing_capability"]["concept"])
            if not all(concept in utterance.lower() for utterance in case["utterances"]):
                errors.append(f"{case['case_id']} does not express its missing concept in every paraphrase")
            registry_terms = {
                slug_label(value).lower()
                for metric in registry["metrics"]
                for value in [metric["id"], metric["name"], *metric["aliases"], *(v["id"] for v in metric["versions"])]
            } | {slug_label(dimension["id"]).lower() for dimension in registry["dimensions"]}
            if concept in registry_terms:
                errors.append(f"{case['case_id']} marks a registered concept as missing")
    return errors


def make_leave_one_domain_out_folds(cases: list[dict]) -> dict:
    """Freeze three transfer folds without exposing target-domain development cases."""
    domains = sorted({case["domain"] for case in cases})
    folds = []
    for held_out in domains:
        source_domains = [domain for domain in domains if domain != held_out]
        folds.append({
            "fold_id": f"holdout_{held_out}",
            "held_out_domain": held_out,
            "source_domains": source_domains,
            "source_development_case_ids": sorted(
                case["case_id"] for case in cases
                if case["domain"] in source_domains and case["split"] == "development"
            ),
            "source_in_domain_test_case_ids": sorted(
                case["case_id"] for case in cases
                if case["domain"] in source_domains and case["split"] == "test"
            ),
            "held_out_transfer_test_case_ids": sorted(
                case["case_id"] for case in cases
                if case["domain"] == held_out and case["split"] == "test"
            ),
            "excluded_target_development_case_ids": sorted(
                case["case_id"] for case in cases
                if case["domain"] == held_out and case["split"] == "development"
            ),
        })
    return {
        "schema_version": "1.0.0",
        "protocol": "Configure only on source-domain development cases; evaluate source in-domain and held-out-domain test cases separately; never inspect target-domain development cases in that fold.",
        "folds": folds,
    }


def leave_one_domain_out_errors(cases: list[dict], manifest: dict) -> list[str]:
    errors = []
    case_by_id = {case["case_id"]: case for case in cases}
    domains = sorted({case["domain"] for case in cases})
    folds = manifest.get("folds", [])
    if len(folds) != len(domains) or sorted(fold.get("held_out_domain") for fold in folds) != domains:
        return ["leave-one-domain-out manifest must contain one fold per domain"]
    target_test_occurrences = Counter()
    for fold in folds:
        held_out = fold["held_out_domain"]
        source_domains = fold.get("source_domains", [])
        if source_domains != [domain for domain in domains if domain != held_out]:
            errors.append(f"{fold.get('fold_id')} has invalid source domains")
        partitions = {
            "source_development_case_ids": (source_domains, "development", 40),
            "source_in_domain_test_case_ids": (source_domains, "test", 160),
            "held_out_transfer_test_case_ids": ([held_out], "test", 80),
            "excluded_target_development_case_ids": ([held_out], "development", 20),
        }
        all_ids = []
        for field, (allowed_domains, split, expected_count) in partitions.items():
            ids = fold.get(field, [])
            all_ids.extend(ids)
            if len(ids) != expected_count or len(ids) != len(set(ids)):
                errors.append(f"{fold['fold_id']} {field} must contain {expected_count} unique cases")
            for case_id in ids:
                case = case_by_id.get(case_id)
                if case is None or case["domain"] not in allowed_domains or case["split"] != split:
                    errors.append(f"{fold['fold_id']} misassigns {case_id} in {field}")
            if field == "held_out_transfer_test_case_ids":
                target_test_occurrences.update(ids)
        if len(all_ids) != len(set(all_ids)):
            errors.append(f"{fold['fold_id']} partitions overlap")
    expected_target_tests = {case["case_id"] for case in cases if case["split"] == "test"}
    if set(target_test_occurrences) != expected_target_tests or any(count != 1 for count in target_test_occurrences.values()):
        errors.append("each held-out test case must be a transfer target in exactly one fold")
    return errors


def validate(
    cases: list[dict], utterances: list[dict], registries: dict[str, dict],
    leave_one_domain_out_manifest: dict | None = None,
) -> dict:
    errors = []
    if len(cases) != 300:
        errors.append(f"expected 300 canonical cases, found {len(cases)}")
    if len(utterances) != 900:
        errors.append(f"expected 900 utterances, found {len(utterances)}")
    if len({c["case_id"] for c in cases}) != len(cases):
        errors.append("case_id values are not unique")
    action_counts = Counter(c["gold_action"] for c in cases)
    if action_counts != Counter({"execute": 120, "clarify": 60, "reject": 60, "coverage_gap": 60}):
        errors.append(f"wrong action distribution: {dict(action_counts)}")
    domain_counts = Counter(c["domain"] for c in cases)
    if domain_counts != Counter({"saas": 100, "commerce": 100, "support": 100}):
        errors.append(f"wrong domain distribution: {dict(domain_counts)}")
    split_counts = Counter(c["split"] for c in cases)
    if split_counts != Counter({"development": 60, "test": 240}):
        errors.append(f"wrong split distribution: {dict(split_counts)}")
    for field in ("template_family", "paraphrase_group", "contrastive_group", "surface_template_set"):
        groups = defaultdict(set)
        for case in cases:
            if case.get(field):
                groups[case[field]].add(case["split"])
        leaking = [k for k, v in groups.items() if len(v) > 1]
        if leaking:
            errors.append(f"{field} leakage: {leaking[:5]}")
    contrastive = [c for c in cases if c.get("contrastive_group")]
    if len(contrastive) < 100:
        errors.append("fewer than 100 cases participate in contrastive pairs")
    for case in cases:
        if len(case["utterances"]) != 3 or len(set(case["utterances"])) != 3:
            errors.append(f"{case['case_id']} lacks three distinct utterances")
        if case["gold_action"] == "execute" and not case.get("gold_intents"):
            errors.append(f"{case['case_id']} lacks a gold intent")
        if case["gold_action"] == "clarify" and not case.get("clarification_question"):
            errors.append(f"{case['case_id']} lacks a targeted question")
        if case["gold_action"] == "reject" and not case.get("violated_constraint"):
            errors.append(f"{case['case_id']} lacks a violated constraint")
        if case["gold_action"] == "coverage_gap" and not case.get("missing_capability"):
            errors.append(f"{case['case_id']} lacks missing-capability evidence")
    duplicate_groups = defaultdict(list)
    for case in cases:
        for utterance in case["utterances"]:
            duplicate_groups[utterance].append(case)
    for utterance, rows in duplicate_groups.items():
        if len(rows) > 1 and (len(rows) != 2 or len({row.get("contrastive_group") for row in rows}) != 1):
            errors.append(f"uncontrolled duplicate utterance: {utterance}")
    registry_inventory = {}
    for domain, registry in registries.items():
        if registry["snapshot_hash"] != canonical_hash(registry):
            errors.append(f"{domain} registry hash mismatch")
        counts = {k: len(registry[k]) for k in ("metrics", "dimensions", "calendars", "entity_paths", "policies")}
        registry_inventory[domain] = counts
        if not 20 <= counts["metrics"] <= 35 or not 25 <= counts["dimensions"] <= 50:
            errors.append(f"{domain} registry size is outside the roadmap range")
        used_metrics = {
            metric
            for case in cases if case["domain"] == domain and case["gold_action"] == "execute"
            for intent in case["gold_intents"] for metric in intent["metrics"]
        }
        if used_metrics != {metric["id"] for metric in registry["metrics"]}:
            errors.append(f"{domain} execute cases do not cover every registered metric")
    errors.extend(contrastive_errors(cases))
    errors.extend(semantic_errors(cases, utterances, registries))
    manifest = leave_one_domain_out_manifest or make_leave_one_domain_out_folds(cases)
    errors.extend(leave_one_domain_out_errors(cases, manifest))
    return {
        "status": "pass" if not errors else "fail", "errors": errors,
        "canonical_cases": len(cases), "utterances": len(utterances),
        "action_distribution": dict(sorted(action_counts.items())), "domain_distribution": dict(sorted(domain_counts.items())),
        "split_distribution": dict(sorted(split_counts.items())),
        "contrastive_groups": len({c["contrastive_group"] for c in contrastive}),
        "contrastive_cases": len(contrastive), "template_families": len({c["template_family"] for c in cases}),
        "leave_one_domain_out_folds": len(manifest.get("folds", [])),
        "registry_inventory": registry_inventory,
        "human_sourced_cases": sum(c["source_type"] == "human_sourced_sanitized" for c in cases),
        "annotation_status": "pending_three_model_review_and_sampled_human_audit",
        "phase4_exit_gate_status": "pending_model_review_human_audit_and_execution",
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_annotation_assets(output_root: Path, cases: list[dict], *, overwrite: bool) -> dict[str, Path]:
    annotation_root = output_root / "benchmarks/phase4/annotation"
    annotation_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "annotation_template": annotation_root / "adjudication_template.csv",
        "blind_annotation_template": annotation_root / "blind_annotation_template.csv",
        "annotation_crosswalk": annotation_root / "annotation_crosswalk.csv",
        "human_question_intake": annotation_root / "human_question_intake.csv",
    }
    shuffled = list(cases)
    random.Random(20260801).shuffle(shuffled)
    opaque_ids = {case["case_id"]: f"P4-{index + 1:03d}" for index, case in enumerate(shuffled)}

    if overwrite or not paths["blind_annotation_template"].exists():
        with paths["blind_annotation_template"].open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([
                "annotation_id", "domain", "utterance_1", "utterance_2", "utterance_3", "context_json",
                "registry_snapshot", "annotator_action", "primary_reason", "registry_evidence", "confidence",
                "paraphrases_equivalent", "execution_accuracy_insufficient", "annotator_notes",
            ])
            for case in shuffled:
                writer.writerow([
                    opaque_ids[case["case_id"]], case["domain"], *case["utterances"],
                    json.dumps(case["context"], sort_keys=True, separators=(",", ":")),
                    case["provenance"]["registry_snapshot"], "", "", "", "", "", "", "",
                ])
    if overwrite or not paths["annotation_crosswalk"].exists():
        with paths["annotation_crosswalk"].open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["annotation_id", "case_id", "seed_action"])
            for case in shuffled:
                writer.writerow([opaque_ids[case["case_id"]], case["case_id"], case["gold_action"]])
    if overwrite or not paths["annotation_template"].exists():
        with paths["annotation_template"].open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["annotation_id", "annotator_1_action", "annotator_1_reason", "annotator_2_action", "annotator_2_reason", "adjudicated_action", "adjudicator_notes", "execution_accuracy_insufficient"])
            for case in shuffled:
                writer.writerow([opaque_ids[case["case_id"]], "", "", "", "", "", "", ""])
    if overwrite or not paths["human_question_intake"].exists():
        with paths["human_question_intake"].open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["source_id", "sanitized_question", "domain", "confidentiality_review", "registry_mapping_status", "notes"])
    return paths


ANNOTATOR_DISTRIBUTION_README = """# Phase 4 blinded review packet

This directory is the only benchmark material that may be distributed to
LLM reviewers or human quality auditors. It contains shuffled opaque cases and
the three frozen registry snapshots needed to determine the action. It excludes
canonical case IDs, seed labels, the seed-label crosswalk, gold intents,
adjudication decisions, and validation reports.

Reviewers work from `blind_annotation_template.csv` and consult only the
matching file under `registries/`. The authoritative LLM procedure and exact
prompts are versioned separately in `docs/phase4-model-review-runbook.md` and
`prompts/phase4/`. Never place completed reviews back in this source directory.
"""


def write_annotator_distribution(
    output_root: Path, annotation_paths: dict[str, Path], registries: dict[str, dict], *, overwrite: bool,
) -> dict[str, Path]:
    """Create a physically separate, allowlisted bundle with no seed labels."""
    bundle_root = output_root / "benchmarks/phase4/annotator_distribution"
    registry_root = bundle_root / "registries"
    bundle_root.mkdir(parents=True, exist_ok=True)
    registry_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "annotator_distribution_readme": bundle_root / "README.md",
        "annotator_distribution_packet": bundle_root / "blind_annotation_template.csv",
        **{
            f"annotator_distribution_registry_{domain}": registry_root / f"{domain}.json"
            for domain in sorted(registries)
        },
    }
    manifest_path = bundle_root / "MANIFEST.json"

    if overwrite or not paths["annotator_distribution_packet"].exists():
        with annotation_paths["blind_annotation_template"].open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            fieldnames = reader.fieldnames
            rows = list(reader)
        if fieldnames is None:
            raise ValueError("blind annotation packet has no header")
        with paths["annotator_distribution_packet"].open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                row["registry_snapshot"] = f"registries/{row['domain']}.json"
                writer.writerow(row)
        paths["annotator_distribution_readme"].write_text(
            ANNOTATOR_DISTRIBUTION_README, encoding="utf-8"
        )
        for domain in sorted(registries):
            shutil.copyfile(
                output_root / f"registries/phase4/{domain}/v1.json",
                paths[f"annotator_distribution_registry_{domain}"],
            )
        manifest = {
            "schema_version": "1.0.0",
            "allowlisted_files": sorted(
                str(path.relative_to(bundle_root)) for path in paths.values()
            ),
            "sha256": {
                str(path.relative_to(bundle_root)): file_hash(path)
                for path in sorted(paths.values())
            },
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["annotator_distribution_manifest"] = manifest_path
    return paths


def build(output_root: Path, *, overwrite_annotation_assets: bool = False) -> dict:
    registries = {domain: make_registry(domain, spec) for domain, spec in DOMAIN_SPECS.items()}
    cases = []
    for domain, spec in DOMAIN_SPECS.items():
        cases.extend(build_domain_cases(domain, spec, registries[domain]))
    utterances = []
    for case in cases:
        for index, value in enumerate(case["utterances"]):
            utterances.append({
                "utterance_id": f"{case['case_id']}-u{index}", "canonical_case_id": case["case_id"],
                "paraphrase_group": case["paraphrase_group"], "paraphrase_index": index,
                "domain": case["domain"], "split": case["split"], "template_family": case["template_family"],
                "surface_template_set": case["surface_template_set"],
                "text": value, "gold_action": case["gold_action"],
            })

    leave_one_domain_out_manifest = make_leave_one_domain_out_folds(cases)
    report = validate(cases, utterances, registries, leave_one_domain_out_manifest)
    if report["status"] != "pass":
        return report

    for domain, registry in registries.items():
        path = output_root / f"registries/phase4/{domain}/v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    case_path = output_root / "benchmarks/phase4/canonical_cases.jsonl"
    utterance_path = output_root / "benchmarks/phase4/utterances.jsonl"
    write_jsonl(case_path, cases)
    write_jsonl(utterance_path, utterances)
    fold_path = output_root / "benchmarks/phase4/leave_one_domain_out_folds.json"
    fold_path.write_text(
        json.dumps(leave_one_domain_out_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    annotation_paths = write_annotation_assets(output_root, cases, overwrite=overwrite_annotation_assets)
    distribution_paths = write_annotator_distribution(
        output_root, annotation_paths, registries, overwrite=overwrite_annotation_assets
    )
    report["artifact_hashes"] = {
        "canonical_cases": file_hash(case_path), "utterances": file_hash(utterance_path),
        "leave_one_domain_out_folds": file_hash(fold_path),
        **{
            name: file_hash(path) for name, path in annotation_paths.items()
            if name != "human_question_intake"
        },
        **{f"registry_{domain}": file_hash(output_root / f"registries/phase4/{domain}/v1.json") for domain in registries},
        **{name: file_hash(path) for name, path in distribution_paths.items()},
    }
    report_path = output_root / "benchmarks/phase4/validation_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("."))
    parser.add_argument(
        "--overwrite-annotation-assets", action="store_true",
        help="Regenerate blank annotation templates and crosswalk; never use after annotation begins.",
    )
    args = parser.parse_args()
    report = build(args.output_root, overwrite_annotation_assets=args.overwrite_annotation_assets)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
