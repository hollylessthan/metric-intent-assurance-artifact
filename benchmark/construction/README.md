# Benchmark construction provenance

The benchmark is synthetic and registry-derived. This directory preserves the source programs used for the two main deterministic construction stages at the pinned research commit:

- `build_synthetic_seed.py`: constructs the synthetic domain registries, canonical seed cases, contrastive structure, and utterance package.
- `finalize_after_adjudication.py`: applies the frozen human-adjudication corrections and validates executable intents before producing the versioned benchmark.

The public artifact's authoritative evaluated benchmark is `benchmark/canonical_cases.v1.1.jsonl`. The construction programs are included for methodological inspection and provenance. Human/LLM annotation workbooks and restricted reviewer source material are intentionally not published; their aggregate/adjudicated outputs are represented by the validation and adjudication records under `benchmark/`.

These files retain historical internal path names inside the programs because they are preserved construction-source snapshots, not the runtime interface of the curated artifact. The evaluated v1.1 benchmark itself is byte-bound by `PRESERVATION_AUDIT.json`.
