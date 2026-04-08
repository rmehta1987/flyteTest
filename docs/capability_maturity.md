# Capability Maturity Snapshot

This page is a living project reference for FLyteTest capability maturity.
It tracks progress toward the project goal: biology-facing tasks and workflows
derived from bioinformatics pipelines, prompt-driven planning from natural
language, replayable workflow-spec generation when enough context is available,
and local plus HPC/Slurm-oriented execution support.

In this snapshot, "deterministic" does not mean "static only": dynamic workflow
generation is part of the goal, but generated plans should be typed, saved or
previewable, and replayable rather than opaque one-off code.

Update this table as the pipeline, planner, storage model, and execution
surfaces evolve.

## Status Labels

- `Current`: implemented in a meaningful way today
- `Close`: partially implemented or structurally prepared, but still missing key pieces
- `Far`: mostly future work or only present as design intent

## Capability Table

| Capability | Status | Why |
| --- | --- | --- |
| Biology-facing planner dataclasses | Current | `src/flytetest/planner_types.py` now defines the stable biology-facing planner dataclasses, `src/flytetest/planner_adapters.py` can adapt current assets and manifests into them, and the additive typed planner preview can consume them through resolver bindings. |
| Manifest-backed asset resolution | Close | `src/flytetest/resolver.py` now provides a first local resolver over explicit bindings, current manifests, and current result-bundle objects, and typed planning exposed through MCP can use it. Day-one MCP recipe execution still freezes explicit prompt paths into runtime bindings for the original runnable targets, and there is no remote or indexed discovery layer yet. |
| Typed workflow composition from registered stages | Current | This is already a core pattern via `src/flytetest/registry.py` and the stage entrypoints in `src/flytetest/workflows/`. |
| Registry as compatibility graph | Close | `src/flytetest/registry.py` now adds compatibility metadata for current workflow entries, including biological stage, planner input/output types, reusable stage status, execution defaults, and composition constraints, while task entries mostly keep defaults until later graph work needs them. |
| Workflow spec schema and persistence | Current | `src/flytetest/specs.py` defines normalized `WorkflowSpec` and related planning/replay metadata contracts, and `src/flytetest/spec_artifacts.py` can save and reload metadata-only `WorkflowSpec` plus `BindingPlan` JSON artifacts without re-parsing the original prompt. |
| Typed prompt planning outcomes | Current | `src/flytetest/planning.py` now has a `plan_typed_request(...)` path that can report direct registered workflows or tasks, registered-stage composition, generated `WorkflowSpec` preview, and honest decline outcomes; `src/flytetest/server.py` now uses that path for MCP recipe preparation. |
| Local saved-spec execution | Current for day-one MCP targets | `src/flytetest/spec_executor.py` executes saved `WorkflowSpec` artifacts through explicit registered handlers, resolver inputs, and saved binding plans, with synthetic manifest-preserving coverage. It is wired into MCP for the day-one handler set, but it still does not auto-load every checked-in Flyte workflow. |
| EggNOG functional annotation | Current | `src/flytetest/tasks/eggnog.py` and `src/flytetest/workflows/eggnog.py` now expose the post-BUSCO functional-annotation boundary, preserve the EggNOG annotations and decorated GFF3 outputs, and keep the local EggNOG database directory explicit. |
| AGAT post-processing | Current | The statistics, conversion, and deterministic cleanup slices after EggNOG functional annotation are wired through task and workflow boundaries, while `table2asn` remains deferred. |
| Prompt-to-spec generation | Current | Typed planning can produce metadata-only `WorkflowSpec` and `BindingPlan` previews from supported natural-language requests. This is controlled dynamic generation from registered biological building blocks, not arbitrary Python code generation. |
| Runtime creation of new task code | Far | The design deliberately avoids opaque runtime task-code generation. Future expansion should prefer registered stages, valid compositions, and saved specs before adding any broader synthesis behavior. |
| Resource-aware execution planning | Close | Flyte `TaskEnvironment` is in place in `src/flytetest/config.py`, but the repo is not yet really using per-task resources, queue selection, or image policy in code. |
| Container/dependency handling | Close | Optional `*.sif` inputs and `run_tool()` are real, but they are user-supplied and local-first rather than centrally managed runtime environments. |
| Local execution with provenance | Current | This is one of the strongest parts today: stable result bundles and `run_manifest.json` files across stages. |
| Managed / remote execution | Far | The repo mostly uses `flyte run --local` and does not yet show a real backend deployment or execution model. |
| Slurm/HPC execution integration | Far | The docs and specs preserve HPC and queue-shaped concepts, and container paths are supported locally, but generic `sbatch` orchestration, Slurm queue binding, and cluster-aware scheduling are not implemented yet. |
| Caching / resumability | Far | The current code does not yet use explicit Flyte cache policy in a meaningful way. |
| Reproducible result delivery | Current locally | The repo writes deterministic local result bundles with copied boundaries and manifests, but not to durable queryable remote storage. |
| Storage-native durable asset return | Far | There is no content-addressed object store or metadata-indexed asset retrieval layer yet. |

## Near-Term Priorities

- Start using the new planner-facing dataclasses in resolver and registry work instead of growing a larger tool-specific public type surface.
- Continue using the normalized spec layer as the stable handoff between planner, saved artifacts, and the local executor.
- Harden the recipe-backed MCP surface and add local handlers only when inputs,
  runtime bindings, and result contracts are explicit.
- Start using the new registry compatibility metadata in planner and resolver work while preserving the older listing helpers.
- Keep dynamic workflow generation replayable by routing new workflow shapes
  through `WorkflowSpec`, `BindingPlan`, provenance, and explicit assumptions.
- Add explicit resource policy for tasks, including CPU, memory, queue, execution profile, and runtime-image defaults where supported.
- Add Slurm/HPC execution profiles only when queue, filesystem, image, and scheduler assumptions can be made explicit.
- Keep result manifests queryable and reusable so downstream stages can consume prior outputs as stable assets without requiring a database-first architecture.

## Notes

- This snapshot is intended to complement, not replace, the milestone-specific notes-alignment table in `README.md`.
- When the repo gains new execution, storage, or planning capabilities, update both this page and any affected README scope language.
