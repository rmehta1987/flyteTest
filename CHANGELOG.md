# Changelog

This file records milestone-level changes in FLyteTest so repo scope, MCP
surface changes, prompt-driven handoff work, and in-progress work notes are
easier to track over time.

Guidelines:

- add new entries immediately below `## Unreleased`, above all existing sections — newest section always first; never append to the bottom
- describe what actually changed, not planned work
- keep scope boundaries honest, especially for deferred post-PASA stages
- link to prompt or checklist docs when they were part of the milestone handoff
- use strikethrough for milestone items that were later removed, renamed, or superseded during refactoring, and add a short note explaining what replaced them
- treat this file as the shared working memory for meaningful units of work;
  update it after each completed slice instead of waiting for a final wrap-up
- use dated checklist items or dated bullets for completed work so the timeline
  is obvious to later agents
- record what was tried, what worked, what failed, what remains blocked, and
  any dead ends that should not be retried without a new reason
- add newly discovered follow-up tasks while implementation is still in
  progress so they are not lost between sessions

Entry template:

```markdown
## Unreleased

### Milestone N — Short Title (YYYY-MM-DD)

- [x] YYYY-MM-DD description
```

## Unreleased

### GATK Milestone A Step 02 — variant_calling_env + registry skeleton (2026-04-21)

- [x] 2026-04-21 added `VARIANT_CALLING_WORKFLOW_NAME`, `VARIANT_CALLING_RESULTS_PREFIX`,
  and `VARIANT_CALLING_SIF_DEFAULT` constants to `src/flytetest/config.py`.
- [x] 2026-04-21 added `variant_calling_env` (`TaskEnvironmentConfig` with 4 CPU / 16 GiB)
  to `TASK_ENVIRONMENT_CONFIGS` and exposed alias in `src/flytetest/config.py`.
- [x] 2026-04-21 created `src/flytetest/registry/_variant_calling.py` with empty
  `VARIANT_CALLING_ENTRIES` tuple; wired into `REGISTRY_ENTRIES` in `__init__.py`
  (replacing the `_gatk.py` placeholder import).
- [x] 2026-04-21 updated `AGENTS.md` and `.codex/registry.md` with `_variant_calling.py`
  family listing; noted `_gatk.py` as reference-only.
- [x] 2026-04-21 added scaffolding smoke test `test_variant_calling_family_registered`
  to `tests/test_registry.py` (deleted in Step 03).

### GATK Milestone A Step 03 — create_sequence_dictionary task + registry entry (2026-04-21)

- [x] 2026-04-21 created `src/flytetest/tasks/variant_calling.py` with
  `create_sequence_dictionary` task: runs `gatk CreateSequenceDictionary -R …
  -O …` via `run_tool` + Apptainer, emits `run_manifest.json` via
  `build_manifest_envelope` (stage `"create_sequence_dictionary"`).
- [x] 2026-04-21 added `create_sequence_dictionary` `RegistryEntry` to
  `VARIANT_CALLING_ENTRIES` in `src/flytetest/registry/_variant_calling.py`
  (pipeline_family `"variant_calling"`, pipeline_stage_order 1).
- [x] 2026-04-21 deleted Step 02 scaffolding test
  `test_variant_calling_family_registered` from `tests/test_registry.py`.
- [x] 2026-04-21 added `tests/test_variant_calling.py` with 4 tests covering
  registry entry shape, correct GATK command invocation, default SIF fallback,
  and manifest emission — all passing.

### GATK Milestone A Step 01 — Planner types for variant calling (2026-04-21)

- [x] 2026-04-21 added `AlignmentSet`, `VariantCallSet`, `KnownSites` planner
  dataclasses to `src/flytetest/planner_types.py` (inherit
  `PlannerSerializable`; `VariantCallSet.variant_type` discriminates GVCF vs
  VCF; `KnownSites` carries VQSR-facing fields for forward compatibility).
- [x] 2026-04-21 extended `__all__` in `planner_types.py` to export the three
  new types.
- [x] 2026-04-21 added round-trip coverage in `tests/test_planner_types.py`:
  `test_alignment_set_round_trips`,
  `test_variant_call_set_round_trips_gvcf`,
  `test_variant_call_set_round_trips_vcf`,
  `test_known_sites_round_trips_with_vqsr_fields`,
  `test_known_sites_defaults_minimal` — 13/13 passing.

### Track A Step A4 — Rewire types/assets.py to shared serialization module (2026-04-21)

- [x] 2026-04-21 removed `_serialize_manifest_value()`, `_is_optional_manifest_type()`,
  `_deserialize_manifest_value()` from `src/flytetest/types/assets.py`
- [x] 2026-04-21 `ManifestSerializable` now inherits `SerializableMixin` with
  `serialize_value_full` + `deserialize_value_coercing` (asset layer)
- [x] 2026-04-21 all private helpers now live only in `serialization.py`; 658 tests pass

### MCP Reshape Step 30 — Seed-bundle audit for fresh-clone honesty (2026-04-21)

- [x] 2026-04-21 added `ResourceBundle.fetch_hints` — optional actionable
  instructions (apptainer pull command, fixture-staging pointers) appended to
  `reasons` when a bundle is unavailable, so `list_bundles()` / `load_bundle()`
  point the scientist at a concrete recovery path instead of a generic
  "missing" message.
- [x] 2026-04-21 populated fetch_hints for all four seeded bundles
  (`braker3_small_eukaryote`, `m18_busco_demo`, `protein_evidence_demo`,
  `rnaseq_paired_demo`), citing `scripts/rcc/download_minimal_images.sh` for
  container pulls and `scripts/rcc/README.md` for fixture layout.
- [x] 2026-04-21 added two bundle-honesty tests in `tests/test_bundles.py`:
  `test_seeded_bundles_report_honestly` (unavailable bundles must report a
  path or actionable verb) and `test_showcase_bundle_is_available_in_repo`
  (the bundle cited in `docs/mcp_showcase.md` is available OR has fetch_hints
  — no dead-end walkthroughs).
- Kept all four seeded bundles: multi-GB biology fixtures (FASTA, BAM, SIF
  containers, BUSCO lineages) cannot be checked into git, so the honest
  contract is structural availability reporting + actionable fetch_hints.
  Verified in a clean worktree at `/tmp/ft-clean`:
  `python -c "import flytetest.server"` succeeds with no `data/` directory,
  and every unavailable bundle emits a scientist-actionable reasons list.

### MCP Reshape Step 28 — Docs and agent-context refresh (2026-04-21)

Closes the MCP Surface Reshape milestone (Steps 1–28; tracker:
`docs/mcp_reshape/checklist.md`).  This entry consolidates the scientist-
facing changes that landed across Steps 16–27 so downstream callers can find
the BC break and recovery path in one place, and records the Step 28 docs
refresh itself.

**BC break — `run_task` / `run_workflow` input shape.** The old flat `inputs=`
dict is gone.  Both tools now accept a typed surface and bundle-shaped dicts
from `load_bundle` spread directly into either:

```python
# Before (M21-era)
run_task(
    task_name="busco_assess_proteins",
    task_inputs={
        "repeat_filter_results": "/path/to/results/repeat_filter_results_...",
        "busco_lineages_text": "eukaryota_odb10",
    },
)

# After (M28)
run_task(
    "busco_assess_proteins",
    bindings={
        "QualityAssessmentTarget": {
            "$manifest": "/path/to/results/repeat_filter_results_.../run_manifest.json",
            "output_name": "repeat_filter_results",
        },
    },
    inputs={"busco_lineages_text": "eukaryota_odb10"},
    resources={"execution_profile": "local"},
    source_prompt="Assess repeat-filtered proteins with BUSCO",
)
```

Declines now arrive as structured `PlanDecline` payloads with
`suggested_bundles`, `suggested_prior_runs`, and `next_steps` channels instead
of bare error strings; successes return `RunReply` / `DryRunReply` dataclasses
(`src/flytetest/mcp_replies.py`).  No compatibility shim is provided — callers
using the old shape must migrate.

Milestone highlights rolled up:

- [x] 2026-04-20 removed prose-parsing heuristics from `planning.py`
  (`_extract_prompt_paths`, `_classify_target`, execution-profile regex parsing)
  — structured planning is now the only entrypoint (Step 16).
- [x] 2026-04-20 reshaped `run_task` and `run_workflow` onto the typed
  `bindings + inputs + resources + execution_profile + runtime_images +
  tool_databases + source_prompt + dry_run` surface (Steps 21, 22).
- [x] 2026-04-20 added the `$ref` binding grammar (durable reuse of prior-run
  outputs) alongside the existing `$manifest` and raw-path forms, with
  exact-name type compatibility checks in `_materialize_bindings` (Steps 13, 14).
- [x] 2026-04-21 added `bundles.py` with `ResourceBundle` + `list_bundles` /
  `load_bundle` MCP tools; availability is checked at call time so new family
  bundles are a one-line append (Steps 4, 25).
- [x] 2026-04-21 added `staging.py::check_offline_staging` and wired it into
  `SlurmWorkflowSpecExecutor.submit` as a preflight gate; unreachable
  containers, tool databases, or input paths short-circuit submission with
  structured findings instead of silent offline failures (Steps 5, 23).
- [x] 2026-04-21 added `validate_run_recipe(artifact_path, execution_profile,
  shared_fs_roots)` as an inspect-before-execute MCP tool (Step 24).
- [x] 2026-04-21 reframed `server.py` decline routing through
  `suggested_bundles` / `suggested_prior_runs` / `next_steps` and wired an
  exception-to-decline translator in `_execute_run_tool` (Steps 19, 20).
- [x] 2026-04-21 documented the resource-hint handoff: registry
  `execution_defaults` may seed `slurm_resource_hints`, but `queue` and
  `account` must always come from the user (Step 27; `QUEUE_ACCOUNT_HANDOFF`
  policy constant in `mcp_contract.py`).
- [x] 2026-04-20 changed `recipe_id` format to
  `<YYYYMMDDThhmmss.mmm>Z-<target_name>` (Step 7); composed novel DAGs fall
  back to `composed-<first_stage>_to_<last_stage>`.

Step 28 docs refresh — files touched:

- [x] 2026-04-21 updated `AGENTS.md` Project Structure (added `bundles.py`,
  `staging.py`, `errors.py`, `mcp_replies.py` and the `validate_run_recipe` /
  `run_workflow` / `list_bundles` / `load_bundle` tool surface) and the
  Prompt/MCP/Slurm section (experiment loop + preflight staging invariant +
  bundle-spread recovery path).
- [x] 2026-04-21 updated `DESIGN.md` Overview (family-pluggability sentence),
  §6.2 (added `list_bundles`, `load_bundle`, `run_workflow`, marked `prepare_*`
  as power tools, added recipe_id format note), and §7.5 (referenced
  `check_offline_staging` by name and documented the shared-FS enforcement
  posture).
- [x] 2026-04-21 refreshed `README.md` Current Status so the experiment loop
  is the primary scientist entrypoint and `prepare_*` / `validate_run_recipe`
  are called out as inspect-before-execute power tools.
- [x] 2026-04-21 refreshed `.codex/registry.md`, `.codex/tasks.md`,
  `.codex/workflows.md`, `.codex/testing.md`, and `.codex/code-review.md`
  (Adding-a-Pipeline-Family walkthrough, bindings-vs-inputs split, scalar-
  inputs-only-at-MCP-boundary contract, new test patterns for bundle
  availability / `$ref` resolution / type-compat declines / staging findings /
  decline-to-bundles shape, MCP-layer-branch-free review rule).
- [x] 2026-04-21 mirrored those updates into `.codex/agent/registry.md`,
  `.codex/agent/task.md`, `.codex/agent/workflow.md`, `.codex/agent/test.md`,
  `.codex/agent/code-review.md`, and `.codex/agent/architecture.md`.
- [x] 2026-04-21 ticked Milestone 22 in `docs/realtime_refactor_checklist.md`
  (registry-driven pipeline tracker — subsumed by the registry restructure +
  `pipeline_family` / `pipeline_stage_order` fields that shipped in the MCP
  reshape sweep).
- [x] 2026-04-21 verified: `rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md`
  returned zero stale hits; `rg -n 'inputs\s*=\s*\{' docs/ .codex/` cross-
  checked against call-site snippets returned zero stale old-shape executable
  examples; `rg -n '_validate_bundles' docs/ .codex/` returned zero hits;
  `python -m compileall src/flytetest/` succeeded.

### MCP Reshape Step 27 — Reframe tool descriptions around the experiment loop (2026-04-21)

- [x] 2026-04-21 rewrote all 22 MCP tool descriptions in `src/flytetest/mcp_contract.py` using a `[group] verb-phrase` structure where group is one of `[experiment-loop]`, `[inspect-before-execute]`, or `[lifecycle]`; old ad-hoc one-liners replaced with experiment-oriented framings that cue LLM clients on when each tool fits the workflow.
- [x] 2026-04-21 introduced `TOOL_DESCRIPTIONS: dict[str, str]` in `mcp_contract.py` as the single source of truth for tool descriptions; `server.py` now passes `description=TOOL_DESCRIPTIONS[key]` to every `mcp.tool()` call so the FastMCP-facing description and the contract constant are always in sync.
- [x] 2026-04-21 grouped `MCP_TOOL_NAMES` into three named tuples (`EXPERIMENT_LOOP_TOOLS`, `INSPECT_TOOLS`, `LIFECYCLE_TOOLS`) and derived the combined `MCP_TOOL_NAMES` from them; added `RUN_TASK_TOOL_NAME = "run_task"` and `RUN_WORKFLOW_TOOL_NAME = "run_workflow"` constants and registered both as first-class MCP tools in `create_mcp_server()` (total tools: 22, was 20).
- [x] 2026-04-21 added `QUEUE_ACCOUNT_HANDOFF` policy constant; appended it to the descriptions for `run_task`, `run_workflow`, and `run_slurm_recipe` to enforce that queue and account always come from the user.
- [x] 2026-04-21 created `tests/test_mcp_contract.py` (4 test classes, 8 tests) covering: all registered tools have descriptions, no stale helper references, queue/account handoff present in required tools, group constants cover all tool names, ordering by group, `run_task`/`run_workflow` in experiment-loop, `run_slurm_recipe` in inspect group.
- [x] 2026-04-21 updated `FakeFastMCP.tool()` in `tests/test_server.py` and `_FakeFastMCP.tool()` in `tests/test_mcp_prompt_flows.py` to accept `description=` kwarg; full suite: 656 passed, 1 skipped, 41 subtests passed.

### MCP Reshape Step 26 — Call-site sweep for `run_task` / `run_workflow` BC migration (2026-04-21)

- [x] 2026-04-21 removed three deleted alias types (`AnnotationRefinementResultBundle`, `ConsensusAnnotationResultBundle`, `ProteinAlignmentChunkResult`) from `src/flytetest/tasks/pasa.py`, `src/flytetest/tasks/consensus.py`, and `src/flytetest/tasks/protein_evidence.py`: all three were empty subclasses that were merged back into their parent classes (`PasaGeneModelUpdateResultBundle`, `EvmConsensusResultBundle`, `ExonerateChunkAlignmentResult`) in the working-tree `types/assets.py` refactor; call sites in each task module now use the parent class directly.
- [x] 2026-04-21 removed three test methods that tested the deleted aliases (`AnnotationRefinementResultBundleTests.test_*_is_subtype_of_*`, `ProteinAlignmentChunkResultTests.test_*_is_subtype_of_*`, `ConsensusAnnotationResultBundleTests.test_*_is_subtype_of_*`) from `tests/test_pasa_update.py`, `tests/test_protein_evidence.py`, and `tests/test_consensus.py`; the containing test classes remain with their other test methods intact.
- [x] 2026-04-21 updated both `run_task` example snippets in `docs/mcp_showcase.md` from the old `task_name=` / `task_inputs=` kwargs to the new positional-name + `inputs=` / `source_prompt=` shape.
- [x] 2026-04-21 verified: `rg -n 'task_name=|task_inputs=' docs/` → zero hits in `run_task` contexts; `rg -n 'inputs=\{' tests/ | grep run_task` → one surviving hit (valid: `run_task("fastqc", inputs={"left":…})` is a "missing required input" decline test using the correct new shape); `pytest tests/` → 649 passed, 1 skipped, 38 subtests passed.

### MCP Reshape Step 25 — Register `list_bundles` / `load_bundle` MCP tools (2026-04-21)

- [x] 2026-04-21 added `list_bundles(pipeline_family=None)` and `load_bundle(name)` to `src/flytetest/server.py` as thin wrappers over `flytetest.bundles`: `list_bundles` delegates to `bundles.list_bundles` and returns structured availability entries; `load_bundle` delegates to `bundles.load_bundle`, converting raw `KeyError` for unknown bundle names into a structured decline (`supported=False`, `next_steps=["Call list_bundles() ..."]`) instead of propagating an uncaught exception.
- [x] 2026-04-21 registered both tools in `create_mcp_server()` after `list_available_bindings`; added `LIST_BUNDLES_TOOL_NAME = "list_bundles"` and `LOAD_BUNDLE_TOOL_NAME = "load_bundle"` to `mcp_contract.py`; appended both to `MCP_TOOL_NAMES`; imported both constants into `server.py`.
- [x] 2026-04-21 added `ListBundlesTests` (3 tests) and `LoadBundleTests` (4 tests) in `tests/test_server.py` covering: full listing with expected keys, pipeline-family filter, unknown-family empty result, happy-path load (6 result keys present), known-but-unavailable bundle (`supported=False` + `reasons`), unknown bundle name (structured decline, not KeyError), and experiment-loop smoke (`load_bundle` output spread into `run_workflow(dry_run=True)` returns `supported=True` + `recipe_id`).
- [x] 2026-04-21 fixed pre-existing `ImportError` fallback in `planning.supported_entry_parameters`: broadened `except ModuleNotFoundError` to also catch plain `ImportError` so that showcase modules with broken internal imports fall back to `_parameters_from_source` instead of propagating. This unblocked 8 pre-existing test failures in `RunWorkflowReshapeTests` and `ServerTests`.

### MCP Reshape Step 24 — Add `validate_run_recipe` MCP tool (inspect-before-execute) (2026-04-21)

- [x] 2026-04-21 added `validate_run_recipe(artifact_path, execution_profile, shared_fs_roots)` to `src/flytetest/server.py`: loads the frozen artifact, re-validates each `explicit_user_bindings` entry via `_materialize_bindings` (catching all exceptions into `findings` with `kind="binding"`), then runs `check_offline_staging` for staging findings; returns `asdict(ValidateRecipeReply(...))` with `supported`, `recipe_id` (artifact path stem), `execution_profile`, and `findings`. Never submits, writes, or mutates — safe to call repeatedly.
- [x] 2026-04-21 added conservative no-roots-declared logic: when `execution_profile="slurm"` and `shared_fs_roots=[]` (explicitly empty, not None), every staged path that exists locally is flagged as `not_on_shared_fs` (no false negatives); `shared_fs_roots=None` (default) skips the shared-FS check for both profiles.
- [x] 2026-04-21 imported `ValidateRecipeReply` from `flytetest.mcp_replies` and `check_offline_staging` from `flytetest.staging` in `server.py`; added `VALIDATE_RUN_RECIPE_TOOL_NAME = "validate_run_recipe"` to `mcp_contract.py` and appended it to `MCP_TOOL_NAMES`; registered `mcp.tool()(validate_run_recipe)` in `create_mcp_server()`.
- [x] 2026-04-21 added `ValidateRunRecipeTests` (7 tests) in `tests/test_server.py` covering: happy path (all bindings + staging clean → `supported=True`), `$ref` to unknown run_id (`kind="binding"`, run_id in reason), unreachable container (`kind="container"`), missing tool_database (`kind="tool_database"`), idempotency (two calls → identical findings), local profile without shared roots (flags missing paths, not shared-fs), slurm with empty roots (flags staged paths as `not_on_shared_fs`); verified with `python -m compileall` and `python -m pytest tests/test_server.py::ValidateRunRecipeTests` (7 passed).

### MCP Reshape Step 23 — Staging preflight gate for Slurm submit (2026-04-21)

- [x] 2026-04-21 added `runtime_images: dict[str, str] = field(default_factory=dict)` to `WorkflowSpec` in `src/flytetest/specs.py` so the executor can inspect container-image paths; updated `artifact_from_typed_plan` in `src/flytetest/spec_artifacts.py` to propagate the plan-level `runtime_images` into the frozen `WorkflowSpec` dict when the spec's own field is empty (same §8 resolution order as `tool_databases`).
- [x] 2026-04-21 added `shared_fs_roots: tuple[Path, ...] = ()` to `SlurmWorkflowSpecExecutor.submit` and `_submit_saved_artifact`; when non-empty, calls `check_offline_staging(artifact.workflow_spec, shared_fs_roots, execution_profile="slurm")` before any `sbatch` invocation and returns `SlurmSpecExecutionResult(supported=False, limitations=(...))` with human-readable finding strings when any path fails — format: `"{kind} '{key}' at {path}: {reason}"`.
- [x] 2026-04-21 extracted `shared_fs_roots` from `resources.get("shared_fs_roots", [])` in both `run_task` and `run_workflow` Slurm branches in `src/flytetest/server.py` and passed it through to `submit()`; staging is skipped when the caller does not supply roots, preserving existing behaviour for all non-staging tests.
- [x] 2026-04-21 added `StagingPreflightTests` (7 tests) in `tests/test_spec_executor.py` covering: unreachable container blocks sbatch, unreachable tool_database blocks sbatch, happy path calls sbatch once, broken symlink surfaces as `not_readable`, symlink inside shared root passes, symlink outside shared root blocked as `not_on_shared_fs`, local profile skips shared-fs check; added `StagingPreflightServerTests` (1 test) in `tests/test_server.py` verifying artifact stays on disk after staging failure and replay (without `shared_fs_roots`) succeeds after path is fixed; verified with `python -m compileall src/flytetest/spec_executor.py src/flytetest/server.py src/flytetest/specs.py src/flytetest/spec_artifacts.py` and `python -m pytest tests/test_spec_executor.py tests/test_staging.py tests/test_specs.py tests/test_registry.py` (125 passed, 34 subtests).

### MCP Reshape Step 22 — Reshape `run_workflow` (2026-04-21)

- [x] 2026-04-21 reshaped `run_workflow` in `src/flytetest/server.py` onto the typed `bindings + inputs + resources + execution_profile + runtime_images + tool_databases + source_prompt + dry_run` surface, symmetric with the Step 21 `run_task`; a bundle-shaped dict now spreads identically into either tool (§3 / §3b / §3g / §3i). The body validates bindings against `accepted_planner_types`, derives scalars via `_scalar_params_for_workflow` (entry parameters not already covered by typed bindings), materializes planner objects through `_materialize_bindings(...)` with the durable-asset index, freezes a `WorkflowSpec` artifact via `artifact_from_typed_plan` + `save_workflow_spec_artifact`, and dispatches through `LocalWorkflowSpecExecutor` or `SlurmWorkflowSpecExecutor` before returning `asdict(RunReply(...))` with `workflow_name` populated.
- [x] 2026-04-21 factored out `_braker_has_evidence(bindings, inputs) -> bool` so the BRAKER3 evidence-check limitation accepts satisfaction from either the legacy scalar path (`inputs.rnaseq_bam_path` / `inputs.protein_fasta_path`) or the typed form (`bindings.ProteinEvidenceSet` / `bindings.ReadSet`), preserving the bundle-spread contract.
- [x] 2026-04-21 extracted the previous direct dispatch into `_execute_workflow_direct(workflow_name, inputs, runner=...)` and flipped the `_local_node_handlers(..., workflow_runner=_execute_workflow_direct)` default so `run_local_recipe` / `run_slurm_recipe` still drive the CLI / direct-Python path, while the reshaped public `run_workflow` now owns the freeze + dispatch flow and cannot recurse through its own handler default.
- [x] 2026-04-21 added a `RunWorkflowReshapeTests` class in `tests/test_server.py` covering bundle-spread, BRAKER3 typed binding satisfaction, BRAKER3 legacy scalar satisfaction, BRAKER3 no-evidence decline, unknown-binding decline, freeze-to-disk, named outputs dict keyed by registry, empty-prompt advisory, `dry_run=True` (artifact exists, no run record, `DryRunReply` shape), chained dry-run → `run_local_recipe` with unchanged artifact bytes, and local non-zero exit → `execution_status="failed"`; retargeted two legacy `run_workflow` CLI tests at `_execute_workflow_direct`; verified with `python -m compileall src/flytetest/server.py` and `python -m pytest tests/` (630 passed, 1 skipped, 38 subtests).

### MCP Reshape Step 21 — Reshape `run_task` (2026-04-20)

- [x] 2026-04-20 reshaped `run_task` in `src/flytetest/server.py` onto the typed `bindings + inputs + resources + execution_profile + runtime_images + tool_databases + source_prompt + dry_run` surface described in the master plan §2 / §3b / §3g / §3i; the body validates bindings against the entry's `accepted_planner_types`, derives scalars via `_scalar_params_for_task` (TASK_PARAMETERS entries not already covered by typed bindings), materializes planner objects through `_materialize_bindings(...)` with the durable-asset index, freezes a `WorkflowSpec` artifact transparently via `artifact_from_typed_plan` + `save_workflow_spec_artifact`, and dispatches through `LocalWorkflowSpecExecutor` or `SlurmWorkflowSpecExecutor` before returning an `asdict(RunReply(...))`.
- [x] 2026-04-20 added `_collect_named_outputs(entry, run_record_path) -> (dict, list)` that projects `manifest["outputs"]` / `final_outputs` onto `entry.outputs[*].name` (§3b), emitting prominent advisories for missing required outputs and soft advisories for missing optional outputs; empty `source_prompt` appends the `_EMPTY_PROMPT_ADVISORY` limitation per §3i.
- [x] 2026-04-20 extracted the previous direct task dispatch into `_execute_task_direct(task_name, inputs)` so `_local_node_handlers(..., task_runner=_execute_task_direct)` continues to power `run_local_recipe` / `run_slurm_recipe`, while the reshaped public `run_task` now owns the freeze + dispatch flow and cannot recurse through its own handler default.
- [x] 2026-04-20 wired the run-tool body through `_execute_run_tool(...)` (Step 19) so typed resolver errors from `_materialize_bindings` translate to `PlanDecline`; local-executor `RuntimeError` from a node handler surfaces as `supported=True, execution_status="failed", exit_status=1` per §3g; slurm submit returns `execution_status="success", exit_status=None`.
- [x] 2026-04-20 added a `RunTaskReshapeTests` class in `tests/test_server.py` covering bundle-spread success, unknown-binding decline, missing-scalar decline, freeze-to-disk, named outputs dict, empty-prompt advisory, `dry_run=True` (artifact exists, no `run_record`, `DryRunReply` shape), chained dry-run → `run_local_recipe` with unchanged artifact bytes, and local non-zero exit → `execution_status="failed"`; updated legacy run_task tests (T1–T4) to use the new keyword-argument surface; verified with `python -m compileall src/flytetest/` and `python -m pytest tests/` (619 passed, 1 skipped, 38 subtests).



- [x] 2026-04-20 added `_execute_run_tool(fn, *, target_name, pipeline_family) -> dict` in `src/flytetest/server.py` as the tool-boundary wrapper that converts every `PlannerResolutionError` subclass into a typed `PlanDecline` with exception-type-aware `next_steps`, and lets any other exception propagate after emitting one ERROR log line with the §3e `tool_name` / `pipeline_family` / traceback fields.
- [x] 2026-04-20 wired translations for `UnknownRunIdError` (point at `list_available_bindings` + `.runtime/durable_asset_index.json`), `UnknownOutputNameError` (name the known outputs on the run), `ManifestNotFoundError` / `BindingPathMissingError` (point at `list_available_bindings` + readability check), and `BindingTypeMismatchError` (§7 — `produced_planner_types` guidance plus raw-path escape hatch).
- [x] 2026-04-20 covered every typed exception with `assertNoLogs("flytetest.server", level="ERROR")` + decline-shape assertions in `tests/test_server.py` and asserted the non-resolution propagation path emits one ERROR record carrying `tool_name` / `pipeline_family` / `exc_info`; verified with `python -m compileall src/flytetest/server.py tests/test_server.py` and `python -m pytest tests/test_server.py` (110 passed).

### MCP Reshape Step 18 — Operator-Side Logging (2026-04-20)

- [x] 2026-04-20 added `_LOG = logging.getLogger(__name__)` module-level loggers in `src/flytetest/resolver.py`, `src/flytetest/spec_executor.py`, and `src/flytetest/server.py` so the three §3e log sites share a common convention aligned with the existing `slurm_monitor.py` pattern.
- [x] 2026-04-20 wired the WARNING site in `_materialize_bindings`: `$ref` resolution failures now emit one `WARNING` line with the binding key, `run_id`, `output_name`, and exception reason (`recipe_id` is still pending at this stage) and re-raise without swallowing.
- [x] 2026-04-20 deferred the ERROR site (uncaught exceptions in `_execute_run_tool`) to Step 19 and the INFO site (`SlurmWorkflowSpecExecutor.submit` staging-preflight short-circuit) to Step 23; Step 18 lands the logger setup only at those modules so the emits drop in cleanly when the surrounding code is written.
- [x] 2026-04-20 covered the WARNING emission with `self.assertLogs("flytetest.resolver", level="WARNING")` in `tests/test_resolver.py` and verified with `python -m compileall src/flytetest/` and `python -m pytest tests/` (600 passed, 1 skipped, 38 subtests).

### MCP Reshape Step 16 — Structured Planning Only (2026-04-20)

- [x] 2026-04-20 removed the prose-parsing helpers from `src/flytetest/planning.py`, including prompt-path extraction, execution-profile/runtime-image regex parsing, and the keyword-scored `_classify_target` route.
- [x] 2026-04-20 reshaped `plan_typed_request` into a structured-only entrypoint keyed by `biological_goal`, `target_name`, and explicit structured inputs, while `plan_request` now does deterministic free-text matching against exact `biological_stage` / entry-name values before composition fallback.
- [x] 2026-04-20 preserved composition fallback and approval gating, added the empty-`source_prompt` advisory to structured planning replies, and widened decline replies with `limitations`, `next_steps`, and the other structured recovery fields expected by the reshape plan.
- [x] 2026-04-20 migrated planning, server, artifact, executor, approval, and MCP prompt-flow coverage away from prose path parsing toward exact-stage prompts or explicit structured bindings/runtime inputs, then verified with `/home/rmeht/Projects/flyteTest/.venv/bin/python -m compileall src/flytetest/planning.py`, the deleted-helper `rg` check, and `/home/rmeht/Projects/flyteTest/.venv/bin/python -m pytest tests/` (596 passed, 1 skipped, 38 subtests passed).

### Open TODOs

- [ ] **Confirm AUGUSTUS_CONFIG_PATH fix for BRAKER3 container runs** — `.runtime/augustus_config/`
      exists at repo root (gitignored, 171 species configs from prior runs) and was likely
      created to work around AUGUSTUS writing species configs into a read-only container path.
      On the next real BRAKER3 run: confirm whether `AUGUSTUS_CONFIG_PATH` must be set and
      bind-mounted explicitly. Document the confirmed fix in `docs/tool_refs/braker3.md`.

- [ ] **Confirm RepeatMasker library path on RCC** — `repeatmasker_4.2.3.sif` requires a
      Dfam/RepBase repeat library bind-mounted at runtime. Confirm the shared library path
      on RCC before the first real annotation run. Document in `docs/annotation_pipeline_setup.md`.

- [ ] **Confirm eggNOG database path on RCC** — `eggnog_mapper_2.1.13.sif` requires the
      eggNOG database (~50 GB) staged and bind-mounted. Confirm whether it is already on a
      shared project path or needs to be downloaded. Document in `docs/annotation_pipeline_setup.md`.

- [ ] **Verify EVM 2.x command flags** — `evidencemodeler_2.1.0.sif` uses the Python 2.x
      CLI, not the Perl 1.x scripts. Confirm that EVM task wrappers use the correct 2.x
      flags before the first real run.

### MCP Reshape Step 15 — Typed Binding Discovery (2026-04-20)

- [x] 2026-04-20 added `_path_fields_for()` and typed planner-field discovery to `list_available_bindings`, exposing a new additive `typed_bindings` field while preserving the existing scalar-parameter `bindings` payload unchanged.
- [x] 2026-04-20 kept the current best-effort scan model intact by reusing the existing extension-based discovery rules for planner Path fields, including run-directory discovery for `_dir` and `_results` style fields.
- [x] 2026-04-20 added server coverage for the additive reply shape, including empty existing-task behavior and a synthetic new planner type that appears in `typed_bindings` without any MCP-layer registration changes.
- [x] 2026-04-20 verified the slice with `/home/rmeht/Projects/flyteTest/.venv/bin/python -m compileall src/flytetest/server.py` and `/home/rmeht/Projects/flyteTest/.venv/bin/python -m pytest tests/test_server.py` (104 passed).

### MCP Reshape Step 14 — Binding Grammar and Durable Reuse (2026-04-20)

- [x] 2026-04-20 added `produced_type` to durable asset refs and populated it during local run indexing when the producing entry declares an unambiguous planner type or the manifest records per-output planner-type metadata.
- [x] 2026-04-20 extended `resolver._materialize_bindings()` with exact-name compatibility checks for both `$manifest` and `$ref` bindings while preserving raw-path bindings as the deliberate type-check escape hatch.
- [x] 2026-04-20 taught manifest-backed type checks to accept both current workflow-level manifests and task-stage manifests by consulting the top-level `workflow` or `stage` key and preferring per-output type metadata when present.
- [x] 2026-04-20 added focused resolver coverage for raw, `$manifest`, `$ref`, mixed-form, and mismatch cases, plus durable-asset-index round-trip coverage for the new `produced_type` field.

### MCP Reshape Step 13 — Resolver Typed Exceptions (2026-04-20)

- [x] 2026-04-20 added `BindingTypeMismatchError` to the typed planner-resolution hierarchy so the resolver path now has the missing subclass the reshape plan expects before Step 14 adds full type-compatibility checks.
- [x] 2026-04-20 added `_materialize_bindings()` to `src/flytetest/resolver.py` with typed failure handling for raw-path bindings, manifest-backed bindings, and durable `$ref` lookups, including binding-key context in the surfaced exception messages.
- [x] 2026-04-20 added focused Step 13 coverage in `tests/test_errors.py` and `tests/test_resolver.py` for `BindingTypeMismatchError`, missing raw paths, missing manifest sidecars, unknown durable `run_id` values, and unknown durable `output_name` values.
- [x] 2026-04-20 verified the slice with `/home/rmeht/Projects/flyteTest/.venv/bin/python -m compileall src/flytetest/resolver.py` and `/home/rmeht/Projects/flyteTest/.venv/bin/python -m pytest tests/test_resolver.py tests/test_errors.py` (32 passed).

### MCP Reshape Step 12 — Execution Defaults Layering (2026-04-20)

- [x] 2026-04-20 expanded showcased registry `execution_defaults` for BRAKER3, BUSCO, and Exonerate entries with seeded `runtime_images`, `tool_databases`, and `module_loads` where the repo already had concrete bundle-backed values.
- [x] 2026-04-20 updated `plan_typed_request` to resolve environment metadata in the documented order: entry defaults, then bundle overrides, then explicit per-call overrides for `runtime_images` and `tool_databases`, while `module_loads` continues to flow through `resource_request.module_loads` and `env_vars` remains bundle-only above the entry default.
- [x] 2026-04-20 froze the resolved environment into planning outputs by wiring `tool_databases` onto `WorkflowSpec`, preserving the selected runtime image in `BindingPlan`, and recording the full resolved environment in `workflow_spec.replay_metadata`.
- [x] 2026-04-20 verified the slice with `/home/rmeht/Projects/flyteTest/.venv/bin/python -m compileall src/flytetest/planning.py` and `/home/rmeht/Projects/flyteTest/.venv/bin/python -m pytest tests/test_planning.py` (25 passed).

### MCP Reshape Step 11 — Registry Manifest Contract Test (2026-04-20)

- [x] 2026-04-20 added `tests/test_registry_manifest_contract.py`, a registry-wide contract test that resolves showcased workflow entries to their owning task modules and asserts every declared registry output name is listed in `MANIFEST_OUTPUT_KEYS`.
- [x] 2026-04-20 kept the contract one-way: extra manifest keys remain allowed for internal audit fields, while missing declared output names fail the test.
- [x] 2026-04-20 marked Step 11 complete in `docs/mcp_reshape/checklist.md` after verifying the passing case and an in-memory negative case with a bogus registry output.

### MCP Reshape Step 10 — Manifest Output Keys (2026-04-20)

- [x] 2026-04-20 added module-level `MANIFEST_OUTPUT_KEYS` tuples to every task module under `src/flytetest/tasks/` as the source of truth for keys written under `manifest["outputs"]`.
- [x] 2026-04-20 included audit-only outputs in those tuples where applicable, including BUSCO's `summary_notation`, and exported the constant from task modules that already curate `__all__`.
- [x] 2026-04-20 verified the slice with `/home/rmeht/Projects/flyteTest/.venv/bin/python -m compileall src/flytetest/tasks/` and one `MANIFEST_OUTPUT_KEYS` definition per task module.

### Post-Refactor Documentation (2026-04-16)

Checklist: `docs/dataserialization/checklist.md` → Post-Refactor Documentation

- [x] 2026-04-16 created `.codex/registry.md` — full registry package guide
  covering package structure, field semantics, how to add entries, how
  `showcase_module` controls MCP exposure, `pipeline_stage_order` conventions,
  and `to_dict()` serialization contract.
- [x] 2026-04-16 created `.codex/agent/registry.md` — specialist role prompt for
  delegated registry entry work (Purpose/Read First/Role/Core Principles/Validation/
  Handoff pattern).
- [x] 2026-04-16 updated `AGENTS.md`: added `## Read Before Editing` registry row
  (`.codex/registry.md`) and replaced stale `## Project Structure` section with a
  complete orientation map of the registry package, core concept modules, tasks,
  workflows, and types.
- [x] 2026-04-16 updated `CLAUDE.md`: added "Registry entries and pipeline families"
  row to specialist guides table pointing at `.codex/registry.md` and
  `.codex/agent/registry.md`.
- [x] 2026-04-16 updated `DESIGN.md` layout section (was "as of 2026-04-14"):
  expanded the `registry/` package tree with all 9 submodule files and their
  entry counts. Updated date to 2026-04-16.
- [x] 2026-04-16 fixed all 12 stale `src/flytetest/registry.py` references across
  9 `.codex/` files (`workflows.md`, `documentation.md`, `testing.md`,
  `code-review.md`, `agent/workflow.md`, `agent/code-review.md`, `agent/test.md`,
  `agent/architecture.md`, `agent/README.md`). Verified 0 hits in
  `.codex/ AGENTS.md CLAUDE.md DESIGN.md`.

### B5 — GATK Proof of Concept (2026-04-16)

Checklist: `docs/dataserialization/checklist.md` → Step B5

- [x] 2026-04-16 created `src/flytetest/registry/_gatk.py` with one entry:
  `gatk_haplotype_caller` (category=workflow, pipeline_family=variant_calling,
  pipeline_stage_order=3). Inputs and outputs modelled on the real GATK4
  HaplotypeCaller task in the Stargazer reference project.
  `showcase_module=""` — no handler or planning coverage yet.
- [x] 2026-04-16 added `from flytetest.registry._gatk import GATK_ENTRIES` and
  `+ GATK_ENTRIES` to `src/flytetest/registry/__init__.py`.
  `len(REGISTRY_ENTRIES)` is now 74 (was 73).
- [x] 2026-04-16 verified: entry visible in `get_pipeline_stages("variant_calling")`,
  absent from `SUPPORTED_TARGET_NAMES`, `to_dict()` does not leak `showcase_module`.
- [x] 2026-04-16 full test suite: 495 tests, all pass (1 skipped).

### B3+B4 — MCP/Server Derivation from Registry (2026-04-16)

Checklist: `docs/dataserialization/checklist.md` → Steps B3+B4

- [x] 2026-04-16 added `showcase_module: str` field (set in B1+B2, populated now)
  to 12 registry entries across `_annotation.py`, `_protein_evidence.py`,
  `_postprocessing.py`, and `_rnaseq.py`. Values match the original hardcoded
  `module_name` paths in the deleted `ShowcaseTarget(...)` blocks.
- [x] 2026-04-16 added `_resolve_source_path(module_name)` helper to
  `mcp_contract.py`; derives the filesystem path for any `flytetest.*` module
  without hardcoding directory segments.
- [x] 2026-04-16 replaced 12 hardcoded `ShowcaseTarget(...)` blocks in
  `mcp_contract.py` with a single generator expression that iterates
  `REGISTRY_ENTRIES` and yields one `ShowcaseTarget` per entry where
  `showcase_module` is set. `SHOWCASE_TARGETS_BY_NAME`, `SUPPORTED_TARGET_NAMES`,
  `SUPPORTED_WORKFLOW_NAMES`, and `SUPPORTED_TASK_NAMES` continue to derive from
  `SHOWCASE_TARGETS` unchanged.
- [x] 2026-04-16 deleted 8 `SUPPORTED_*_NAME` constants from `mcp_contract.py`
  (`SUPPORTED_FASTQC_TASK_NAME`, `SUPPORTED_GFFREAD_PROTEINS_TASK_NAME`,
  `SUPPORTED_BUSCO_WORKFLOW_NAME`, `SUPPORTED_EGGNOG_WORKFLOW_NAME`,
  `SUPPORTED_AGAT_WORKFLOW_NAME`, `SUPPORTED_AGAT_CONVERSION_WORKFLOW_NAME`,
  `SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME`, `SUPPORTED_TABLE2ASN_WORKFLOW_NAME`).
  The 4 policy constants used by `planning.py` as branch points are preserved.
- [x] 2026-04-16 updated `SHOWCASE_LIMITATIONS` and `LIST_ENTRIES_LIMITATIONS`
  in `mcp_contract.py` to derive the name list from `SUPPORTED_TARGET_NAMES`;
  surrounding prose kept as curated text.
- [x] 2026-04-16 simplified `_local_node_handlers()` in `server.py`: removed
  8 explicit per-workflow-name dict entries; replaced with
  `{name: workflow_handler for name in SUPPORTED_WORKFLOW_NAMES}` plus the
  existing `{name: task_handler for name in SUPPORTED_TASK_NAMES}`.
- [x] 2026-04-16 updated `test_server.py`: moved the 6 deleted constants to
  aliased imports from `flytetest.config`; added
  `test_supported_target_names_match_expected_set` safety test.
- [x] 2026-04-16 full test suite: 495 tests, all pass (1 skipped).

### B1+B2 — Registry Package Restructure (2026-04-16)

Checklist: `docs/dataserialization/checklist.md` → Step B1+B2

- [x] 2026-04-16 converted `src/flytetest/registry.py` (2679-line monolith)
  into `src/flytetest/registry/` package in one atomic change, no intermediate
  `_registry_legacy.py` file.
- [x] 2026-04-16 created `src/flytetest/registry/_types.py` with the exact
  dataclass definitions (`Category`, `InterfaceField`,
  `RegistryCompatibilityMetadata`, `RegistryEntry`); added
  `showcase_module: str = ""` field to `RegistryEntry`; overrode `to_dict()`
  to exclude `showcase_module` from serialized output, preserving the public
  payload shape for all downstream consumers.
- [x] 2026-04-16 created 7 family files (entries/counts):
  `_transcript_evidence.py` (8), `_consensus.py` (16),
  `_protein_evidence.py` (6), `_annotation.py` (5), `_evm.py` (12),
  `_postprocessing.py` (21), `_rnaseq.py` (5). Total: 73 entries.
  Each entry is self-contained with inline `RegistryCompatibilityMetadata`
  (resources + slurm hints folded in); `_WORKFLOW_COMPATIBILITY_METADATA`,
  `_WORKFLOW_LOCAL_RESOURCE_DEFAULTS`, `_WORKFLOW_SLURM_RESOURCE_HINTS` dicts
  and both merge helpers eliminated.
- [x] 2026-04-16 created `src/flytetest/registry/__init__.py` re-exporting
  all types plus query functions (`list_entries`, `get_entry`,
  `get_pipeline_stages`) verbatim; all existing
  `from flytetest.registry import ...` consumers unchanged.
- [x] 2026-04-16 deleted `src/flytetest/registry.py` monolith.
- [x] 2026-04-16 full test suite: 494 tests, all pass (1 skipped).

### Milestone 26 — Consensus Annotation Generic Asset Surface (2026-04-16)

- [x] 2026-04-16 introduced `ConsensusAnnotationResultBundle` as a biology-
  facing generic sibling dataclass that inherits all fields from
  `EvmConsensusResultBundle` unchanged. The 7 internal EVM computation types
  remain EVM-named because they are internal implementation details. *(types/assets.py)*
- [x] 2026-04-16 updated `consensus.py` `collect_evm_results()` to construct
  `ConsensusAnnotationResultBundle` and emit both the generic manifest asset key
  `consensus_annotation_result_bundle` and the legacy key
  `evm_consensus_result_bundle` for backward replay compatibility. *(tasks/consensus.py)*
- [x] 2026-04-16 exported `ConsensusAnnotationResultBundle` from
  `flytetest.types` and `flytetest` package top-level.
- [x] 2026-04-16 added 3 tests to `tests/test_consensus.py`: subtype isinstance
  check, generic manifest key present, legacy manifest key present.
  Full suite: 421 tests, 1 skipped.

### Milestone 25 — PASA Refinement Generic Asset Surface (2026-04-16)

- [x] 2026-04-16 introduced `AnnotationRefinementResultBundle` as a biology-
  facing generic sibling dataclass that inherits all fields from
  `PasaGeneModelUpdateResultBundle` unchanged. *(types/assets.py)*
- [x] 2026-04-16 updated `pasa.py` `collect_pasa_update_results()` to construct
  `AnnotationRefinementResultBundle` and emit both the generic manifest asset key
  `annotation_refinement_bundle` and the legacy key `pasa_gene_model_update_bundle`
  for backward replay compatibility. *(tasks/pasa.py)*
- [x] 2026-04-16 exported `AnnotationRefinementResultBundle` from `flytetest.types`
  and `flytetest` package top-level.
- [x] 2026-04-16 added 3 tests to `tests/test_pasa_update.py`: subtype isinstance
  check, generic manifest key present, legacy manifest key present.
  Full suite: 418 tests, 1 skipped.

### Milestone 24 — Protein Evidence Generic Alignment Asset Surface (2026-04-16)

- [x] 2026-04-16 added `ProteinAlignmentChunkResult` as a biology-facing
  generic sibling dataclass that inherits all fields from
  `ExonerateChunkAlignmentResult` unchanged. *(types/assets.py)*
- [x] 2026-04-16 updated `protein_evidence.py` `exonerate_concat_results()` to
  construct raw chunk assets as `ProteinAlignmentChunkResult` and emit generic
  keys alongside legacy keys in new manifests. Historical manifests remain
  replayable unchanged. *(tasks/protein_evidence.py)*
- [x] 2026-04-16 exported `ProteinAlignmentChunkResult` from `flytetest.types`
  and `flytetest` public namespaces.
- [x] 2026-04-16 added 4 tests to `tests/test_protein_evidence.py`: subtype
  check, generic output keys present, legacy keys still present, both asset
  keys in manifest. All 415 tests pass.

### Milestone 23 — TransDecoder Generic Asset Surface (2026-04-16)

- [x] 2026-04-16 added `CodingPredictionResult` as a biology-facing generic
  sibling dataclass that inherits all fields from `TransDecoderPredictionResult`
  unchanged. *(types/assets.py)*
- [x] 2026-04-16 updated `transdecoder.py` `collect_transdecoder_results()` to
  construct the result as `CodingPredictionResult` and emit both
  `"coding_prediction"` (preferred generic key) and `"transdecoder_prediction"`
  (legacy compatibility key) in new manifests. *(tasks/transdecoder.py)*
- [x] 2026-04-16 exported `CodingPredictionResult` from `flytetest.types` and
  `flytetest` public namespaces.
- [x] 2026-04-16 added 3 tests to `tests/test_transdecoder.py`: subtype check,
  new manifest includes `coding_prediction` key, legacy `transdecoder_prediction`
  key still present.

### Milestone 22 — Registry-Driven Pipeline Tracker (2026-04-16)

- [x] 2026-04-16 added `pipeline_family: str = ""` and `pipeline_stage_order: int = 0`
  to `RegistryCompatibilityMetadata` (frozen dataclass) with safe defaults so all
  existing construction sites remain valid. *(registry.py → registry/_types.py)*
- [x] 2026-04-16 populated all 17 `_WORKFLOW_COMPATIBILITY_METADATA` entries with
  `pipeline_family="annotation"` and `pipeline_stage_order=1..15` for the 15 annotation
  pipeline workflows; `busco_assess_proteins` and `rnaseq_qc_quant` keep defaults.
- [x] 2026-04-16 added `get_pipeline_stages(family: str) -> list[tuple[str, str]]`
  pure function; returns `(workflow_name, biological_stage_label)` pairs ordered by
  `pipeline_stage_order`, empty list for unknown family. *(registry/__init__.py)*
- [x] 2026-04-16 replaced the hardcoded `ANNOTATION_PIPELINE_STAGES` literal in
  `pipeline_tracker.py` with `get_pipeline_stages("annotation")`; removed the 15
  `config.py` workflow-name imports that were no longer needed. *(pipeline_tracker.py)*
- [x] 2026-04-16 added 3 tests to `test_pipeline_tracker.py`: annotation stage
  count/order, empty-family guard, standalone-workflow exclusion.

### Milestone 21d — Pipeline Status Tracker (2026-04-15)

- [x] 2026-04-15 added `src/flytetest/pipeline_tracker.py` with
  `ANNOTATION_PIPELINE_STAGES` (15-stage ordered list), `StageStatus` dataclass,
  `get_annotation_pipeline_status(runs_dir)`, and `get_pipeline_summary(stages)`.
  Reads durable `SlurmRunRecord` files from `.runtime/runs/` without modification.
  Self-contained — no imports from `server.py`. *(pipeline_tracker.py)*
- [x] 2026-04-15 added `GET_PIPELINE_STATUS_TOOL_NAME = "get_pipeline_status"` to
  `mcp_contract.py` and appended it to `MCP_TOOL_NAMES`.
- [x] 2026-04-15 added `_get_pipeline_status_impl()` and `get_pipeline_status()`
  to `server.py`; registered in `create_mcp_server`. *(server.py)*
- [x] 2026-04-15 added `tests/test_pipeline_tracker.py` with 11 synthetic tests
  covering all-pending, completed/failed/running/timeout states, most-recent-wins,
  summary counts, next-pending-stage label, none-when-all-complete.

### Milestone 21c — Biology Closure: table2asn NCBI Submission (2026-04-15)

- [x] 2026-04-15 added `TABLE2ASN_WORKFLOW_NAME`, `TABLE2ASN_RESULTS_PREFIX`,
  `TaskEnvironmentConfig` entry, and `table2asn_env` handle to `config.py`.
- [x] 2026-04-15 added `SUPPORTED_TABLE2ASN_WORKFLOW_NAME` constant and new
  `ShowcaseTarget(category="workflow", module_name="flytetest.workflows.agat")`
  entry to `mcp_contract.py`; updated `SHOWCASE_LIMITATIONS` and
  `LIST_ENTRIES_LIMITATIONS` strings.
- [x] 2026-04-15 implemented `_agat_cleaned_gff3(results_dir)` helper and
  `table2asn_submission` task in `src/flytetest/tasks/agat.py`. Command shape
  follows `docs/braker3_evm_notes.md`: `-M n -J -c w -euk -gaps-min 10
  -l proximity-ligation -Z -V b` plus conditional `-locus-tag-prefix` and `-j`
  flags. Writes `run_manifest.json`. *(tasks/agat.py)*
- [x] 2026-04-15 added `annotation_postprocess_table2asn` workflow to
  `src/flytetest/workflows/agat.py`; updated `__all__`. *(workflows/agat.py)*
- [x] 2026-04-15 wired handler in `server.py` `_local_node_handlers()` dict and
  added QualityAssessmentTarget `input_name` mapping entry.
- [x] 2026-04-15 added `annotation_postprocess_table2asn` to registry entry,
  compatibility metadata, local resource defaults, and Slurm resource hints.
- [x] 2026-04-15 added T19–T23: server tests (run_task declines
  `table2asn_submission`, list_entries includes workflow entry) and task tests
  (correct command flags, manifest written, FileNotFoundError when no GFF3).
  Full suite: 393 tests, 1 skipped.
- [x] 2026-04-15 updated `docs/mcp_showcase.md`, `docs/capability_maturity.md`,
  `README.md`, and `docs/realtime_refactor_checklist.md` (M21c marked Complete).

### Milestone 21b — HPC Observability (2026-04-15)

- [x] 2026-04-15 added `FETCH_JOB_LOG_TOOL_NAME`, `WAIT_FOR_SLURM_JOB_TOOL_NAME`,
  `RUN_RECIPE_RESOURCE_URI_PREFIX`, `RESULT_MANIFEST_RESOURCE_URI_PREFIX`
  constants to `mcp_contract.py`; updated `MCP_TOOL_NAMES` (now 16 entries)
  and `MCP_RESOURCE_URIS` (now 6 entries). *(mcp_contract.py)*
- [x] 2026-04-15 implemented `fetch_job_log(log_path, tail_lines=100)` reusing
  the existing `_read_text_tail` path-traversal guard with `DEFAULT_RUN_DIR`
  as `allowed_root`. *(server.py)*
- [x] 2026-04-15 implemented `wait_for_slurm_job(run_record_path, timeout_s=300,
  poll_interval_s=15)`: polls `_monitor_slurm_job_impl` until `final_scheduler_state`
  is non-None or the timeout expires; returns standard monitor payload plus
  `timed_out: bool`. Poll interval floored at 5 seconds. *(server.py)*
- [x] 2026-04-15 implemented `resource_run_recipe(path)` and
  `resource_result_manifest(path)` with `REPO_ROOT`-scoped path validation.
  Registered all new tools and resources in `create_mcp_server()`. *(server.py)*
- [x] 2026-04-15 added 8 new tests T11–T18 in `tests/test_server.py`; full suite
  now 388 tests passing, 1 skipped.
- [x] 2026-04-15 updated `docs/mcp_showcase.md` with HPC Observability section;
  updated `docs/capability_maturity.md` with job log fetching and polling rows.

### Milestone 21 — Ad Hoc Task Execution Surface (2026-04-15)

- [x] 2026-04-15 added `SUPPORTED_FASTQC_TASK_NAME`, `SUPPORTED_GFFREAD_PROTEINS_TASK_NAME`,
      `LIST_AVAILABLE_BINDINGS_TOOL_NAME`, `GET_RUN_SUMMARY_TOOL_NAME`,
      `INSPECT_RUN_RESULT_TOOL_NAME` constants to `mcp_contract.py`; added `fastqc`
      and `gffread_proteins` `ShowcaseTarget(category="task")` entries to `SHOWCASE_TARGETS`;
      updated `SUPPORTED_TARGET_NAMES`, `MCP_TOOL_NAMES`, `SHOWCASE_LIMITATIONS`, and
      `LIST_ENTRIES_LIMITATIONS` accordingly. *(mcp_contract.py)*
- [x] 2026-04-15 refactored `run_task()` to use `SUPPORTED_TASK_NAMES` (derived from
      showcase) and a new `TASK_PARAMETERS` dispatch dict instead of hardcoded
      per-task if-blocks; added `fastqc` and `gffread_proteins` dispatch branches;
      updated `_local_node_handlers()` to use `SUPPORTED_TASK_NAMES`. *(server.py)*
- [x] 2026-04-15 implemented TODO 16 `list_available_bindings(task_name, search_root=None)`:
      depth-3 heuristic file scan with per-parameter FASTA/GFF/FASTQ extension
      patterns; scalar parameters return a hint string; unknown tasks return
      `supported=False`. *(server.py)*
- [x] 2026-04-15 implemented TODO 12 `get_run_summary(run_dir, limit=20)`: offline
      scan of `slurm_run_record.json` and `local_run_record.json` files; groups by
      state; caps at `limit * 5` directories; returns `total_scanned`, `by_state`,
      and `recent` list. *(server.py)*
- [x] 2026-04-15 implemented TODO 17 `inspect_run_result(run_record_path)`: loads one
      run record (Slurm or local), returns structured summary with scheduler state,
      node results, and output paths; no scheduler calls. *(server.py)*
- [x] 2026-04-15 implemented TODO 15: added `difflib.get_close_matches()` in
      `_find_close_target_matches()` helper and wired into `_unsupported_typed_plan()`
      so near-miss target names in the prompt surface actionable suggestions. *(planning.py)*
- [x] 2026-04-15 registered `list_available_bindings`, `get_run_summary`,
      `inspect_run_result` in `create_mcp_server()`; MCP tool count now 14. *(server.py)*
- [x] 2026-04-15 added 10 new tests T1–T10 in `tests/test_server.py`; full suite now
      381 tests, all pass (1 skipped).

### Archive Migration and Policy Cleanup (2026-04-15)

- [x] 2026-04-15 moved 17 completed milestone plan files (M12–M21) from
  `docs/realtime_refactor_plans/` to `docs/realtime_refactor_plans/archive/`
  using `git mv`; milestones covered: 12, 13, 14, 15, 15-part-b, 16,
  16-part-2, 17, 18, 18a, 18b, 18c, 19, 19-part-b, 19-phase-a-audit, 20b,
  21; active plan files (22–25, 21b, 21c, dataclass-serialization,
  documentation-sweep, post-m17-audit) remain in the active plans directory
- [x] 2026-04-15 updated `AGENTS.md`, `.codex/documentation.md`,
  `.codex/agent/README.md`, `docs/realtime_refactor_plans/README.md`, and
  `docs/realtime_refactor_checklist.md` to make explicit that archived plans
  are historical references, not default required context for new milestone
  work; adds "consult archived plans only when checking prior decisions or
  historical scope" to all policy locations
- [x] 2026-04-15 updated M22–M25 submission prompts to replace explicit
  archive-path instruction in item 8 with "follow that directory's README for
  plan lifecycle rules", removing archive boilerplate from active agent context
- [x] 2026-04-15 deleted `move_artificat.md` from repo root after applying all
  its prescribed changes

### Milestone 20a — HPC Failure Recovery (in progress)

- [x] 2026-04-13 added `ResourceSpec.module_loads: tuple[str, ...]` field with
  an empty default so per-workflow or per-call Slurm module aliases can be
  frozen into a recipe without breaking existing artifacts; updated
  `_coerce_resource_spec()` and `_merge_resource_specs()` in `planning.py` to
  handle the new field with the same coercion pattern as `notes`
- [x] 2026-04-13 added `SlurmRunRecord.resource_overrides: ResourceSpec | None`
  field so each retry can record both the effective (merged) resource spec that
  was actually submitted and the caller-supplied override for audit purposes
- [x] 2026-04-13 added `DEFAULT_SLURM_MODULE_LOADS`, `_coerce_retry_resource_overrides()`,
  `_effective_resource_spec()`, and `_slurm_module_load_lines()` helpers to
  `spec_executor.py`; replaced hardcoded module-load lines in `render_slurm_script()`
  with `*_slurm_module_load_lines(resource_spec)` so custom loads render when
  present and the defaults apply when `module_loads` is empty
- [x] 2026-04-13 extended `_submit_saved_artifact()` to accept
  `resource_overrides` and compute `_effective_resource_spec()` before rendering
  the sbatch script; both the effective spec and the raw override are stored in
  the child `SlurmRunRecord`
- [x] 2026-04-13 replaced `retry()` in `SlurmWorkflowSpecExecutor` with a new
  version that accepts `resource_overrides`, validates keys against
  `_RETRY_RESOURCE_OVERRIDE_FIELDS` (unknown keys → `supported=False` before sbatch),
  and enables an escalation path for `resource_exhaustion` failures (OOM and TIMEOUT)
  that are not `DEADLINE`; `DEADLINE` is explicitly excluded and always requires a
  new `prepare_run_recipe` call
- [x] 2026-04-13 added `MAX_MONITOR_TAIL_LINES = 500`, `_read_text_tail()` with
  path-traversal guard (resolves and validates path is under `allowed_root`), and
  `ValueError` for negative `tail_lines`; updated `_monitor_slurm_job_impl()` to
  include `stdout_tail` / `stderr_tail` in the response for terminal states, null
  for non-terminal or absent files
- [x] 2026-04-13 updated `_retry_slurm_job_impl()` and `retry_slurm_job()` in
  `server.py` to accept and forward `resource_overrides`; updated `mcp_contract.py`
  with expanded tool description rules documenting valid override keys, DEADLINE
  exclusion, and `tail_lines` parameter
- [x] 2026-04-13 added 22 new tests across `test_spec_executor.ModuleLoadsAndResourceOverrideTests`,
  `test_server.ServerTests`, and `test_mcp_prompt_flows.SlurmMcpPromptFlowTests`;
  full test suite: 362 tests + 1 skipped (up from 340)
- [x] 2026-04-13 updated Phase 5 in `docs/mcp_showcase.md` to document escalation
  retry path, `resource_overrides` valid keys, DEADLINE exclusion, and `tail_lines`
  for `monitor_slurm_job`; added Scenario 6 to `docs/mcp_cluster_prompt_tests.md`;
  updated retry and HPC integration rows in `docs/capability_maturity.md`

### Milestone 20b — Storage-Native Durable Asset Return (2026-04-14)

- [x] 2026-04-14 added `DURABLE_ASSET_INDEX_SCHEMA_VERSION`, `DEFAULT_DURABLE_ASSET_INDEX_FILENAME`,
  and `DurableAssetRef` dataclass (frozen, slots, `SpecSerializable`) to
  `spec_artifacts.py`; fields: `schema_version`, `run_id`, `workflow_name`,
  `output_name`, `node_name`, `asset_path`, `manifest_path | None`,
  `created_at`, `run_record_path`
- [x] 2026-04-14 added `save_durable_asset_index(refs, run_dir)` and
  `load_durable_asset_index(run_dir)` helpers to `spec_artifacts.py`; the index
  is an atomic sidecar file `durable_asset_index.json` alongside
  `local_run_record.json`; loading an absent file returns `[]` for legacy
  compatibility; an unrecognised `schema_version` raises `ValueError`
- [x] 2026-04-14 moved `_json_ready()` and `_write_json_atomically()` from
  `spec_executor.py` to `spec_artifacts.py`; `spec_executor.py` now imports
  `_write_json_atomically` from `spec_artifacts`; removed the duplicate
  definitions and the now-unused `import os` from `spec_executor.py`
- [x] 2026-04-14 added `_durable_refs_from_record(record: LocalRunRecord) -> list[DurableAssetRef]`
  private helper to `spec_executor.py`; iterates `record.node_results`, emits
  one `DurableAssetRef` per `Path`-valued output; non-Path outputs are skipped;
  `manifest_path` is populated from `node_result.manifest_paths.get(output_name)`
- [x] 2026-04-14 updated `LocalWorkflowSpecExecutor.execute()` to call
  `save_durable_asset_index(refs, run_dir)` after `save_local_run_record()`
  when `refs` is non-empty; `LocalRunRecord` fields are unchanged
- [x] 2026-04-14 added `durable_index: Sequence[DurableAssetRef] = ()` parameter to
  `LocalManifestAssetResolver.resolve()`; all existing callers are unaffected;
  added `_durable_ref_for_missing_source()` helper to `resolver.py`; when a
  manifest source raises `FileNotFoundError` and a matching durable ref is found,
  an explicit limitation message citing `run_id` and `output_name` is added to
  `unresolved_requirements`; imported `DurableAssetRef` from `spec_artifacts`
  (no circular imports)
- [x] 2026-04-14 added 8 new tests: 3 in `test_spec_artifacts.DurableAssetIndexTests`
  (round-trip, missing-file, schema-version validation), 3 in
  `test_spec_executor.DurableAssetIndexIntegrationTests` (index written alongside
  record, fields match run record, legacy directory loads cleanly), 2 in
  `test_resolver.DurableIndexResolverTests` (missing path reports context,
  existing path succeeds); full test suite: 370 tests + 1 skipped

### MCP Doc Cross-linking

- [x] 2026-04-13 linked the `Validated Slurm Walkthrough` in
  `docs/mcp_showcase.md` to `docs/mcp_cluster_prompt_tests.md` so the general
  MCP guide points to the detailed live-cluster prompt test script instead of
  repeating the acceptance scenarios inline

### Slurm Test Coverage Follow-Up

- [x] 2026-04-13 fixed pre-existing timing flake in `test_loop_survives_reconcile_error`
  (`tests/test_slurm_async_monitor.py`) — replaced real thread dispatch with
  `patch.object(anyio.to_thread, "run_sync", new=fake_run_sync)` so the test
  only waits on `anyio.sleep` between cycles; widened the window from 0.5s to
  1.0s as a safety margin
- [x] 2026-04-13 added `test_monitor_slurm_job_reports_completed_terminal_state`,
  `_failed_`, and `_timeout_` — verify `final_scheduler_state` is non-null for
  each terminal state; the COMPLETED/FAILED path also checks `stdout_path` and
  `stderr_path` are present so clients know where to retrieve diagnostic output
- [x] 2026-04-13 added `test_monitor_slurm_job_uses_sacct_when_squeue_is_empty`
  — simulates empty squeue + sacct hit to prove the normal job-completion
  transition (job aged off squeue) is handled; asserts `source == "sacct"`
- [x] 2026-04-13 added `test_retry_slurm_job_declines_timeout_failure` and
  `_declines_cancelled_record` — verify both terminal states decline without
  calling sbatch; TIMEOUT requires new `prepare_run_recipe` with updated walltime
- [x] 2026-04-13 added `test_retry_slurm_job_child_record_links_to_parent`
  — after a successful NODE_FAIL retry, loads the child run record and asserts
  `retry_parent_run_record_path` points to the original record
- [x] 2026-04-13 added `cancel_slurm_job` idempotency and scancel-failure tests
  — `test_cancel_slurm_job_is_idempotent` verifies scancel is called exactly
  once across two cancel requests; `test_cancel_slurm_job_persists_cancellation_when_scancel_fails`
  verifies `cancellation_requested_at` is written to the run record even when
  scancel returns non-zero
- [x] 2026-04-13 updated `SlurmWorkflowSpecExecutor.cancel()` in
  `spec_executor.py` to support both behaviors: added early-return idempotency
  guard when `cancellation_requested_at` is already set; moved
  `save_slurm_run_record` before the `returncode != 0` check so the durable
  cancellation intent is always persisted regardless of scheduler response
- [x] 2026-04-13 added `test_cancel_then_monitor_shows_cancelled_state`
  — full cancel → CANCELLED monitor cycle; verifies `final_scheduler_state`
  is set after a reconcile that reports CANCELLED from the scheduler
- [x] 2026-04-13 added `test_run_slurm_recipe_saves_script_with_correct_directives`
  — reads the saved sbatch script and asserts `#SBATCH` directives match the
  frozen `resource_request` (`--cpus-per-task`, `--mem`, `--partition`,
  `--account`, `--time`)
- [x] 2026-04-13 added `test_run_slurm_recipe_script_path_points_to_existing_file`
  — verifies the `script_path` field in the durable run record points to a
  file that actually exists on disk after submission
- [x] 2026-04-13 added `slurm_resource_hints` to `_entry_payload()` in
  `server.py`; added `test_list_entries_exposes_slurm_resource_hints_for_slurm_capable_workflows`
  — verifies `cpu`, `memory`, and `walltime` are present and `queue`/`account`
  are absent for the BUSCO workflow entry
- [x] 2026-04-13 added `resume_from_local_record` parameter to
  `_run_slurm_recipe_impl()` in `server.py` and threaded it through to
  `.submit()`; added `test_run_slurm_recipe_carries_forward_local_resume_node_state`
  — builds a prior `LocalRunRecord`, submits with it, and asserts
  `local_resume_node_state` is populated in the `SlurmRunRecord`
- [x] 2026-04-13 added `test_monitor_slurm_job_rejects_unknown_schema_version`
  — overwrites a run record with an unrecognised `schema_version`, calls
  monitor, and asserts a human-readable schema/version message appears in
  `limitations` rather than a cryptic `KeyError`
- [x] 2026-04-13 added `test_run_slurm_recipe_twice_produces_independent_run_records`
  — submits the same artifact twice and asserts the two run records have
  different `run_id` values and different on-disk paths
- [x] 2026-04-13 full suite: 335 tests pass, 1 live-Slurm smoke skipped

### MCP Prompt-Level Integration Tests

- [x] 2026-04-13 created `tests/test_mcp_prompt_flows.py` — 5 multi-turn Slurm
  lifecycle flows exercised through the MCP tool surface (`create_mcp_server()`
  → `server.tools["tool_name"](keyword_args)`), mirroring the exact JSON-RPC
  call path a Claude client takes; Slurm subprocess layer replaced by
  in-process fakes so tests run offline without real cluster access
- [x] 2026-04-13 `test_mcp_prepare_submit_and_poll_until_completed` — full
  prepare → submit → monitor(RUNNING) → monitor(COMPLETED) flow; validates the
  `final_scheduler_state` polling gate: first call returns `None` (client must
  keep polling), second returns `"COMPLETED"` (client stops)
- [x] 2026-04-13 `test_mcp_failed_job_is_retried_to_completed` — prepare →
  submit → monitor(NODE_FAIL) → retry_slurm_job → monitor(COMPLETED) flow;
  verifies `retry_run_record_path` is a different path from the parent and
  the child lifecycle reaches COMPLETED independently
- [x] 2026-04-13 `test_mcp_duplicate_cancel_does_not_issue_second_scancel` —
  prepare → submit → cancel × 2; verifies second cancel returns `supported=True`
  without issuing a second `scancel` to the scheduler
- [x] 2026-04-13 `test_mcp_prepare_with_resource_request_dict_uses_slurm_profile`
  — verifies that passing `resource_request` as a dict with
  `execution_profile="slurm"` freezes the slurm profile into the recipe
  binding plan so `run_slurm_recipe` can proceed without re-planning
- [x] 2026-04-13 `test_mcp_list_slurm_run_history_returns_submitted_job` —
  verifies that after prepare + submit, the job appears in
  `list_slurm_run_history` with the correct `workflow_name` and `job_id`; this
  is the client path for resuming monitoring after a restart
- [x] 2026-04-13 full suite: 340 tests pass, 1 live-Slurm smoke skipped

### Registry Slurm Resource Hints

- [x] 2026-04-13 added `_WORKFLOW_SLURM_RESOURCE_HINTS` dict to
  `src/flytetest/registry.py` with advisory `cpu`, `memory`, and `walltime`
  starting-point values for all 16 Slurm-capable workflows; `queue` and
  `account` are deliberately absent — they are site-specific and must always
  come from the user
- [x] 2026-04-13 updated `_with_resource_defaults()` to attach hints under
  `execution_defaults["slurm_resource_hints"]` alongside the existing
  `execution_defaults["resources"]` (local) table; updated the function
  docstring to describe both tables and their precedence rules
- [x] 2026-04-13 added rule to `AGENTS.md` Section 7: when the user does not
  specify Slurm resources, read `slurm_resource_hints` from the target
  workflow's registry entry and surface them to the user before freezing;
  queue and account must always come from the user
- [x] 2026-04-13 updated `docs/capability_maturity.md` Resource-aware
  execution planning row to name both `execution_defaults["resources"]`
  (local cpu/memory/execution_class) and `execution_defaults["slurm_resource_hints"]`
  (Slurm cpu/memory/walltime) and their advisory role
- [x] 2026-04-13 updated `docs/mcp_showcase.md` `resource_request` description
  to direct clients toward `list_entries` →
  `compatibility.execution_defaults.slurm_resource_hints` as the starting-point
  source before freezing a recipe

### MCP Showcase Slurm Lifecycle Documentation

- [x] 2026-04-13 restructured "Validated Slurm Walkthrough" in
  `docs/mcp_showcase.md` into six named phases: Prepare, Submit, Monitor, On
  Completion, On Failure, Cancel; each phase is self-contained so users can
  navigate to the step they need
- [x] 2026-04-13 added scheduler state reference table covering `PENDING`,
  `RUNNING`, `COMPLETED`, `FAILED`, `TIMEOUT`, `OUT_OF_MEMORY`, `CANCELLED`
  with meaning and next-action guidance; `TIMEOUT` and `OUT_OF_MEMORY` are
  documented as terminal states that require a new `prepare_run_recipe` call
  with updated `resource_request` rather than `retry_slurm_job`
- [x] 2026-04-13 added "Slurm Prerequisites" section before the walkthrough
  explaining the 2FA constraint, authenticated HPC login session requirement,
  and required commands on `PATH`; cross-referenced from Common Failure Modes
  (moved from buried in failure modes to a dedicated callout)
- [x] 2026-04-13 added `resource_request` JSON schema example in the Recipe
  Flow section with all five fields (`cpu`, `memory`, `queue`, `account`,
  `walltime`); noted that these fields can also be embedded in the prompt text
  for MCP clients that drop optional tool arguments
- [x] 2026-04-13 added Phase 4 (On Completion) happy-path example showing a
  `COMPLETED` terminal state; `final_scheduler_state` being non-null is
  documented as the polling gate for MCP clients
- [x] 2026-04-13 added Phase 5 (On Failure) decision tree: `retry_slurm_job`
  for retryable failures (`NODE_FAIL`, transient errors) versus new
  `prepare_run_recipe` with updated `resource_request` for resource-exhaustion
  terminal states
- [x] 2026-04-13 added `.runtime/runs/<run_id>/` sbatch script callout in the
  `run_slurm_recipe` description so users know the script can be inspected
  before or after submission to verify directives
- [x] 2026-04-13 updated `retry_slurm_job` tools one-liner to state it
  resubmits the original frozen recipe unchanged; resource changes require a
  new `prepare_run_recipe` call
- [x] 2026-04-13 updated `AGENTS.md` Sections 3 and 7 to replace stale Flyte
  Slurm plugin language with the authenticated-session `sbatch` model; added
  explicit note that 2FA prevents SSH key pairing
- [x] 2026-04-13 updated `DESIGN.md` Section 4.5 to replace non-existent
  `SlurmExecutionProfile` / `sbatch_conf_for_recipe` API pseudo-code with the
  actual four-phase recipe workflow (`prepare_run_recipe` → `run_slurm_recipe`
  → `monitor_slurm_job` → `retry_slurm_job`)
- [x] 2026-04-13 added "## Slurm Execution" section to
  `docs/tutorial_context.md` covering the 2FA constraint, frozen resource
  settings, `TIMEOUT`/`OUT_OF_MEMORY` terminal classification, and BUSCO
  fixture as the canonical smoke-test reference

### Documentation Style Guide and Context Cleanup

- [x] 2026-04-13 rewrote `## Inline Comments` section of `.codex/comments.md`
  with four concrete code examples (annotation comment blocks, biological
  context, guard/constraint explanations); replaced abstract guidance with
  patterns that can be applied directly to source files
- [x] 2026-04-13 updated `.codex/comments.md` Function Docstrings section to
  name `slurm_poll_loop` in `src/flytetest/slurm_monitor.py` as the canonical
  depth standard for all project docstrings
- [x] 2026-04-13 updated `.codex/documentation.md` to add the `slurm_poll_loop`
  depth-target paragraph at the top of Code Documentation Expectations, and
  added a `named sub-sections` bullet (Error handling:, Output contract:,
  Retry logic:) to the Args/Returns guidance
- [x] 2026-04-13 added rule to both `.codex/comments.md` and
  `.codex/documentation.md`: Args and Returns explanations must go beyond the
  type hint to give the biological or engineering reason for each parameter,
  not just restate the type
- [x] 2026-04-13 created `.claudeignore` to exclude
  `Genomic Studies Platform Summary.md` from Claude Code context without
  removing it from the repository
- [x] 2026-04-13 archived 24 milestone submission prompt and plan files from
  `docs/realtime_refactor_plans/` into `docs/realtime_refactor_plans/archive/`;
  covered M12–M18 submission prompts, MCP spec cutover, recipe binding plans,
  and bulk milestone prompts; active M19 phase prompts remain in place
- [x] 2026-04-13 moved misplaced `src/flytetest/improve_dataclass_serializatoin.md`
  (typo in name, wrong directory) into a clean gated plan at
  `docs/realtime_refactor_plans/2026-04-13-dataclass-serialization-consolidation.md`;
  added matching checklist section to `docs/realtime_refactor_checklist.md`;
  gate: after M19 Phases C and D complete; key constraint: no `slots=True`
  (breaks Flyte's `dataclasses.asdict()`)

### Milestone 18 RCC Slurm Smoke

- [x] 2026-04-13 fixed M18 BUSCO image path freezing for cluster runs:
  `m18_prepare_slurm_recipe.py` now resolves a repo-relative `BUSCO_SIF` to an
  absolute path before saving the Slurm recipe, preventing Apptainer from
  resolving `data/images/...` relative to the BUSCO task scratch directory
- [x] 2026-04-13 validated the M18 RCC Slurm smoke from an authenticated
  cluster session: recipe submission, monitoring, synthetic retry-seed
  creation, retry-child submission, and retry-child monitoring all worked; the
  retry child is considered complete when its run record reconciles to
  `COMPLETED` with scheduler exit code `0:0` and `attempt_number` 2
- [x] 2026-04-13 updated `scripts/rcc/README.md` and `README.md` to document
  the M18 BUSCO image path behavior, retry-child success criteria, and current
  Slurm retry support status
- [x] 2026-04-13 added MCP recipe planning support for the M18 BUSCO eukaryota
  fixture: `prepare_run_recipe` can now freeze `busco_assess_proteins` as a
  registered-task Slurm recipe with the fixture FASTA, `auto-lineage`, genome
  mode, `busco_cpu`, and optional `busco_sif` runtime bindings; updated the
  MCP docs with a client prompt for Codex/OpenCode-style testing
- [x] 2026-04-13 extended `list_entries` / `flytetest://supported-targets`
  payloads with `supported_execution_profiles` and `default_execution_profile`
  so clients can ask which runnable targets are Slurm-capable before calling
  `prepare_run_recipe`

### Milestone 19 HPC Cluster Validation Helpers

- [x] 2026-04-13 threaded `resume_from_local_record` into compute-node Slurm
  execution: `_run_local_recipe_impl()` now accepts an optional prior local
  run-record path, and generated Slurm scripts call that helper with the
  frozen local-resume record when one was provided at submission time, so the
  local-to-Slurm resume path now affects actual job execution instead of only
  durable submission metadata
- [x] 2026-04-13 added RCC-first Milestone 19 cluster-validation helpers under
  `scripts/rcc/` for two scenarios: approval-gated composed recipe submission
  (`run_m19_approval_gate_smoke.sh`) and local-to-Slurm resume reuse
  (`run_m19_resume_slurm_smoke.sh`); added generic monitor/cancel Python
  helpers plus scenario-specific monitor/cancel wrappers and documented the new
  pointer files in `scripts/rcc/README.md`
- [x] 2026-04-13 kept the approval-gate smoke honest in the docs and helper
  output: it proves rejection before approval and accepted Slurm submission
  after approval, but does not claim end-to-end success for the current
  generated repeat-filter plus BUSCO workflow on the local handler surface
- [x] 2026-04-13 validated the Milestone 19 approval-gate smoke on RCC:
  unapproved composed-recipe submission was blocked with "No approval record
  found for this composed recipe.", the approved resubmission was accepted by
  Slurm, and downstream composed execution later reconciled to `FAILED` with
  exit code `1:0` as expected under the smoke's documented runtime
  limitations
- [x] 2026-04-13 validated the Milestone 19 local-to-Slurm resume smoke on
  RCC: the resume helper submitted a BUSCO recipe with a matching prior local
  run record, and the monitored Slurm run reconciled to `COMPLETED` with
  scheduler exit code `0:0`, confirming that compute-node execution honored
  `resume_from_local_record` instead of only persisting the resume metadata in
  the durable submission record
- [x] 2026-04-13 validated the first real workflow Milestone 19 Slurm probe on
  RCC with the protein-evidence lifecycle wrappers: the submit helper froze a
  durable recipe artifact and Slurm run record, and the monitor helper later
  reconciled the job to `COMPLETED` with scheduler exit code `0:0`, closing
  the RCC-side real-workflow validation gate for Milestone 19
- [x] 2026-04-13 added passive RCC poll-loop watcher helpers
  `watch_slurm_run_record.py` and `watch_slurm_run_record.sh`; they reload the
  durable JSON record directly at a fixed interval and print only the
  background-reconciliation evidence fields, so RCC sessions can prove that
  the MCP server's `slurm_poll_loop()` updated the record without using
  `monitor_slurm_job`
- [x] 2026-04-13 moved the generic latest-run pointer behavior into the shared
  `run_slurm_recipe` server path: every successful Slurm submission now
  refreshes `.runtime/runs/latest_slurm_run_record.txt` and
  `.runtime/runs/latest_slurm_artifact.txt`, so back-to-back direct MCP
  submissions no longer depend on workflow-specific RCC wrapper pointers

### MCP Slurm Run History

- [x] 2026-04-13 added `list_slurm_run_history` to the MCP surface; it reads
  durable `.runtime/runs/` records only, returns recent accepted Slurm
  submissions newest first, includes the generic latest pointer targets, and
  does not require live scheduler access
- [x] 2026-04-13 added focused server tests for the new history tool: one
  covers recent-run ordering plus latest-pointer reporting, and one covers the
  empty-run-root case
- [x] 2026-04-13 extended `list_slurm_run_history` with exact
  `workflow_name`, `active_only`, and `terminal_only` filters plus
  `matched_count` reporting; conflicting active-versus-terminal requests now
  fail fast with an explicit limitation message

### Documentation Sweep Planning

- [x] 2026-04-12 moved the documentation sweep notes into
  `docs/realtime_refactor_plans/2026-04-12-documentation-sweep-plan.md`;
  renamed the misspelled scratch file into a durable plan and split the sweep
  into review-sized batches with per-batch validation rules
- [x] 2026-04-13 refreshed Batch 0 inventory in the documentation sweep plan:
  re-ran the helper-boilerplate searches, rechecked `spec_executor.py` for
  LocalNodeExecutionRequest-style copy-paste docstrings, verified no remaining
  module-docstring indentation issues in `src/` or `tests/`, and kept the pass
  documentation-only
- [x] 2026-04-13 completed documentation sweep Batches 1 and 2 in
  `src/flytetest/spec_executor.py`: replaced the copied
  LocalNodeExecutionRequest-style class/dataclass docstrings, removed generic
  helper Args/Returns boilerplate, and validated with `python3 -m compileall`,
  `.venv/bin/python -m pytest tests/test_spec_executor.py`, targeted `rg`
  checks, and `git diff --check -- src/flytetest/spec_executor.py`; the bare
  `python` command is not available in this shell
- [x] 2026-04-13 completed documentation sweep Batch 3 across shared
  infrastructure modules: cleaned planner, manifest, MCP contract, config,
  GFF3, asset, spec, artifact, and server helper docstrings without changing
  production behavior; worker validations covered `python3 -m compileall`,
  targeted `tests/test_specs.py`, `tests/test_planning.py`,
  `tests/test_server.py`, small manifest/config/GFF3/server test selections,
  targeted boilerplate `rg` checks, and path-scoped `git diff --check`
- [x] 2026-04-13 completed documentation sweep Batches 4, 5, and 6 across the
  biological task/workflow families: PASA, consensus, repeat filtering,
  protein evidence, transcript evidence, TransDecoder, AGAT, EggNOG,
  annotation, functional annotation, and RNA-seq QC/quant docstrings now
  describe the existing stage boundaries instead of helper boilerplate; worker
  validations passed per-family `python3 -m compileall`, targeted PASA,
  consensus/filtering, protein-evidence, transcript/TransDecoder, and
  downstream annotation tests, targeted `rg` checks, and path-scoped
  `git diff --check`
- [x] 2026-04-13 completed documentation sweep Batch 7 test cleanup: removed
  boilerplate test helper docstrings and trimmed nested test-double docstrings
  across server, spec executor, biological stage, planning/spec, and Flyte stub
  tests while leaving assertions and fixture behavior unchanged; worker
  validations passed compileall, the touched test-file pytest targets,
  targeted `rg` checks, and path-scoped `git diff --check`
- [x] 2026-04-13 completed documentation sweep Batch 8 shell comment audit in
  `scripts/rcc/`: added missing file-level purpose comments to RCC smoke,
  fixture, image, Slurm, and wrapper scripts without changing commands, flags,
  variables, or control flow; validation passed `bash -n` for changed shell
  entrypoints, `git diff --check -- scripts/rcc`, and a comment-only diff
  inspection
- [x] 2026-04-13 completed documentation sweep Batch 9 final validation:
  repo-wide boilerplate `rg` checks are clean, `spec_executor.py` has only the
  allowed `LocalNodeExecutionRequest` occurrence of the copied phrase, the
  module-docstring indentation scan found no first-docstring indentation
  issues, `python3 -m compileall src tests` passed, `git diff --check` passed,
  and the consolidated touched-file pytest target passed with 179 tests; the
  full suite still has one persistent failure in untouched
  `tests/test_slurm_async_monitor.py::TestSlurmPollLoop::test_loop_survives_reconcile_error`
  where the async retry loop only records one call inside the test timeout

### Milestone 19 Phase D: Deterministic Cache-Key Normalization

- [x] 2026-04-12 added `HANDLER_SCHEMA_VERSION = "1"` constant in
  `spec_executor.py`; included in every cache key so bumping the version
  invalidates all prior records when handler output shapes change
- [x] 2026-04-12 added `cache_identity_key()` pure function that computes a
  stable SHA-256 hex digest (16-char prefix) from frozen `WorkflowSpec`,
  `BindingPlan`, resolved planner inputs, and handler schema version; path
  normalization strips repo-root prefix and converts to POSIX separators
- [x] 2026-04-12 added `cache_identity_key: str | None` optional field to
  both `LocalRunRecord` and `SlurmRunRecord`; persisted in the durable JSON
  record and survives save/load round-trips
- [x] 2026-04-12 extended `_validate_resume_identity()` with an optional
  `current_cache_key` parameter; the cache key comparison is the authoritative
  content-level gate for resume acceptance (workflow name and artifact path
  remain as fast pre-filters)
- [x] 2026-04-12 wired `cache_identity_key` computation into
  `LocalWorkflowSpecExecutor.execute()` and
  `SlurmWorkflowSpecExecutor._submit_saved_artifact()`; the key is computed
  from frozen dicts and persisted in every new run record
- [x] 2026-04-12 added 12 Phase D tests in `CacheIdentityKeyTests`:
  determinism, node change, runtime binding change, resource spec change,
  runtime image change, repo-root normalization, handler version invalidation,
  cache key match/mismatch resume, LocalRunRecord/SlurmRunRecord round-trip,
  and executor integration
- [x] 2026-04-12 marked the Phase A cache-key checklist item as complete;
  resolved the cache-key normalization and cache invalidation open blockers

### Milestone 19 Core Phase B: Local Resume Semantics

- [x] 2026-04-12 added `resume_from: Path | None` parameter to
  `LocalWorkflowSpecExecutor.execute()`; when provided, the prior
  `LocalRunRecord` is loaded, identity-validated (workflow name + artifact
  path), and used to skip nodes whose `node_completion_state` entry is `True`
- [x] 2026-04-12 added `node_skip_reasons: dict[str, str]` field to
  `LocalRunRecord`; each skipped node gets a human-readable reason referencing
  the prior run ID and completion status
- [x] 2026-04-12 added `_validate_resume_identity()` helper that rejects
  resume when workflow name or artifact path differs between prior record and
  current artifact; returns a structured mismatch description
- [x] 2026-04-12 added 6 Phase B tests to `LocalResumeTests` in
  `tests/test_spec_executor.py`: full-skip resume, skip-reason recording,
  workflow-name mismatch rejection, artifact-path mismatch rejection,
  partial-completion re-execution, and `node_skip_reasons` round-trip

### Milestone 19 Core Phase C: Slurm Parity And Safe Composed Execution

Design decision — resume alignment between `LocalRunRecord` and `SlurmRunRecord`:

The two record types remain separate dataclasses.  Alignment is achieved by:
(a) `SlurmWorkflowSpecExecutor.submit()` accepts an optional
`resume_from_local_record: Path | None`; when provided and identity-matched,
completed nodes from the local record are recorded as pre-done in the new
`SlurmRunRecord` via a `local_resume_node_state` dict.
(b) The Slurm submission script can use the pre-done node list to skip
already-completed stages.
(c) Both paths use the same `_validate_resume_identity()` helper for identity
checking.
(d) Approval state lives in a companion `RecipeApprovalRecord(SpecSerializable)`
alongside the saved artifact, not inside the artifact itself, so approval is
explicit, durable, and independently inspectable.

- [x] 2026-04-12 added `local_resume_node_state: dict[str, bool]` and
  `local_resume_run_id: str | None` fields to `SlurmRunRecord`; these carry
  forward completed node state from a prior local run without merging the two
  record types
- [x] 2026-04-12 added `resume_from_local_record: Path | None` parameter to
  `SlurmWorkflowSpecExecutor.submit()` and `_submit_saved_artifact()`; when
  identity-matched, prior local completion state is recorded in the new
  `SlurmRunRecord` and noted in assumptions
- [x] 2026-04-12 introduced `RecipeApprovalRecord(SpecSerializable)` in
  `spec_artifacts.py` with `RECIPE_APPROVAL_SCHEMA_VERSION = "recipe-approval-v1"`;
  includes `save_recipe_approval()`, `load_recipe_approval()`, and
  `check_recipe_approval()` helpers using atomic temp-file writes
- [x] 2026-04-12 added `approve_composed_recipe` MCP tool in `server.py` that
  writes a durable approval record alongside the artifact; added
  `APPROVE_COMPOSED_RECIPE_TOOL_NAME` to `MCP_TOOL_NAMES` in `mcp_contract.py`
- [x] 2026-04-12 `run_local_recipe` and `run_slurm_recipe` now check
  `check_recipe_approval()` before executing `generated_workflow` artifacts;
  unapproved composed recipes are blocked with a clear limitation message
- [x] 2026-04-12 added 3 Slurm resume tests in `SlurmResumeFromLocalRecordTests`
  (pre-completed state, identity mismatch rejection, round-trip) and 10
  approval tests in `tests/test_recipe_approval.py` (record round-trip, schema
  validation, missing/approved/rejected/expired checks, MCP tool, run_local gate)
- [x] 2026-04-12 full suite: 297 tests pass (284 pre-Phase C + 13 new), 1
  live-Slurm smoke skipped

### Milestone 19 Part B: Async Slurm Monitoring

- [x] 2026-04-12 created `src/flytetest/slurm_monitor.py` as the standalone
  async monitoring module — contains `SlurmPollingConfig`, batched Slurm
  parsing helpers, file-locking helpers, `reconcile_active_slurm_jobs()`, and
  the `slurm_poll_loop()` async entry point
- [x] 2026-04-12 implemented `batch_query_slurm_job_states()` that issues a
  single `squeue --format="%i %T"` call and a single `sacct
  --format=JobID,State,ExitCode` call per poll cycle for all active job IDs,
  replacing the per-job query loop that M16 relied on
- [x] 2026-04-12 added `_parse_batch_squeue_output()` and
  `_parse_batch_sacct_output()` to handle multi-job scheduler output; sacct
  parser prefers bare-JobID rows over step rows (e.g. `123.batch`)
- [x] 2026-04-12 introduced `fcntl.flock`-based exclusive locks on a companion
  `.lock` file alongside each `slurm_run_record.json`; both the async updater
  and synchronous MCP handlers can coexist safely via `save_slurm_run_record_locked()`
  and `load_slurm_run_record_locked()`
- [x] 2026-04-12 implemented `discover_active_slurm_run_dirs()` to scan
  `.runtime/runs/` for non-terminal, non-cancelled Slurm run records before
  each poll cycle, avoiding unnecessary scheduler queries for completed jobs
- [x] 2026-04-12 attached `slurm_poll_loop` to the MCP server event loop in
  `_run_stdio_server_async()` via `anyio.create_task_group()`; the poll task
  is cancelled cleanly when the server's stdio transport closes
- [x] 2026-04-12 configured `SlurmPollingConfig` with defaults: 30-second
  poll interval, 300-second backoff cap, factor-of-2 exponential backoff,
  30-second per-command timeout; a single `sacct` timeout causes backoff only,
  not a server crash
- [x] 2026-04-12 added `tests/test_slurm_async_monitor.py` covering batch
  squeue/sacct parsing, mocked batch queries (including squeue timeout and
  failure), run-directory discovery across mixed states, full reconcile
  end-to-end, locked round-trips, lock-file creation, and async loop lifecycle
- [x] 2026-04-12 updated `docs/capability_maturity.md` to mark async Slurm
  monitoring as `Current`; module is observational only — does not alter
  submission, retry, or cancellation semantics
- [x] 2026-04-12 marked all Milestone 19 Part B checklist items complete in
  `docs/realtime_refactor_checklist.md`

### Planning assessment refresh

- [x] 2026-04-13 added `synchronous-twirling-panda-assessment.md` with a
  current-state agree / disagree critique of `synchronous-twirling-panda.md`,
  reflecting that the Slurm design update is complete and Milestone 19 Phase A
  has landed while Phase B/C resume and cache-key work remain open

### Milestone 19 Core Phase A: Durable Local Run Records

- [x] 2026-04-12 introduced `LocalRunRecord(SpecSerializable)` in
  `src/flytetest/spec_executor.py` — the first durable local run-record shape
  for saved-spec execution; stage completion state is no longer in-memory only
- [x] 2026-04-12 added schema version constant `LOCAL_RUN_RECORD_SCHEMA_VERSION
  = "local-run-record-v1"` and `DEFAULT_LOCAL_RUN_RECORD_FILENAME =
  "local_run_record.json"`; schema version is validated on deserialize and
  rejected when mismatched so stale records cannot silently produce wrong data
- [x] 2026-04-12 persists per-node completion state (`node_completion_state`
  dict keyed by node name), output references (`node_results`, `final_outputs`),
  timestamps (`created_at`, `completed_at`), resolved planner inputs, and
  assumptions; all fields round-trip exactly via `SpecSerializable`
- [x] 2026-04-12 added `save_local_run_record()` + `load_local_run_record()`
  helpers in `spec_executor.py`, following the same atomic temp-file pattern
  as the Slurm helpers from M16/18
- [x] 2026-04-12 extended `LocalWorkflowSpecExecutor.__init__` with optional
  `run_root: Path | None = None`; writes a durable record after every
  successful run when set; no record written when `None` (backward compat)
- [x] 2026-04-12 made `LocalNodeExecutionResult` extend `SpecSerializable`
  (changed `manifest_paths` annotation to `dict[str, Path]` for full round-trip
  fidelity); no behavioral change to existing callers
- [x] 2026-04-12 added 4 Phase A tests to `tests/test_spec_executor.py`:
  round-trip, schema-version validation, executor-persistence integration, and
  backward-compat with no `run_root`
- [x] 2026-04-12 full suite: 241 tests pass (237 pre-existing + 4 new), 0
  failures, 1 live-Slurm smoke skipped
- [ ] Phase B (resume semantics) — completed under Phase C session
- [ ] Phase C (cache keys + Slurm parity) — completed: Slurm resume alignment,
  approval gate, and composed-recipe execution gating landed

### Design alignment for scheduler-backed execution

- [x] 2026-04-12 updated `DESIGN.md` to replace the Flyte Slurm plugin model
  with the supported authenticated-session `sbatch` topology
- [x] 2026-04-12 aligned the Slurm execution, MCP tool, and test guidance in
  `DESIGN.md` with the already-implemented scheduler-bound execution path
- [x] 2026-04-12 normalized the Milestone 16 authenticated-Slurm handoff note
  so older Flyte Slurm plugin language is clearly historical

### Validation sweep after Milestone 15 review

- [x] 2026-04-11 fixed the `prepare_evm_transcript_inputs` signature typo so
  the pre-EVM consensus workflow and tests consistently use `pasa_results`
- [x] 2026-04-11 verified full local unittest discovery after the Milestone 15
  review fixes: 237 tests passing, 1 live Slurm smoke skipped because `sbatch`
  is required

### Milestone 15 Phase 2: Planning Integration & Approval Gating

- [x] 2026-04-11 extended `_planning_goal_for_typed_request()` to try
  registry-constrained composition fallback when hardcoded patterns don't match
- [x] 2026-04-11 integrated composition algorithm into planning layer via
  `_try_composition_fallback()` function that queries synthesis-eligible stages
  and attempts path discovery for common output types
- [x] 2026-04-11 added `requires_user_approval` flag to `plan_typed_request()`
  response so composed workflows are explicitly marked as needing approval
- [x] 2026-04-11 implemented approval gating in `_prepare_run_recipe_impl()`
  to prevent artifact save when composition requires approval
- [x] 2026-04-11 fixed `_workflow_spec_for_typed_goal()` to support
  arbitrary multi-stage workflow specs (not just hardcoded 2-entry repeat+BUSCO)
- [x] 2026-04-11 created `tests/test_planning_composition.py` with focused
  integration tests for composition fallback and approval gating
- [x] 2026-04-11 updated README.md with Workflow Composition section
  explaining discovery, approval requirements, and bounding parameters
- [x] 2026-04-11 updated docs/capability_maturity.md marking Registry-driven
  composition as "Current" instead of "Close", added M15 Phase 2 to Near-Term
  Priorities
- [x] 2026-04-11 fixed a regression where unrelated prompts and known day-one
  missing-input declines could fall through to registry-composition candidates
- [x] 2026-04-11 verified the focused composition/planning coverage after adding
  regression tests for fallback intent gating
- [x] 2026-04-11 backward compatible: hardcoded patterns checked before
  composition fallback, existing requests behave identically

### Milestone 16 Slurm lifecycle observability

- [x] 2026-04-11 added durable Slurm run-record loading and reconciliation
  through `squeue`, `scontrol show job`, and `sacct`
- [x] 2026-04-11 added explicit `monitor_slurm_job` and `cancel_slurm_job`
  MCP operations for submitted jobs
- [x] 2026-04-11 added terminal-state recording for stdout, stderr, exit code,
  and cancellation details in the durable run record
- [x] 2026-04-11 added focused tests for reconciliation, cancellation, and
  stale-record handling
- [x] 2026-04-11 changed the Slurm execution boundary so it now tracks job
  lifecycle state explicitly instead of treating submission as the end of the
  scheduler contract

### Protein-evidence Slurm smoke

- [x] 2026-04-11 added RCC wrapper scripts for submitting, monitoring, and
  cancelling the protein-evidence Slurm recipe from frozen run records
- [x] 2026-04-11 added a validated protein-evidence Slurm path that freezes
  the recipe, submits it, and persists the latest run-record and artifact
  pointers under `.runtime/runs/`
- [x] 2026-04-11 added supporting smoke and debug helpers for the
  protein-evidence HPC workflow
- [x] 2026-04-11 changed the protein-evidence stage so it now has an explicit
  HPC validation path in addition to the local fixture and workflow tests

### Tool reference normalization

- [x] 2026-04-11 normalized `docs/tool_refs/` so every tool reference now
  includes `Input Data`, `Output Data`, and `Code Reference` sections
- [x] 2026-04-11 added code back-links from the tool refs to the relevant task
  and workflow modules, including the deferred `table2asn` boundary
- [x] 2026-04-11 updated `docs/tool_refs/README.md` and
  `docs/tool_refs/stage_index.md` so the stage index and tool-reference
  guidance reflect the implemented workflow surface more honestly
- [x] 2026-04-11 refreshed stale stage notes in the BRaker3, PASA, EVM,
  TransDecoder, Trinity, BUSCO, EggNOG, AGAT, Exonerate, Salmon, FastQC, and
  repeat-filtering references to match the current code paths

### Authenticated Slurm access boundary

- [x] 2026-04-11 changed `run_slurm_recipe`, `monitor_slurm_job`, and
  `cancel_slurm_job` so they now report explicit unsupported-environment
  limitations when FLyteTest is running outside an already-authenticated
  scheduler-capable environment
- [x] 2026-04-11 changed Slurm lifecycle diagnostics so they distinguish
  missing CLI commands and scheduler reachability issues from ordinary
  lifecycle state
- [x] 2026-04-11 updated README, MCP showcase docs, capability notes, and the
  Milestone 16 Part 2 handoff docs so they describe the supported Slurm
  topology as a local MCP/server process running inside an authenticated HPC
  session
- [x] 2026-04-11 updated README and MCP showcase docs with Codex CLI and
  OpenCode client setup examples plus the validated prompt sequence for
  prepare, submit, monitor, and cancel on the protein-evidence Slurm path

### TaskEnvironment catalog refactor

- [x] 2026-04-11 centralized shared Flyte `TaskEnvironment` defaults in
  `src/flytetest/config.py`
- [x] 2026-04-11 introduced a declarative task-environment catalog plus
  compatibility aliases for current task families
- [x] 2026-04-11 added explicit per-family runtime overrides for BRAKER3
  annotation and BUSCO QC so the catalog reflects real workload differences
- [x] 2026-04-11 added focused tests for the shared defaults and alias
  stability
- [x] 2026-04-11 reduced repetition in the task-environment setup so future
  task families can inherit shared runtime policy from one place

### Local recipe execution robustness

- [x] 2026-04-11 changed collection-shaped workflow inputs such as
  `protein_fastas: list[File]` so they now bypass the local `flyte run
  --local` wrapper in MCP/server execution and use direct Python workflow
  invocation instead
- [x] 2026-04-11 avoided the current Flyte 2.1.2 CLI serialization gap where
  collection inputs are parsed as JSON but nested `File` / `Dir` values are
  not rehydrated for workflow execution

### AGAT post-processing milestone

- [x] 2026-04-11 implemented the AGAT statistics slice as `agat_statistics`
  plus the `annotation_postprocess_agat` workflow wrapper
- [x] 2026-04-11 implemented the AGAT conversion slice as
  `agat_convert_sp_gxf2gxf` plus the `annotation_postprocess_agat_conversion`
  workflow wrapper
- [x] 2026-04-11 implemented the AGAT cleanup slice as `agat_cleanup_gff3`
  plus the `annotation_postprocess_agat_cleanup` workflow wrapper
- [x] 2026-04-11 added synthetic AGAT coverage in `tests/test_agat.py`
- [x] 2026-04-11 updated the AGAT tool reference, stage index, capability
  snapshot, registry, compatibility exports, and prompt handoff docs to
  reflect the new post-EggNOG boundary
- [x] 2026-04-11 advanced the implemented biological scope from EggNOG
  functional annotation into the AGAT post-processing slices on the
  EggNOG-annotated and AGAT-converted GFF3 bundles
- [x] completed in M21c: `table2asn` NCBI submission (`annotation_postprocess_table2asn`)

### EggNOG functional annotation milestone

- [x] 2026-04-11 implemented the `annotation_functional_eggnog` workflow for
  the post-BUSCO functional-annotation milestone
- [x] 2026-04-11 added the EggNOG task family: `eggnog_map` and
  `collect_eggnog_results`
- [x] 2026-04-11 added synthetic EggNOG coverage in `tests/test_eggnog.py`
- [x] 2026-04-11 updated the EggNOG tool reference, stage index, capability
  matrix, tutorial context, and milestone checklist to track the new boundary
- [x] 2026-04-11 advanced the implemented biological scope from BUSCO-based
  annotation QC into EggNOG functional annotation while keeping AGAT and
  `table2asn` deferred
- [x] 2026-04-11 updated the registry, compatibility exports, README
  milestone tables, planning adapters, and prompt handoff docs to expose the
  new boundary explicitly
- [x] completed in M21c: `table2asn` NCBI submission; AGAT completed earlier
  milestone

### BUSCO annotation QC milestone

- [x] 2026-04-11 implemented the `annotation_qc_busco` workflow for post-
  repeat-filtering annotation QC
- [x] 2026-04-11 added the BUSCO task family: `busco_assess_proteins` and
  `collect_busco_results`
- [x] 2026-04-11 added synthetic BUSCO coverage in `tests/test_functional.py`
- [x] 2026-04-11 added a BUSCO milestone handoff prompt in
  `docs/busco_submission_prompt.md`
- [x] 2026-04-11 advanced the implemented biological scope from repeat-
  filtered GFF3/protein collection through BUSCO-based annotation QC while
  keeping EggNOG, AGAT, and submission-prep deferred
- [x] 2026-04-11 updated the registry, compatibility exports, README
  milestone tables, stage index, and BUSCO tool reference to expose the new
  QC boundary explicitly
- [x] 2026-04-11 validated the BUSCO workflow with a real repo-local Apptainer
  runtime and explicit `_odb12` lineage datasets, and updated BUSCO docs to
  reflect the tested `flyte run` CLI surface and runtime paths
- [x] completed in subsequent milestones: EggNOG (M21), AGAT (M21), `table2asn` (M21c)
  this milestone

### Repeat filtering and cleanup milestone

- [x] 2026-04-11 implemented the post-PASA `annotation_repeat_filtering`
  workflow for RepeatMasker conversion, gffread protein extraction,
  funannotate overlap filtering, repeat blasting, deterministic removal
  transforms, and final repeat-free GFF3/protein FASTA collection
- [x] 2026-04-11 added the repeat-filtering task family:
  `repeatmasker_out_to_bed`, `gffread_proteins`, `funannotate_remove_bad_models`,
  `remove_overlap_repeat_models`, `funannotate_repeat_blast`,
  `remove_repeat_blast_hits`, and `collect_repeat_filter_results`
- [x] 2026-04-11 added synthetic repeat-filtering tests plus local
  RepeatMasker fixture-path coverage in `tests/test_repeat_filtering.py`
- [x] 2026-04-11 advanced the implemented biological scope from PASA post-EVM
  refinement through repeat filtering and cleanup while keeping the later
  functional and submission stages deferred
- [x] 2026-04-11 updated the registry, compatibility exports, README milestone
  tables, tutorial context, and tool references to expose the repeat-
  filtering boundary explicitly
- [x] 2026-04-11 implemented `trinity_denovo_assemble`, updated
  `transcript_evidence_generation` to collect both Trinity branches, and
  removed PASA's external de novo Trinity FASTA requirement in favor of the
  transcript-evidence bundle
- [x] completed in subsequent milestones: BUSCO (M21), EggNOG (M21), AGAT (M21), `table2asn` (M21c)
  outside this milestone

### Documentation and planning

- [x] 2026-04-11 clarified the active milestone, stop rule, and stage-by-stage
  notes alignment in `README.md`
- [x] 2026-04-11 added tutorial-backed prompt-planning context in
  `docs/tutorial_context.md`
- [x] 2026-04-11 added stage-oriented tool-reference landing pages and prompt
  starters under `docs/tool_refs/`
- [x] 2026-04-11 added refactor milestone tracking and handoff materials in
  `docs/refactor_completion_checklist.md` and
  `docs/refactor_submission_prompt.md`

### Codebase structure and workflow coverage

- [x] 2026-04-11 split the repo into a package layout under `src/flytetest/`
  with separate task, workflow, type, registry, planning, and server modules
- [x] 2026-04-11 implemented deterministic workflow coverage through PASA
  post-EVM refinement while keeping repeat filtering, BUSCO, EggNOG, AGAT,
  and `table2asn` deferred
- [x] 2026-04-11 preserved the notes-faithful pre-EVM filename contract for
  `transcripts.gff3`, `predictions.gff3`, and `proteins.gff3`

### MCP showcase

- [x] 2026-04-11 added a narrow FastMCP stdio server in
  `src/flytetest/server.py`
- [x] 2026-04-11 limited the runnable MCP showcase to workflow
  `ab_initio_annotation_braker3` and task `exonerate_align_chunk`
- [x] 2026-04-11 added prompt planning in `src/flytetest/planning.py` for
  explicit local-path extraction and hard downstream-stage declines
- [x] 2026-04-11 added small read-only MCP resources for scope discovery:
  `flytetest://scope`, `flytetest://supported-targets`, and
  `flytetest://example-prompts`
- [x] 2026-04-11 added a compact additive `result_summary` block to
  `prompt_and_run` responses for success, decline, and failure cases

### Validation and fixtures

- [x] 2026-04-11 added synthetic MCP server coverage in `tests/test_server.py`
- [x] 2026-04-11 staged lightweight tutorial-derived local fixture files under
  `data/` for bounded smoke testing

## Prompt Tracking

Current prompt/handoff docs already in the repo:

- `docs/refactor_submission_prompt.md`
- `docs/tutorial_context.md`
- `docs/tool_refs/stage_index.md`

Future improvement idea:

- [ ] add a small prompt archive directory for accepted milestone prompts
  once the current MCP contract stabilizes
- [ ] add an environment preflight layer that checks for the active
  interpreter, `mcp`, `flyte`, and other required tools instead of assuming
  they are already available
