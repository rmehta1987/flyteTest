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
| Manifest-backed asset resolution | Close | `src/flytetest/resolver.py` now provides a first local resolver over explicit bindings, current manifests, and current result-bundle objects, and typed planning exposed through MCP can use it. MCP recipe preparation now accepts explicit manifest sources, serialized planner bindings, and runtime bindings for BUSCO, EggNOG, and AGAT recipe inputs, and there is still no remote or indexed discovery layer yet. |
| Typed workflow composition from registered stages | Current | This is already a core pattern via `src/flytetest/registry.py` and the stage entrypoints in `src/flytetest/workflows/`. |
| Registry-driven dynamic workflow composition | Close | The registry already carries compatibility metadata and typed planning can select supported targets, but intent-based multi-node DAG composition is still future work, and execution-capable composed DAGs stay gated on Milestone 19 caching/resumability. |
| Registry as compatibility graph | Close | `src/flytetest/registry.py` now adds compatibility metadata for current workflow entries, including biological stage, planner input/output types, reusable stage status, execution defaults, and composition constraints, while task entries mostly keep defaults until later graph work needs them. |
| Workflow spec schema and persistence | Current | `src/flytetest/specs.py` defines normalized `WorkflowSpec` and related planning/replay metadata contracts, and `src/flytetest/spec_artifacts.py` can save and reload metadata-only `WorkflowSpec` plus `BindingPlan` JSON artifacts without re-parsing the original prompt. |
| Typed prompt planning outcomes | Current | `src/flytetest/planning.py` now has a `plan_typed_request(...)` path that can report direct registered workflows or tasks, registered-stage composition, generated `WorkflowSpec` preview, and honest decline outcomes; `src/flytetest/server.py` now uses that path for MCP recipe preparation. |
| Local saved-spec execution | Current | `src/flytetest/spec_executor.py` executes saved `WorkflowSpec` artifacts through explicit registered handlers, resolver inputs, and saved binding plans, with synthetic manifest-preserving coverage. It is wired into MCP for the original runnable targets plus BUSCO, EggNOG, and the three individual AGAT slices, but it still does not auto-load every checked-in Flyte workflow. |
| Generic biology asset compatibility | Current | `src/flytetest/types/assets.py` now exposes `ManifestSerializable`, typed `AssetToolProvenance`, and generic sibling names for `AbInitioResultBundle`, `RnaSeqAlignmentResult`, and `CleanedTranscriptDataset` while keeping the legacy BRAKER3, STAR, and PASA names readable for historical manifests. |
| Generic biology asset adoption | Close | Generic biology asset names now appear in the compatibility layer and selected manifest emitters, but a broader migration across planner adapters and workflow outputs is still reserved for Milestone 17 while legacy alias replay stays available. |
| Slurm retry and resubmission policy | Far | Slurm job submission, lifecycle reconciliation, and cancellation now exist, but failed jobs still need an explicit retry policy with attempt limits before they can be resubmitted safely. Milestone 18 covers that Slurm-specific recovery step. |
| EggNOG functional annotation | Current | `src/flytetest/tasks/eggnog.py` and `src/flytetest/workflows/eggnog.py` now expose the post-BUSCO functional-annotation boundary, preserve the EggNOG annotations and decorated GFF3 outputs, and keep the local EggNOG database directory explicit. |
| AGAT post-processing | Current | The statistics, conversion, and deterministic cleanup slices after EggNOG functional annotation are wired through task and workflow boundaries, while `table2asn` remains deferred. |
| Prompt-to-spec generation | Current | Typed planning can produce metadata-only `WorkflowSpec` and `BindingPlan` previews from supported natural-language requests. This is controlled dynamic generation from registered biological building blocks, not arbitrary Python code generation. |
| Ad hoc task execution | Close | The current MCP/server surface can already execute `exonerate_align_chunk` directly for stage-level experimentation, but a broader bounded task-execution policy with explicit eligibility and input binding rules is still future Milestone 21 work. |
| Runtime creation of new task code | Far | The design deliberately avoids opaque runtime task-code generation. Future expansion should prefer registered stages, valid compositions, and saved specs before adding any broader synthesis behavior. |
| Resource-aware execution planning | Current | The recipe-backed planner now freezes a selected execution profile plus structured `ResourceSpec` and optional `RuntimeImageSpec` metadata into saved `BindingPlan` artifacts and local or Slurm submission results. Registry workflow metadata exposes resource defaults for current workflow targets, and Slurm lifecycle reconciliation records the observed scheduler state. |
| Container/dependency handling | Close | Optional `*.sif` inputs and `run_tool()` are real, but they are user-supplied and local-first rather than centrally managed runtime environments. |
| Local execution with provenance | Current | This is one of the strongest parts today: stable result bundles and `run_manifest.json` files across stages. |
| Managed / remote execution | Far | The repo mostly uses `flyte run --local` and does not yet show a real backend deployment or execution model. |
| Slurm/HPC execution integration | Close | The Slurm path now renders an `sbatch` script from a frozen Slurm-profile recipe, submits it explicitly, captures the accepted job ID, writes a run record under `.runtime/runs/`, reconciles scheduler state with `squeue`, `scontrol show job`, and `sacct`, and records `scancel` cancellation requests. Retry/resubmission and resumability remain future milestones. |
| Caching / resumability | Far | The current code does not yet use explicit cache keys, stage-completion state, or replayable resume rules in a meaningful way. Milestone 19 covers that execution recovery step. |
| Reproducible result delivery | Current locally | The repo writes deterministic local result bundles with copied boundaries and manifests, but not to durable queryable remote storage. |
| Storage-native durable asset return | Far | There is no content-addressed object store or metadata-indexed asset retrieval layer yet. Milestone 20 covers the first filesystem-backed durable asset reference step. |

## Near-Term Priorities

- Start using the new planner-facing dataclasses in resolver and registry work instead of growing a larger tool-specific public type surface.
- Continue using the normalized spec layer as the stable handoff between planner, saved artifacts, and the local executor.
- Harden the recipe-backed MCP surface and extend the explicit input-binding
  pattern to later follow-on stages only when inputs, runtime bindings, and
  result contracts are explicit.
- Keep async orchestration as a targeted future optimization rather than a
  default architecture choice; it is most likely to help in MCP transport,
  Slurm polling, and any future remote resolver or asset-discovery layer.
- Keep using manifest sources, explicit planner bindings, and runtime bindings
  for BUSCO, EggNOG, and AGAT recipe preparation; do not widen into composed
  downstream pipelines until those recipe boundaries are explicit.
- Start using the new registry compatibility metadata in planner and resolver work while preserving the older listing helpers.
- Keep dynamic workflow generation replayable by routing new workflow shapes
  through `WorkflowSpec`, `BindingPlan`, provenance, and explicit assumptions.
- Define a bounded ad hoc task execution policy before widening the current
  single-task MCP task surface.
- Migrate internal callers and manifest emitters toward the generic asset
  vocabulary while keeping legacy aliases available.
- Keep registry-driven composition bounded, typed, and approval-gated before
  execution, with composed DAG execution gated on Milestone 19.
- Extend explicit resource policy from current workflow-level recipe metadata into task-level graph planning when later composition work needs it.
- Keep resource requests and execution profiles explicit in the recipe-backed MCP flow before any Slurm submission work.
- Add explicit Slurm retry and resubmission policy before any caching or resumability work.
- Add caching and resumability before any durable asset-reference layer.
- Add durable asset references without turning the project into a database-first architecture.
- Add Slurm/HPC execution profiles only when queue, filesystem, image, and scheduler assumptions can be made explicit.
- Keep result manifests queryable and reusable so downstream stages can consume prior outputs as stable assets without requiring a database-first architecture.

## Notes

- This snapshot is intended to complement, not replace, the milestone-specific notes-alignment table in `README.md`.
- When the repo gains new execution, storage, or planning capabilities, update both this page and any affected README scope language.
