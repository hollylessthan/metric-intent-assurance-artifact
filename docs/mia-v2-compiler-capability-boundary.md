# MIA v2 compiler capability boundary

Status: **credential-free design; no provider calls authorized**

## Decision

MIA v2 does not reimplement MetricFlow join planning, entity traversal, or cardinality reasoning.

The current reference path uses the existing frozen MIA-v1 canonical Intent and existing compilers for requests that can be represented without loss.

A model-generated semantic request that groups across multiple registry entities cannot be faithfully represented by the v1 single `output_grain.entity` field. MIA v2 therefore does **not**:

- choose one entity arbitrarily;
- weaken the frozen v1 entity-grain invariant;
- add an independent one-to-one / many-to-many rule engine;
- claim that an `entity_path.allowed` flag proves a safe join.

Until a separate end-to-end semantic-compiler capability path is demonstrated, such a request fails closed as:

`GAP_COMPOSITION`

This is a capability boundary, not a claim that MetricFlow itself cannot execute the request.

## Why this is intentionally conservative

MetricFlow already owns semantic-model/entity resolution. Duplicating that logic in MIA would expand the research contribution into join planning and create two sources of truth.

The v2 regression can proceed without that expansion because:

1. ordinary single-representation intents use the existing deterministic assurance/compiler path;
2. mixed-entity candidates no longer crash the provider run;
3. they remain auditable as explicit `GAP_COMPOSITION` decisions;
4. no mixed-entity capability claim is made until an integration proves it.

## Future evidence required to enable mixed-entity Execute

Before MIA-v2 may newly Execute a mixed-entity request:

1. define a semantic request -> MetricFlow capability adapter that does not depend on the v1 single output-entity field;
2. prove the requested metric/dimension combination against the actual MetricFlow semantic configuration;
3. add an end-to-end fixture test showing MetricFlow resolves and executes it;
4. freeze that adapter before fresh challenge-v2 inference.

This does not require changing MetricFlow itself.

## Reproducibility

MIA-v1 remains unchanged. No Phase 5 prompt, schema, validator, compiler, registry, trace, threshold, or result is modified by this v2 boundary.
