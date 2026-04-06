# Capability Maturity Snapshot

This page is a living project reference for FLyteTest capability maturity.
It captures which platform goals are implemented now, which are close, and
which are still future work.

Update this table as the pipeline, planner, storage model, and execution
surfaces evolve.

## Status Labels

- `Current`: implemented in a meaningful way today
- `Close`: partially implemented or structurally prepared, but still missing key pieces
- `Far`: mostly future work or only present as design intent

## Capability Table

| Capability | Status | Why |
| --- | --- | --- |
| Metadata-driven data resolution | Far | The repo currently requires explicit local file paths and explicitly says there is no remote fetch/query/update or content addressing in `src/flytetest/types/assets.py` and `src/flytetest/planning.py`. |
| Typed workflow composition from registered stages | Current | This is already a core pattern via `src/flytetest/registry.py` and the stage entrypoints in `src/flytetest/workflows/`. |
| Runtime creation of new tasks/workflows | Far | The design now allows controlled runtime synthesis, but the current repo does not implement that capability yet. |
| Resource-aware execution planning | Close | Flyte `TaskEnvironment` is in place in `src/flytetest/config.py`, but the repo is not yet really using per-task resources, queue selection, or image policy in code. |
| Container/dependency handling | Close | Optional `*.sif` inputs and `run_tool()` are real, but they are user-supplied and local-first rather than centrally managed runtime environments. |
| Local execution with provenance | Current | This is one of the strongest parts today: stable result bundles and `run_manifest.json` files across stages. |
| Managed / remote execution | Far | The repo mostly uses `flyte run --local` and does not yet show a real backend deployment or execution model. |
| Caching / resumability | Far | The current code does not yet use explicit Flyte cache policy in a meaningful way. |
| Reproducible result delivery | Current locally | The repo writes deterministic local result bundles with copied boundaries and manifests, but not to durable queryable remote storage. |
| Storage-native durable asset return | Far | There is no content-addressed object store or metadata-indexed asset retrieval layer yet. |

## Near-Term Priorities

- Add an asset resolver layer that maps stable biological asset identifiers to local or remote paths plus metadata.
- Start using the typed asset dataclasses in `src/flytetest/types/assets.py` as real planner inputs instead of future placeholders.
- Add explicit resource policy for tasks, including CPU, memory, queue, and runtime-image defaults where supported.
- Extend the planner so it can resolve supported requests from asset identity and stage metadata instead of only explicit file paths.
- Keep result manifests queryable and reusable so downstream stages can consume prior outputs as stable assets.

## Notes

- This snapshot is intended to complement, not replace, the milestone-specific notes-alignment table in `README.md`.
- When the repo gains new execution, storage, or planning capabilities, update both this page and any affected README scope language.
