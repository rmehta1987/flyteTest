# Scientist-Centered MCP: Less Heuristic, More Natural, Family-Extensible

## Context

### Why this change is happening

Consider a working biologist who has just sequenced a new non-model eukaryote and wants to annotate its genome: protein-coding gene prediction with BRAKER3 using RNA-seq and a curated protein evidence set, followed by completeness assessment with BUSCO. From the scientist's seat, the ideal experience is something like *"here is my genome FASTA, here are my reads, here is my protein set — predict genes and give me a reproducible artifact I can hand to my collaborator."* The scientist should not have to memorize tool orchestration vocabulary, remember that BRAKER3 wants a BAM rather than FASTQs for RNA-seq evidence, or hand-craft SLURM directives for a campus cluster.

FlyteTest's founding purpose — quoted verbatim from `DESIGN.md`'s opening — is to *"minimize the computational and engineering burden on scientists by enabling dynamic composition of bioinformatics pipelines from natural-language requests."* Today's MCP surface, while functionally complete, falls short of that purpose in two specific ways:

1. **It feels like a CLI, not a conversation.** Running a workflow currently requires orchestrating four MCP calls in order: `prepare_run_recipe` freezes a plan into an on-disk `WorkflowSpec`, `approve_composed_recipe` releases the approval gate, `run_local_recipe` or `run_slurm_recipe` executes by `artifact_path`, and lifecycle tools (`monitor_slurm_job`, `inspect_run_result`) read the result. The scientist is effectively juggling artifact paths and approval state — the mental overhead belongs to a build engineer, not a geneticist.

2. **Server-side prose heuristics are brittle.** `src/flytetest/planning.py` currently contains six keyword/regex helpers (`_extract_prompt_paths`, `_extract_braker_workflow_inputs`, `_extract_protein_workflow_inputs`, `_classify_target`, `_extract_execution_profile`, `_extract_runtime_images`) and a BUSCO keyword branch in the biological-goal derivation path. These helpers try to pull file paths, evidence kinds, resource requests, and container image hints out of free-text scientist prompts. They break on valid synonyms ("assembly" vs. "genome FASTA"), miscategorize edge cases (BUSCO on proteins vs. genome vs. transcripts), and duplicate work the client-side LLM already performs more reliably. Previous milestones have gated a growing list of tasks/workflows behind this fragile parsing layer.

### The four pillars this plan preserves

`DESIGN.md` establishes four pillars that distinguish flyteTest from generic workflow platforms. Every change in this plan is judged against whether it reinforces or erodes them:

1. **Typed biological contracts.** Scientists and the planner speak in domain types — `ReferenceGenome`, `ReadSet`, `ProteinEvidenceSet`, `AnnotationEvidenceSet`, and the M23–M26 generic result bundles (`CodingPredictionResult`, `ProteinAlignmentChunkResult`, `AnnotationRefinementResultBundle`, `ConsensusAnnotationResultBundle`) — not loose dictionaries of paths. The types carry semantics: a `ReadSet` knows whether it is paired-end, what sample it belongs to, and (optionally) which prior run produced it.

2. **Frozen run recipes (`WorkflowSpec`) with `source_prompt` captured.** Every execution — local or Slurm — first materializes a `WorkflowSpec` artifact on disk (`.runtime/specs/<recipe_id>.json`), with the originating scientist prompt recorded verbatim for audit. This is the reproducibility gate: a collaborator receiving the `recipe_id` can replay the exact same run weeks later. Nothing executes without first freezing.

3. **Pipeline families with stage order.** `RegistryCompatibilityMetadata` carries `pipeline_family` (e.g. `"annotation"`, `"variant_calling"`, `"postprocessing"`) and `pipeline_stage_order` (1, 2, 3...), giving the scientist a map: *"I am at stage 2 of the annotation family; stage 3 is consensus merging; stage 4 is QC."* The planner uses these fields to suggest what runs next, the MCP surface uses them for browsing, and `.codex/registry.md` uses them to guide contributors.

4. **Offline-compute HPC reality.** FlyteTest's primary deployment target is HPC clusters where compute nodes cannot reach the internet (DESIGN §7.5). Apptainer/Singularity container images, tool databases (BUSCO lineage directories, EVM weight tables, dbSNP VCFs for GATK, etc.), and resolved input files must all live on a compute-visible shared filesystem *before* `sbatch` is called. The scheduler will happily submit a job referencing an unreachable `.sif` path; the job will then fail on the node with a cryptic runtime error. Catching this at submit time is not a nice-to-have — it is the difference between a 30-second error and a 2-hour wasted queue slot.

### Two ideas borrowed from `../stargazer/`

FlyteTest's sibling project `stargazer` has two UX patterns worth translating without copying wholesale:

- **Task-vs-workflow split at the MCP surface.** `run_task` exposes a single registered Flyte task (e.g. one Exonerate chunk alignment) for stage-scoped experimentation; `run_workflow` exposes a registered multi-task entrypoint (e.g. `braker3_annotation_workflow`) for production runs. Scientists browsing tasks vs. workflows immediately see the granularity distinction, which matters when you are *tuning* a stage versus *running* the full pipeline.

- **Curated resource bundles.** A bundle is a named, typed, versionable snapshot of bindings + scalar inputs + container images + tool databases that points at fixtures already present under `data/`. Instead of asking the scientist to remember that BUSCO wants `lineage_dataset="eukaryota_odb10"` and `busco_mode="proteins"` with a specific `.sif` at a specific path, `load_bundle("m18_busco_demo")` returns everything needed to run — ready to spread into `run_task` or `run_workflow`.

Crucially, we are not copying stargazer's request plumbing or its metadata-keyed asset indexing (Content-ID model). FlyteTest stays path-based and keyed on its existing manifest + durable-asset-index infrastructure. What we borrow is the *scientist's mental model*: browse a stage or workflow → grab a starter kit → run.

### Family extensibility is load-bearing

The immediate test case for the extensibility story is already in the repository: `src/flytetest/registry/_gatk.py` (added in refactor step B5, dated 2026-04-16) declares a catalog-only `gatk_haplotype_caller` workflow entry — `pipeline_family="variant_calling"`, `pipeline_stage_order=3`, `accepted_planner_types=("ReferenceGenome","AlignmentSet")`, `produced_planner_types=("VariantCallSet",)`, and an empty `showcase_module=""` signalling "not yet wired through the executor." Neither `AlignmentSet` nor `VariantCallSet` exists in `planner_types.py` today.

When a future milestone lights up GATK variant calling, the change must stay inside the registry package, the planner types module, the tasks directory, the workflows directory, and (optionally) `bundles.py`. The MCP tool implementations, the planning engine, the MCP contract constants, the freeze/execute infrastructure, and the resolver must all pick up the new family automatically — because they derive their supported surface from `REGISTRY_ENTRIES` + `showcase_module` (post-B3/B4 refactor). This plan explicitly preserves and tests that contract. Pipeline-family growth is a biology concern; MCP-layer edits are an architecture concern; the two must remain decoupled.

**Known remaining coupling (honest accounting):** `TASK_PARAMETERS` at `server.py:125` is still a hand-maintained dispatch table mapping `task_name` → list of `(param_name, required)` tuples. Adding a new *task* to a new family today does require one line in that table, even though adding a new *workflow* does not. This plan does not fix that coupling in-milestone — it would expand the diff substantially. Instead, the plan documents the coupling explicitly and proposes a follow-up milestone to move task parameter metadata onto `RegistryCompatibilityMetadata` as a new `task_parameters` field, at which point `TASK_PARAMETERS` is deleted and the "no MCP-layer edits required" claim becomes unconditional.

### What already exists (do not reimplement)

Several pieces of the new surface are already in the repo from prior milestones. The plan builds on them rather than duplicating:

- **`run_task` and `run_workflow` MCP tools** (M21, 2026-04-15) at `server.py:995` and `server.py:869`. Current shape: flat `inputs` dict, no freeze step, no `source_prompt` capture, returns `exit_status` + `output_paths` but not `recipe_id` or `run_record_path`. This plan reshapes both in place.
- **`TASK_PARAMETERS` dispatch** at `server.py:125` — covers `exonerate_align_chunk`, `busco_assess_proteins`, `fastqc`, `gffread_proteins` currently. Adding a task adds one entry.
- **Registry filter** `list_entries(category=...)` at `registry/__init__.py:46` — already filters by category. The **MCP-side** `list_entries` tool layers a cosmetic `pipeline_family` filter on top.
- **Registry-as-source-of-truth** (B1–B4 refactor). `RegistryEntry` now carries `category`, `accepted_planner_types`, `produced_planner_types`, `pipeline_family`, `pipeline_stage_order`, `supported_execution_profiles`, and `execution_defaults["slurm_resource_hints"]`.
- **Auto-derived constants.** `_local_node_handlers()` and `SUPPORTED_TASK_NAMES` / `SUPPORTED_WORKFLOW_NAMES` derive automatically from `showcase_module` — the registry drives the runtime surface.
- **Approval gating** (M15 P2, 2026-04-11). `requires_user_approval` is set only for planner-composed novel DAGs produced by `_try_composition_fallback`; registered single-entry targets (everything `run_task`/`run_workflow` dispatches to) bypass the gate correctly.
- **Freeze/execute infrastructure.** `artifact_from_typed_plan`, `save_workflow_spec_artifact`, and `load_workflow_spec_artifact` live in `spec_artifacts.py`. `LocalWorkflowSpecExecutor` and `SlurmWorkflowSpecExecutor` live in `spec_executor.py`. All are generic over any registered target.
- **Durable asset index** (M20b). `DurableAssetRef` + `durable_asset_index.json` sidecar; `LocalManifestAssetResolver.resolve(durable_index=...)` — the plumbing for cross-run output reuse is already in place.
- **Composition fallback** (`_try_composition_fallback` in `planning.py`, M15 P2). Operates on structured planning goals, not prose — keeps working unchanged after we remove the prose-parsing helpers.

### Outcome

After this milestone, the scientist-facing experiment loop is:

```
list_entries(category="workflow", pipeline_family="annotation")
   → browse registered stages; see pipeline family and stage order

list_bundles(pipeline_family="annotation")
   → find a starter kit that matches the stage

load_bundle("braker3_small_eukaryote")
   → get typed bindings, scalar inputs, container images, tool databases

run_workflow("braker3_annotation_workflow", **bundle, source_prompt="...")
   → freeze recipe, execute, return recipe_id + run_record_path + outputs
```

…and every piece of family-specific logic — the planner types, the catalog entry, the tasks, the workflow entrypoint, and (optionally) the bundle — lives under a single pipeline-family surface (`registry/_<family>.py` + `planner_types.py` + `tasks/<family>.py` + `workflows/<family>.py` + an entry in `bundles.py`). The MCP implementation, the planning engine, and the MCP contract stay untouched when a new family is added — modulo the `TASK_PARAMETERS` coupling called out above, slated for a follow-up.

### Backward compatibility — intentional coordinated migration

Reshaping `run_task` and `run_workflow` from the M21 flat `inputs` shape to the new `bindings` + scalar `inputs` + `resources` + `execution_profile` + `runtime_images` + `source_prompt` shape is a hard-break API change. Per DESIGN §8.7, this qualifies as an **intentional compatibility migration** rather than an accidental breakage: it is coordinated inside one branch, all dependent callers (tests, smoke scripts, documentation examples, active milestone plans) are updated in the same change series, and `CHANGELOG.md` records the cutover with a dated entry. No shim for the old flat shape is provided; the scientist's client is expected to adopt the new shape at the same time the server does.

## Changes (with concrete code)

### 1. Widen the MCP `list_entries` tool

`src/flytetest/server.py` — the tool currently returns a thin payload from `_entry_payload()`. Widen it so the catalog reads as a scientist's pipeline map:

```python
def _entry_payload(entry: RegistryEntry) -> dict[str, object]:
    comp = entry.compatibility
    return {
        "name": entry.name,
        "category": entry.category,
        "description": entry.description,
        "pipeline_family": comp.pipeline_family,
        "pipeline_stage_order": comp.pipeline_stage_order,
        "biological_stage": comp.biological_stage,
        "accepted_planner_types": list(comp.accepted_planner_types),
        "produced_planner_types": list(comp.produced_planner_types),
        "supported_execution_profiles": list(comp.supported_execution_profiles),
        "slurm_resource_hints": comp.execution_defaults.get("slurm_resource_hints", {}),
        "local_resource_defaults": comp.execution_defaults.get("resources", {}),
        "inputs": [asdict(f) for f in entry.inputs],
        "outputs": [asdict(f) for f in entry.outputs],
        "tags": list(entry.tags),
    }


@mcp.tool()
def list_entries(category: Literal["task", "workflow"] | None = None,
                 pipeline_family: str | None = None) -> list[dict]:
    """List registered tasks and workflows the scientist may run.

    Each entry exposes the biology-facing contract (accepted/produced planner
    types, pipeline family + stage order, resource hints) so the client can
    choose a stage without reading task source code.
    """
    entries = registry.list_entries(category)
    if pipeline_family:
        entries = tuple(e for e in entries
                        if e.compatibility.pipeline_family == pipeline_family)
    # filter to entries actually wired through the showcase path
    return [_entry_payload(e) for e in entries if e.showcase_module]
```

This is the same filter the registry already exposes — we just layer a cosmetic `pipeline_family` filter on top for conversational browsing (*"what's in variant_calling?"*).

### 2. Reshape `run_task` in place (`server.py:995`)

```python
@mcp.tool()
def run_task(
    task_name: str,
    bindings: dict[str, dict] | None = None,
    inputs: dict | None = None,
    resources: dict | None = None,
    execution_profile: Literal["local", "slurm"] = "local",
    runtime_images: dict[str, str] | None = None,
    source_prompt: str = "",
) -> dict:
    """Run one registered task against typed biological bindings.

    Use this for stage-scoped experimentation (e.g. tuning Exonerate on one
    chunk). The run is frozen into a WorkflowSpec artifact before execution,
    so the experiment is reproducible later from the returned recipe_id.
    """
    if task_name not in SUPPORTED_TASK_NAMES:
        return _unsupported_target_reply(task_name, SUPPORTED_TASK_NAMES, kind="task")
    entry = registry.get_entry(task_name)
    bindings = bindings or {}
    inputs = inputs or {}

    # 1. Validate bindings against the entry's biological contract.
    unknown_types = set(bindings) - set(entry.compatibility.accepted_planner_types)
    if unknown_types:
        return _limitation_reply(
            task_name,
            f"Unknown binding types: {sorted(unknown_types)}. "
            f"Accepted: {list(entry.compatibility.accepted_planner_types)}"
        )

    # 2. Materialize typed planner objects from the binding dicts.
    explicit_bindings = _materialize_bindings(bindings)  # uses planner_adapters

    # 3. Validate scalar inputs against TASK_PARAMETERS for keys NOT bound by typed bindings.
    scalar_params = _scalar_params_for_task(task_name, bindings)
    unknown_scalars = set(inputs) - {p for p, _ in scalar_params}
    if unknown_scalars:
        return _limitation_reply(task_name, f"Unknown scalar inputs: {sorted(unknown_scalars)}")
    missing = [p for p, required in scalar_params if required and inputs.get(p) in (None, "")]
    if missing:
        return _limitation_reply(task_name, f"Missing required inputs: {missing}")

    # 4. Build typed plan (structured input — no text parsing).
    plan = plan_typed_request(
        biological_goal=entry.compatibility.biological_stage or task_name,
        target_name=task_name,
        explicit_bindings=explicit_bindings,
        scalar_inputs=inputs,
        resource_request=_coerce_resource_spec(resources),
        execution_profile=execution_profile,
        runtime_images=runtime_images or {},
        source_prompt=source_prompt,
    )
    if not plan["supported"]:
        return plan  # surfaces decline + close-match suggestions

    # 5. Freeze transparently — the scientist never manages artifact_path.
    artifact = artifact_from_typed_plan(plan, created_at=_now_iso())
    artifact_path = save_workflow_spec_artifact(artifact, DEFAULT_SPEC_DIR)

    # 6. Dispatch via existing executors; registered entries auto-approved.
    if execution_profile == "slurm":
        run_record_path = SlurmWorkflowSpecExecutor().submit(artifact_path)
    else:
        run_record_path = LocalWorkflowSpecExecutor().execute(artifact_path)

    return {
        "supported": True,
        "task_name": task_name,
        "recipe_id": artifact.recipe_id,
        "run_record_path": str(run_record_path),
        "artifact_path": str(artifact_path),
        "execution_profile": execution_profile,
        "outputs": _collect_named_outputs(entry, run_record_path),
        "limitations": [],
    }


def _scalar_params_for_task(task_name: str,
                            bindings: dict[str, dict]) -> list[tuple[str, bool]]:
    """Return TASK_PARAMETERS entries that aren't already covered by typed bindings.

    The scalar-vs-binding split is derived, not hand-maintained: a param name
    covered by a field on any planner type in `bindings` is a binding; the rest
    are scalars. Adding a new task therefore only requires adding an entry to
    TASK_PARAMETERS — no per-task server logic.
    """
    bound_field_names = set()
    for type_name, field_dict in bindings.items():
        bound_field_names.update(field_dict.keys())
    return [(name, required)
            for (name, required) in TASK_PARAMETERS[task_name]
            if name not in bound_field_names]
```

### 3. Reshape `run_workflow` in place (`server.py:869`) — symmetric with `run_task`

**Why symmetric.** An earlier draft made `run_workflow` scalars-only on the theory that "workflows own their internal assembly." In practice bundles carry typed bindings (a reference genome, a read set, a protein evidence set) and scientists will want to hand those bindings directly to a workflow exactly as they would to a task. Forcing the scientist to re-flatten a bundle's typed bindings into scalar path strings for the `run_workflow` call — while `run_task` accepts the typed form — is gratuitous inconsistency. The cleaner contract is: both tools accept the same top-level shape; the workflow entrypoint is free to consume whichever fields are relevant.

```python
@mcp.tool()
def run_workflow(
    workflow_name: str,
    bindings: dict[str, dict] | None = None,
    inputs: dict | None = None,
    resources: dict | None = None,
    execution_profile: Literal["local", "slurm"] = "local",
    runtime_images: dict[str, str] | None = None,
    tool_databases: dict[str, str] | None = None,
    source_prompt: str = "",
    runner: Any = subprocess.run,  # internal test seam; not part of MCP schema
) -> dict:
    """Run a registered workflow entrypoint.

    Accepts the same typed request shape as run_task: biological inputs go in
    `bindings` (keyed by planner-type name), scalar knobs in `inputs`, HPC
    resources in `resources`, container overrides in `runtime_images`, and
    tool-database pointers in `tool_databases`. Every run is frozen into a
    WorkflowSpec on disk before execution, so the scientist can replay the
    exact call later from the returned `recipe_id`.
    """
    if workflow_name not in SUPPORTED_WORKFLOW_NAMES:
        return _unsupported_target_reply(workflow_name, SUPPORTED_WORKFLOW_NAMES, kind="workflow")
    entry = registry.get_entry(workflow_name)
    bindings = bindings or {}
    inputs = inputs or {}

    # 1. Validate bindings against the workflow's biological contract (same rule as run_task).
    unknown_types = set(bindings) - set(entry.compatibility.accepted_planner_types)
    if unknown_types:
        return _limitation_reply(
            workflow_name,
            f"Unknown binding types: {sorted(unknown_types)}. "
            f"Accepted: {list(entry.compatibility.accepted_planner_types)}",
            pipeline_family=entry.compatibility.pipeline_family,
        )

    # 2. Preserve the BRAKER3 evidence-check limitation (server.py:934-949). The check
    #    now looks at both the legacy scalar scape (inputs.protein_fasta_path) and the
    #    new typed shape (bindings.ProteinEvidenceSet, bindings.ReadSet), so the scientist
    #    can satisfy it either way.
    if workflow_name == BRAKER3_WORKFLOW_NAME and not _braker_has_evidence(bindings, inputs):
        return _limitation_reply(
            workflow_name,
            "BRAKER3 requires at least one evidence input (ReadSet or ProteinEvidenceSet).",
            pipeline_family=entry.compatibility.pipeline_family,
        )

    # 3. Materialize typed planner objects, resolving any $ref bindings through the
    #    durable asset index (see §7 for the binding grammar).
    explicit_bindings = _materialize_bindings(bindings)

    plan = plan_typed_request(
        biological_goal=entry.compatibility.biological_stage or workflow_name,
        target_name=workflow_name,
        explicit_bindings=explicit_bindings,
        scalar_inputs=inputs,
        resource_request=_coerce_resource_spec(resources),
        execution_profile=execution_profile,
        runtime_images=runtime_images or {},
        tool_databases=tool_databases or {},
        source_prompt=source_prompt,
    )
    if not plan["supported"]:
        return plan

    artifact = artifact_from_typed_plan(plan, created_at=_now_iso())
    artifact_path = save_workflow_spec_artifact(artifact, DEFAULT_SPEC_DIR)

    if execution_profile == "slurm":
        run_record_path = SlurmWorkflowSpecExecutor().submit(artifact_path)
    else:
        run_record_path = LocalWorkflowSpecExecutor().execute(artifact_path)

    limitations: list[str] = []
    if not source_prompt:
        limitations.append(_EMPTY_PROMPT_ADVISORY)

    return {
        "supported": True,
        "workflow_name": workflow_name,
        "recipe_id": artifact.recipe_id,
        "run_record_path": str(run_record_path),
        "artifact_path": str(artifact_path),
        "execution_profile": execution_profile,
        "outputs": _collect_named_outputs(entry, run_record_path),
        "limitations": limitations,
    }
```

Symmetrizing the surface also means a bundle can be spread into either tool: `run_workflow("braker3_annotation_workflow", **load_bundle("braker3_small_eukaryote"), source_prompt="...")` and `run_task("exonerate_align_chunk", **load_bundle("protein_evidence_demo"), source_prompt="...")` read the same way.

### 3b. Stable named outputs (replace positional `output_paths`)

**Why.** Today `run_task` / `run_workflow` return `output_paths: list[str]` — a positional list with no indication of which path is which. For a single-output task this is workable; for a GATK HaplotypeCaller run producing both a `.g.vcf.gz` and its `.tbi` index, the scientist has to infer which list element is the index by extension sniffing. That is precisely the kind of friction the typed-contracts pillar is meant to remove. Meanwhile, every `RegistryEntry` already carries an `outputs: tuple[InterfaceField, ...]` field where each `InterfaceField` has `name`, `type`, and `description`. Using those names as keys in the reply is essentially free and strictly clearer.

New helper in `server.py`:

```python
def _collect_named_outputs(entry: RegistryEntry, run_record_path: Path) -> dict[str, str]:
    """Return the run's output paths keyed by the registry's declared output names.

    Reads the run record's result manifest, aligns each produced path against
    the InterfaceField.name entries on the registry entry, and returns a
    name-keyed dict. An output declared in the registry but not produced at
    runtime appears with an empty string value and surfaces as a warning in
    the caller's limitations. An output produced at runtime but not declared
    on the entry is a contract violation and raises — the registry is the
    source of truth.
    """
```

Reply shape becomes (for a GATK-style run):

```python
{
    "supported": True,
    "workflow_name": "gatk_haplotype_caller",
    "recipe_id": "2026-04-17T14-22-05Z-abc123",
    "run_record_path": "results/gatk/2026-04-17T14-22-05Z-abc123/run_record.json",
    "artifact_path": ".runtime/specs/2026-04-17T14-22-05Z-abc123.json",
    "execution_profile": "slurm",
    "outputs": {
        "results_dir": "/project/.../results/gatk/2026-04-17T14-22-05Z-abc123/",
    },
    "limitations": [],
}
```

**BC break.** The old `output_paths` key is removed, not kept as a transitional alias — we are already doing a coordinated hard break on `run_task` / `run_workflow` signatures, so an additional named-vs-positional migration inside the same cutover is zero marginal cost. Callers that previously iterated `reply["output_paths"]` iterate `reply["outputs"].values()` instead, which is also clearer. The call-site sweep (§12) catches any stragglers.

### 3c. Expanded `execution_defaults` — environment as a first-class registry concern

**Why not a separate `environment_profiles.py` module.** An earlier draft considered a standalone `environment_profiles.py` catalog (inspired by LatchBio's per-task environment pattern) mapping names like `"braker3_apptainer"` to `{runtime_images, module_loads, env_vars, tool_databases}`. On reflection this creates a second source of truth running parallel to the registry: a scientist would pick a registered workflow AND a separate environment profile, and the composition rules (which overrides what) would need their own mental model. The registry-as-source-of-truth pillar (B1–B4) argues instead for making environment a typed concern on `RegistryCompatibilityMetadata`.

`RegistryCompatibilityMetadata.execution_defaults` today is a loosely-typed `dict[str, object]` holding `{"profile": "local", "result_manifest": "run_manifest.json", "resources": {...}, "slurm_resource_hints": {...}}`. This plan expands the documented schema with four additional keys, each optional:

```python
execution_defaults = {
    # already present
    "profile": "local",
    "result_manifest": "run_manifest.json",
    "resources": {"cpu": "8", "memory": "32Gi", "execution_class": "local"},
    "slurm_resource_hints": {"cpu": "8", "memory": "32Gi", "walltime": "08:00:00"},

    # newly documented keys — all optional, all scoped to the registered entry
    "runtime_images": {"gatk_sif": "data/images/gatk_4.5.0.0.sif"},
    "module_loads": ("python/3.11.9", "apptainer/1.4.1"),
    "env_vars": {"GATK_LOCAL_JAR": "/opt/gatk/gatk.jar"},
    "tool_databases": {"dbsnp_vcf": "data/references/dbsnp_155.vcf.gz"},
}
```

**Resolution order in `run_task` / `run_workflow`:**

1. Start with the entry's `execution_defaults["runtime_images" | "module_loads" | "env_vars" | "tool_databases"]` (empty dict/tuple if absent).
2. Layer on the bundle's fields when a bundle is used via `load_bundle()`.
3. Layer on explicit arguments passed to the run tool (`runtime_images=...`, `tool_databases=...`) — these win.
4. Freeze the fully-resolved environment into the `WorkflowSpec` so replays are deterministic.

**Bundles inherit, not duplicate.** Bundles can now be much leaner: when the registered entry's defaults already name the BRAKER3+STAR containers, a `braker3_small_eukaryote` bundle lists only the scientist-facing inputs (genome, reads, protein evidence) and omits the container dict entirely. The bundle's `runtime_images` field becomes an *override* channel rather than a duplication.

**No new module.** The existing `RegistryCompatibilityMetadata` dataclass in `registry/_types.py` grows no new fields; the change is entirely in the documented schema of the existing `execution_defaults` dict and in the resolution code inside `plan_typed_request` / `artifact_from_typed_plan`. That keeps the B1–B4 registry-as-source-of-truth pillar intact without introducing a parallel catalog.

**Catalog surfacing.** `list_entries()` returns the entry's `execution_defaults` verbatim in its payload (the existing `_entry_payload` already exposes the `slurm_resource_hints` and `resources` keys; the new keys ride along on the same dict). Clients inspecting a workflow see its container and tool-DB requirements without reading registry code.

### 4. New module `src/flytetest/bundles.py`

**Why bundles.** A scientist running BUSCO on a new proteome does not want to be the person who remembers that the eukaryote lineage lives at `data/busco/lineages/eukaryota_odb10/`, that `busco_mode` must be `"proteins"` for a gene-prediction QC run (versus `"genome"` or `"transcripts"`), or that the correct container is `data/images/busco_5.7.1.sif` rather than some older image lingering in the tree. A *bundle* packages all of that — the typed bindings, the scalar defaults, the runtime image paths, and the tool-database pointers — behind a single memorable name like `m18_busco_demo`. The scientist calls `load_bundle("m18_busco_demo")`, spreads the result into `run_workflow` or `run_task`, and goes to lunch.

Bundles are also a soft form of versioning. When the tool-database path changes (e.g. BUSCO lineage updates from `odb10` to `odb12`), a bundle revision bumps in one place instead of every scientist's prompt. The reproducibility pillar still holds because each executed run captures the concrete resolved paths into its frozen `WorkflowSpec` — the bundle is just a convenient way to produce those paths.

**Why startup validation was the wrong choice.** An earlier draft of this plan validated every bundle at module import time, hard-failing server startup if any referenced path was missing. On reflection this is too brittle: a missing BUSCO lineage directory should not prevent the scientist from running an unrelated Exonerate task. The corrected design keeps validation but defers it to call time (`list_bundles`, `load_bundle`) and reports unavailability as structured data rather than a crashed import.

**Module layout:**

```python
"""Curated resource bundles — turn-key starter inputs for registered entries.

A bundle is a named, typed snapshot of bindings + scalar inputs + container
images pointing at existing fixtures under `data/`. Bundles stay portable
across pipeline families because they key on the generic biology types from
M23-M26 (`CodingPredictionResult`, `ProteinAlignmentChunkResult`, etc.) and
the stable planner types from `planner_types.py`.

Adding a new family's bundle means appending one entry to BUNDLES — nothing
in server.py, planning.py, or mcp_contract.py needs to change.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from flytetest.registry import REGISTRY_ENTRIES, get_entry


@dataclass(frozen=True)
class ResourceBundle:
    name: str
    description: str
    pipeline_family: str
    bindings: dict[str, dict]           # planner-type name -> field dict
    inputs: dict[str, object]           # scalar defaults
    runtime_images: dict[str, str]      # container defaults; scientist may override
    tool_databases: dict[str, str]      # reference data (BUSCO lineage, EVM weights, dbSNP, ...)
    applies_to: tuple[str, ...]         # registered entry names


BUNDLES: dict[str, ResourceBundle] = {
    "braker3_small_eukaryote": ResourceBundle(
        name="braker3_small_eukaryote",
        description="Small-eukaryote BRAKER3 annotation starter kit: reference "
                    "genome, paired RNA-seq reads, protein evidence.",
        pipeline_family="annotation",
        bindings={
            "ReferenceGenome": {"fasta_path": "data/braker3/reference/genome.fa"},
            "ReadSet": {
                "sample_id": "demo",
                "left_reads_path": "data/braker3/rnaseq/reads_1.fq.gz",
                "right_reads_path": "data/braker3/rnaseq/reads_2.fq.gz",
            },
            "ProteinEvidenceSet": {
                "protein_fasta_path": "data/braker3/protein_data/fastas/proteins.fa",
            },
        },
        inputs={"braker_species": "demo_species"},
        runtime_images={
            "braker_sif": "data/images/braker3_3.0.7.sif",
            "star_sif": "data/images/star_2.7.11a.sif",
        },
        tool_databases={},
        applies_to=("braker3_annotation_workflow",),
    ),
    "m18_busco_demo": ResourceBundle(
        name="m18_busco_demo",
        description="M18 BUSCO fixture: small eukaryote proteins + lineage path.",
        pipeline_family="annotation",
        bindings={"ReferenceGenome": {"fasta_path": "data/busco/fixtures/genome.fa"}},
        inputs={"lineage_dataset": "eukaryota_odb10", "busco_cpu": 2, "busco_mode": "proteins"},
        runtime_images={"busco_sif": "data/images/busco_5.7.1.sif"},
        tool_databases={"busco_lineage_dir": "data/busco/lineages/eukaryota_odb10"},
        applies_to=("busco_assess_proteins", "busco_annotation_qc_workflow"),
    ),
    # ... protein_evidence_demo, rnaseq_paired_demo follow the same pattern
}


@dataclass(frozen=True)
class BundleAvailability:
    """Structured availability result for a bundle.

    `available=True` means every referenced file/directory exists on disk and
    the bundle is structurally consistent with its declared applies_to entries.
    `available=False` means one or more paths are missing or the registry
    contract is violated; the `reasons` field lists each problem as a short
    string suitable for surfacing to the scientist.
    """
    name: str
    available: bool
    reasons: tuple[str, ...] = ()


def _check_bundle_availability(b: ResourceBundle) -> BundleAvailability:
    """Return structured availability for a bundle without raising.

    This is the runtime check used by list_bundles() and load_bundle(). It
    replaces the earlier import-time hard-fail so that a missing BUSCO lineage
    directory cannot prevent the server from starting or block unrelated
    tasks.
    """
    reasons: list[str] = []

    # (a) every referenced path exists on disk (bindings, images, tool_databases)
    for type_name, field_dict in b.bindings.items():
        for field_name, value in field_dict.items():
            if field_name.endswith("_path") and not Path(value).exists():
                reasons.append(f"{type_name}.{field_name} missing: {value}")
    for key, value in b.runtime_images.items():
        if not Path(value).exists():
            reasons.append(f"runtime_image {key} missing: {value}")
    for key, value in b.tool_databases.items():
        if not Path(value).exists():
            reasons.append(f"tool_database {key} missing: {value}")

    # (b) every applies_to entry exists and accepts the bundle's binding types
    for entry_name in b.applies_to:
        try:
            entry = get_entry(entry_name)
        except KeyError:
            reasons.append(f"applies_to entry {entry_name!r} not in registry")
            continue
        accepted = set(entry.compatibility.accepted_planner_types)
        missing = set(b.bindings) - accepted
        if missing:
            reasons.append(
                f"bindings {sorted(missing)} not accepted by {entry_name!r} "
                f"(accepts {sorted(accepted)})"
            )
        if entry.compatibility.pipeline_family != b.pipeline_family:
            reasons.append(
                f"pipeline_family {b.pipeline_family!r} mismatches "
                f"{entry_name!r} family {entry.compatibility.pipeline_family!r}"
            )

    return BundleAvailability(name=b.name, available=not reasons, reasons=tuple(reasons))


def list_bundles(pipeline_family: str | None = None) -> list[dict]:
    """Enumerate curated bundles, optionally filtered by pipeline family.

    Each entry includes an `available` flag plus a `reasons` list — unavailable
    bundles are not hidden; they are surfaced so a scientist can see what is
    missing ("download the eukaryota_odb10 lineage to data/busco/lineages/")
    and decide whether to proceed.
    """
    results: list[dict] = []
    for b in BUNDLES.values():
        if pipeline_family is not None and b.pipeline_family != pipeline_family:
            continue
        status = _check_bundle_availability(b)
        results.append({
            "name": b.name,
            "description": b.description,
            "pipeline_family": b.pipeline_family,
            "applies_to": list(b.applies_to),
            "binding_types": sorted(b.bindings.keys()),
            "available": status.available,
            "reasons": list(status.reasons),
        })
    return results


def load_bundle(name: str) -> dict:
    """Return a bundle's typed bindings + scalar inputs + runtime images ready
    to spread into run_task / run_workflow.

    If the named bundle does not exist, raises KeyError listing the available
    names. If the bundle exists but is unavailable (missing files, registry
    mismatch), returns a structured reply with supported=False and the reasons
    — never silently returning partial data.
    """
    if name not in BUNDLES:
        raise KeyError(f"Unknown bundle {name!r}. Available: {sorted(BUNDLES)}")
    b = BUNDLES[name]
    status = _check_bundle_availability(b)
    if not status.available:
        return {
            "supported": False,
            "name": b.name,
            "reasons": list(status.reasons),
            "next_steps": [
                "Resolve the missing paths under data/ and retry load_bundle(...)",
                "Or call list_available_bindings() to locate substitute inputs",
            ],
        }
    return {
        "supported": True,
        "bindings": dict(b.bindings),
        "inputs": dict(b.inputs),
        "runtime_images": dict(b.runtime_images),
        "tool_databases": dict(b.tool_databases),
        "description": b.description,
        "pipeline_family": b.pipeline_family,
    }
```

No module-level `_validate_bundles()` call. The server boots cleanly regardless of which seed bundles have their backing data present. Bundles appear in `list_bundles()` with honest availability flags; `load_bundle()` refuses unavailable bundles with structured reasons the scientist can act on.

Then in `server.py`:

```python
@mcp.tool()
def list_bundles(pipeline_family: str | None = None) -> list[dict]:
    """List curated starter bundles the scientist can use as inputs."""
    return _bundles.list_bundles(pipeline_family)


@mcp.tool()
def load_bundle(name: str) -> dict:
    """Return a bundle ready to spread into run_task / run_workflow."""
    return _bundles.load_bundle(name)
```

### 5. Remove prose heuristics from `src/flytetest/planning.py`

Delete:

- `_extract_prompt_paths`, `_extract_braker_workflow_inputs`, `_extract_protein_workflow_inputs` (`planning.py:254-414`).
- `_extract_execution_profile` regex (`planning.py:657-675`).
- `_extract_runtime_images` regex (`planning.py:678-694`).
- M18 BUSCO keyword branch in biological-goal derivation (`planning.py:921-985`).
- `_classify_target` keyword scoring (`planning.py:769-840`).

Reshape `plan_typed_request` to a structured-only entrypoint:

```python
def plan_typed_request(
    *,
    biological_goal: str,
    target_name: str,
    explicit_bindings: dict[str, PlannerSerializable] | None = None,
    scalar_inputs: dict[str, object] | None = None,
    resource_request: ResourceSpec | None = None,
    execution_profile: str = "local",
    runtime_images: dict[str, str] | None = None,
    source_prompt: str = "",
    manifest_sources: Sequence[Path] = (),
) -> dict[str, object]:
    """Build a typed plan from structured inputs. No prose parsing.

    The source_prompt is captured verbatim into the WorkflowSpec for the
    audit-trail pillar; it is not parsed.
    """
    # ... structured logic only; _try_composition_fallback + approval gating preserved
```

`plan_request` (the free-text preview tool) returns a helpful decline pointing at `run_task` / `run_workflow` / `list_bundles` rather than attempting to parse prose.

### 6. Tool descriptions in `src/flytetest/mcp_contract.py`

Reframe the primary surface as *"the scientist's experiment loop"* — `list_entries` → `list_bundles` → `load_bundle` → `run_task` or `run_workflow`. Mark `prepare_run_recipe`, `run_local_recipe`, `run_slurm_recipe`, `approve_composed_recipe` as **inspect-before-execute** power-user tools. Lifecycle tools (`monitor_slurm_job`, `cancel_slurm_job`, `retry_slurm_job`, `wait_for_slurm_job`, `fetch_job_log`, `get_run_summary`, `inspect_run_result`, `get_pipeline_status`, `list_available_bindings`) unchanged.

Every `run_task` / `run_workflow` / `run_slurm_recipe` description carries a one-sentence note on **resource-hint handoff** (DESIGN §7.5): `execution_defaults["slurm_resource_hints"]` supplies sensible defaults for `cpu`/`memory`/`walltime`, but `queue` and `account` must come from the user — the server never invents them.

### 7. Binding-value grammar and cross-run output reuse

**Why one grammar.** A scientist might want to express a binding three different ways in the same working session:

1. *"Use this file I have on disk right now."* — a raw path.
2. *"Use whatever the annotation manifest from my last BRAKER3 run says the GFF is."* — a manifest-resolved asset.
3. *"Use the GFF output of recipe `2026-04-16T12-00-00Z-abc123`."* — a durable reference to a prior run output.

All three are *biologically* the same kind of input (an `AnnotationGff`, say); only the provenance differs. Having three different top-level shapes in `run_task` / `run_workflow` for the same type of thing would be poor ergonomics. Instead, every binding value is a dict that may carry any of three mutually-exclusive forms, resolved through one code path (`_materialize_bindings`):

```python
# Form A — raw path (already supported):
bindings={"ReferenceGenome": {"fasta_path": "data/braker3/reference/genome.fa"}}

# Form B — manifest-resolved asset (already supported through LocalManifestAssetResolver):
bindings={"AnnotationGff": {"$manifest": "results/braker3/2026-04-15/run_manifest.json",
                            "output_name": "annotation_gff"}}

# Form C — durable reference to a prior run output (new):
bindings={"AnnotationGff": {"$ref": {"run_id": "2026-04-16T12-00-00Z-abc123",
                                     "output_name": "annotation_gff"}}}
```

Mixing is allowed across bindings in the same call: the scientist can pass a raw-path `ReferenceGenome` and a `$ref`-based `AnnotationGff` in one `run_workflow` call.

**Resolution and freeze semantics.** `_materialize_bindings` in `resolver.py` dispatches on the form:
- Form A: constructs the planner dataclass directly.
- Form B: already handled — calls `LocalManifestAssetResolver.resolve(manifest_path, output_name)`.
- Form C (new): calls `LocalManifestAssetResolver.resolve(run_id, output_name, durable_index=_load_durable_index())` (M20b).

Once resolved, every form lowers to the same concrete planner dataclass with a concrete filesystem path. That concrete path is then frozen into the `WorkflowSpec`, which means the recipe remains replayable even if the durable asset index is later rewritten — the pointer indirection is a convenience for the scientist, not a reproducibility promise on its own.

**Failure modes.** If a `$ref` refers to an unknown `run_id`, the reply is a typed decline with the offending `run_id` in `limitations` and `next_steps` pointing at `list_available_bindings()` or at a re-run of the producing workflow. If a `$ref` refers to a real `run_id` but a missing `output_name`, the reply enumerates the known output names for that run. If a `$manifest` path does not exist, the reply names the expected manifest file. No silent fall-throughs.

### 8. Preflight offline-compute staging validation

New module `src/flytetest/staging.py`:

```python
"""Preflight checks that every container image, tool database, and resolved
input path is reachable on the compute-visible filesystem before a Slurm job
is submitted. Mirrors DESIGN §7.5's offline-compute invariant — compute nodes
cannot reach the internet, so unreachable paths fail the job silently.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StagingFinding:
    kind: str           # "container" | "tool_database" | "input_path"
    key: str            # e.g. "braker_sif", "busco_lineage_dir", "ReferenceGenome.fasta_path"
    path: str
    reason: str         # "not_found" | "not_readable" | "not_on_shared_fs"


def check_offline_staging(artifact, shared_fs_roots: tuple[Path, ...]) -> list[StagingFinding]:
    """Inspect a frozen WorkflowSpec artifact and return staging findings.

    `shared_fs_roots` is read from the Slurm resource request (e.g. the
    project's `/project/...` or `/scratch/...` prefixes). A path is "on shared
    fs" when one of the roots is a parent. `local` profile skips the shared-fs
    check but still verifies existence.
    """
    findings: list[StagingFinding] = []
    for key, image_path in artifact.runtime_images.items():
        findings.extend(_check_path("container", key, image_path, shared_fs_roots))
    for key, db_path in artifact.tool_databases.items():
        findings.extend(_check_path("tool_database", key, db_path, shared_fs_roots))
    for key, input_path in artifact.resolved_input_paths.items():
        findings.extend(_check_path("input_path", key, input_path, shared_fs_roots))
    return findings
```

Wired into `SlurmWorkflowSpecExecutor.submit`: before calling `sbatch`, run `check_offline_staging`; if any findings are returned, block submission and surface them in the MCP reply as structured `limitations`. The existing `classify_slurm_failure()` semantics are untouched (hard constraint per AGENTS.md).

`WorkflowSpec` gains a `tool_databases: dict[str, str]` field (carried through from the originating bundle or explicit argument). `artifact_from_typed_plan` wires it from the plan.

### 9. `source_prompt` empty-warning

In `run_task` / `run_workflow` / `plan_typed_request`, when `source_prompt == ""`, append a non-fatal advisory to the returned `limitations`:

```python
if not source_prompt:
    limitations.append("source_prompt was empty; the frozen recipe will lack "
                       "the original scientist request in its audit trail. "
                       "Pass source_prompt=<user question> for full provenance.")
```

This keeps pillar #2 (frozen recipes have provenance) honest without breaking clients that haven't adopted the field yet.

### 10. Structured decline routing with broad next-step suggestions

**Why.** When a `run_*` call declines, the scientist needs an obvious next move — not a dead-end error. "BRAKER3 requires at least one evidence input" on its own is true but unhelpful. What the scientist actually wants to know is: *"Is there a starter kit I can try? Do I already have suitable evidence on disk from a prior run? Can I reformulate the question?"* The decline payload should answer all three.

`_limitation_reply` and `_unsupported_target_reply` are extended to populate three optional next-step channels whenever the decline names a specific registered entry and its pipeline family:

- `suggested_bundles` — bundles whose `applies_to` includes the declined target AND whose availability check currently passes. A declined bundle is filtered out so the scientist never sees "try this" pointing at a broken starter kit.
- `suggested_prior_runs` — entries from the durable asset index whose produced outputs match a planner type the target accepts. This is the "you might already have a BAM from last week" channel.
- `next_steps` — human-readable action strings that combine the above plus generic recovery options (reformulate prompt, call `list_available_bindings()` to discover unbound workspace files, widen or narrow the biological goal).

The reply shape becomes:

```python
{
    "supported": False,
    "target": "braker3_annotation_workflow",
    "pipeline_family": "annotation",
    "limitations": ["BRAKER3 requires at least one evidence input (ReadSet or ProteinEvidenceSet)."],
    "suggested_bundles": [
        {
            "name": "braker3_small_eukaryote",
            "description": "Small-eukaryote BRAKER3 starter kit: reference genome, paired RNA-seq reads, protein evidence.",
            "applies_to": ["braker3_annotation_workflow"],
            "available": True,
        },
    ],
    "suggested_prior_runs": [
        {
            "run_id": "2026-04-14T09-12-33Z-def456",
            "produced_type": "ReadSet",
            "output_name": "rnaseq_reads",
            "hint": "Use bindings={'ReadSet': {'$ref': {'run_id': '...', 'output_name': 'rnaseq_reads'}}}",
        },
    ],
    "next_steps": [
        "load_bundle('braker3_small_eukaryote') then re-call run_workflow",
        "Or reference a prior run output via the $ref binding form (see suggested_prior_runs)",
        "Or call list_available_bindings() to locate RNA-seq / protein FASTA inputs under data/",
        "Or reformulate the request with explicit evidence files",
    ],
}
```

`plan_request` (the free-text preview tool) uses the same routing when it declines, so that a client-side LLM getting a "not supported" back has a concrete recovery path without needing to parse prose itself.

### 11. New `validate_run_recipe` MCP tool

DESIGN §6.2 lists this tool; it doesn't exist yet. Add to `server.py`:

```python
@mcp.tool()
def validate_run_recipe(artifact_path: str,
                        execution_profile: Literal["local", "slurm"] = "local",
                        shared_fs_roots: list[str] | None = None) -> dict:
    """Validate a frozen recipe without executing it.

    Runs the same preflight checks a real execution would — inputs resolve
    through the manifest + durable asset index, containers and tool databases
    exist, and (for slurm) every staged path sits on a compute-visible root.
    """
    artifact = load_workflow_spec_artifact(Path(artifact_path))
    findings: list[dict] = []

    # resolve every input binding through the existing resolver
    resolver = LocalManifestAssetResolver()
    for binding_name, binding in artifact.bindings.items():
        try:
            resolver.resolve(binding, durable_index=_load_durable_index())
        except Exception as exc:
            findings.append({"kind": "binding", "key": binding_name, "reason": str(exc)})

    # staging check
    roots = tuple(Path(r) for r in (shared_fs_roots or []))
    for f in check_offline_staging(artifact, roots):
        findings.append({"kind": f.kind, "key": f.key, "path": f.path, "reason": f.reason})

    return {
        "supported": len(findings) == 0,
        "recipe_id": artifact.recipe_id,
        "execution_profile": execution_profile,
        "findings": findings,
    }
```

Register in `create_mcp_server()` alongside the other tools; advertise in `mcp_contract.py` as part of the inspect-before-execute group.

### 12. Call-site sweep for the BC migration

Because `run_task` / `run_workflow` change shape (not shimmed), every caller breaks the moment the signature changes. Sweep and update in the same commit series:

- `tests/test_server.py`, `tests/test_mcp_prompt_flows.py`, `tests/test_planning.py`, `tests/test_spec_executor.py`, and any other test referencing the flat `inputs=...` shape.
- Smoke scripts under `scripts/` (if any invoke `run_task`/`run_workflow`).
- `docs/mcp_showcase.md` and `docs/tutorial_context.md` walkthroughs.
- `docs/realtime_refactor_plans/` active plans that quote the old shape.

Grep anchors: `rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/` — every hit is a call-site review. CI green post-sweep is part of the acceptance criteria.

### 13. Seed-bundle tool-DB reality check

`_validate_bundles()` fires at import. If a seed bundle references `data/busco/lineages/eukaryota_odb10/` and that directory is absent, the server won't boot. Before merging:

- Audit each seed bundle against what actually ships under `data/`.
- For bundles whose tool DBs already exist: ship as-is.
- For bundles whose tool DBs don't exist locally: either drop the missing bundle from the initial seed set (preferred — ship fewer, working bundles) or mark the specific tool-DB paths with a `demo_only=True` flag that `_validate_bundles()` treats as a soft-warn instead of a hard failure.

Decision: **ship fewer, working bundles** — hard-fail validation stays loud; a bundle is either usable or absent.

### 14. Documentation and coding-agent context refresh

The `.codex/` specialist guides and top-level agent files are the context future Claude sessions (and other contributors) load first. After the surface reshape lands, these must reflect the new reality or every downstream session will propose the old patterns. In-scope updates:

**Top-level**
- `AGENTS.md` — add `bundles.py`, `staging.py`, `validate_run_recipe` to the Project Structure orientation; update the Prompt/MCP/Slurm section to mention the scientist's experiment loop (`list_entries` → `list_bundles` → `load_bundle` → `run_task`/`run_workflow`) and the preflight staging invariant.
- `CLAUDE.md` — no structural change; verify the @AGENTS.md include still pulls updated content.
- `DESIGN.md` — update §6.2 MCP tool surface (add `list_bundles`, `load_bundle`, `validate_run_recipe`; note `prepare_*` are inspect-before-execute power tools); add a sentence to the opening that new pipeline families plug in without MCP-layer edits; update §7.5 to reference the preflight staging check by name.
- `CHANGELOG.md` — dated entry covering: heuristic removal, MCP reshape (with BC-break call-out), bundles, staging preflight, `validate_run_recipe`, `$ref` bindings, decline-to-bundles routing, resource-hint handoff docs.

**`.codex/` specialist guides**
- `.codex/registry.md` — add the "Adding a Pipeline Family" walkthrough (`_<family>.py` + planner types + tasks + workflows + optional bundle, nothing else). Link the GATK placeholder as the worked example.
- `.codex/tasks.md` — document the `bindings` vs `inputs` split for `run_task`; show how `TASK_PARAMETERS` entries map to scalar inputs once typed bindings cover the rest.
- `.codex/workflows.md` — document that workflows receive scalar `inputs` only at the MCP boundary and own their internal assembly.
- `.codex/testing.md` — add patterns for: mocking `_validate_bundles()` in unit tests, testing `$ref` resolution, testing preflight staging findings, asserting the decline-to-bundles shape.
- `.codex/documentation.md`, `.codex/comments.md` — no changes unless a grep surfaces stale examples referencing the old flat shape.
- `.codex/code-review.md` — add a checklist item: MCP-layer PRs must not introduce family-specific branches; families live in `registry/_<family>.py` + `tasks/` + `workflows/` + optional `bundles.py`.

**`.codex/agent/` role prompts**
- `.codex/agent/registry.md` — mirror `.codex/registry.md` updates for the registry-specialist agent.
- `.codex/agent/task.md`, `.codex/agent/workflow.md` — reflect the new run-tool shapes so the specialist agents propose bindings/scalar-input code, not flat-dict code.
- `.codex/agent/test.md` — mirror `.codex/testing.md` additions.
- `.codex/agent/code-review.md` — mirror the MCP-layer-branch-free checklist.
- `.codex/agent/architecture.md` — note the scientist's experiment loop and the family-extensibility contract as load-bearing constraints.

**Realtime refactor docs**
- `docs/realtime_refactor_checklist.md` — tick off items this milestone closes (heuristic removal, bundles, validate_run_recipe); add a new line for any items promoted from OOS.
- `docs/realtime_refactor_milestone_*_submission_prompt.md` — update the active milestone's prompt to reflect the reshape if it references the old MCP surface.
- On completion, archive the superseded planning doc to `docs/realtime_refactor_plans/archive/` per `AGENTS.md` §Behavior Changes.

**User-facing docs**
- `docs/mcp_showcase.md` — primary walkthrough rewritten around `list_entries` → `list_bundles` → `load_bundle` → `run_task` / `run_workflow`; keep `prepare_run_recipe` as an Inspect-Before-Execute appendix; add a short "Adding a Pipeline Family" section linking `.codex/registry.md`.
- `docs/tutorial_context.md` — typed-binding prompt templates; add a `$ref` cross-run-reuse example.
- `docs/braker3_evm_notes.md` — no changes unless a grep surfaces old shape references.

**Grep sweep for stale context clues**
`rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md` → every hit is a doc to update. Re-run after edits to confirm zero stale references.

## Extensibility: Adding a New Pipeline Family (GATK walkthrough)

The `_gatk.py` placeholder (B5, 2026-04-16) is the concrete extension test. Here is exactly what a future milestone needs to change to light up GATK — and, critically, what it does **not**:

**Files that change:**

1. `src/flytetest/planner_types.py` — add `AlignmentSet` and `VariantCallSet` planner dataclasses, mirroring `ReadSet` / `ProteinEvidenceSet`:
   ```python
   @dataclass(frozen=True)
   class AlignmentSet(PlannerSerializable):
       sample_id: str
       bam_path: Path
       bai_path: Path | None = None
       source_run_manifest: Path | None = None

   @dataclass(frozen=True)
   class VariantCallSet(PlannerSerializable):
       sample_id: str
       gvcf_path: Path
       tbi_path: Path | None = None
       reference: ReferenceGenome | None = None
       source_run_manifest: Path | None = None
   ```
2. `src/flytetest/registry/_gatk.py` — populate `showcase_module="flytetest.workflows.gatk"` so the entry surfaces on the MCP.
3. `src/flytetest/tasks/gatk.py` — **new** — Flyte task wrappers for `gatk_haplotype_caller`, matching the `InterfaceField` declarations.
4. `src/flytetest/workflows/gatk.py` — **new** — the workflow entrypoint `gatk_haplotype_caller`.
5. `src/flytetest/bundles.py` — optionally append a `gatk_small_wgs_demo` entry under `pipeline_family="variant_calling"`.
6. `src/flytetest/server.py` — **one line** added to `TASK_PARAMETERS` if the family introduces new *tasks* (not workflows) that expose scalar parameters. This is a documented known coupling; see "Remaining Coupling" below.

**Files that do NOT change (the extensibility contract):**

- `src/flytetest/server.py` run-tool implementations — `run_task` / `run_workflow` / `list_entries` / `list_bundles` / `load_bundle` / `validate_run_recipe` pick up the new entry automatically through `REGISTRY_ENTRIES`, `SUPPORTED_TASK_NAMES`, `SUPPORTED_WORKFLOW_NAMES`, and `_local_node_handlers()` (all registry-derived since refactor steps B3+B4). The contract is that no branching logic on family name appears in the run tools.
- `src/flytetest/planning.py` — structured-only `plan_typed_request` validates against the new entry's `accepted_planner_types` without family-specific branches.
- `src/flytetest/mcp_contract.py` — surface constants derive from the registry.
- `src/flytetest/spec_artifacts.py`, `spec_executor.py`, `staging.py` — freeze/execute/staging infrastructure is generic over any registered target.
- `src/flytetest/resolver.py` — already handles manifest + durable-index resolution generically.
- `src/flytetest/registry/__init__.py` — one-line import of `GATK_ENTRIES` already landed (B5); the same pattern applies to any new family.

**Remaining Coupling (honest accounting):** Adding a new *task* currently requires one entry in `TASK_PARAMETERS` at `server.py:125`. This is a list of `(param_name, required)` tuples covering scalar inputs that are not already covered by typed bindings. Adding a new *workflow* does not require touching this table because the workflow entrypoint consumes scalars from its own signature rather than through MCP-layer validation. The "no MCP-layer edits required" claim is therefore currently bounded: it holds for workflows unconditionally, and it holds for tasks as soon as a follow-up milestone moves task parameter metadata onto `RegistryCompatibilityMetadata.task_parameters` (a tuple of `InterfaceField`-like entries per task). That follow-up is trivially mechanical; it is not in this milestone only because reshaping the run tools and the bundle surface together is already a sufficiently large diff.

What the scientist then sees (no code change to the MCP tools):

```
list_entries(pipeline_family="variant_calling")
  → [{"name": "gatk_haplotype_caller", "category": "workflow",
      "pipeline_family": "variant_calling", "pipeline_stage_order": 3,
      "accepted_planner_types": ["ReferenceGenome", "AlignmentSet"],
      "produced_planner_types": ["VariantCallSet"],
      "slurm_resource_hints": {"cpu": "8", "memory": "32Gi", "walltime": "08:00:00"}, ...}]

list_bundles(pipeline_family="variant_calling")
  → [{"name": "gatk_small_wgs_demo", "applies_to": ["gatk_haplotype_caller"], ...}]

run_workflow("gatk_haplotype_caller",
             inputs={"sample_name": "NA12878", "emit_ref_confidence": "GVCF"},
             resources={"cpu": 8, "memory": "32Gi", "walltime": "08:00:00",
                        "queue": "caslake", "account": "rcc-staff"},
             execution_profile="slurm",
             source_prompt="Call variants on NA12878 with GATK4 in GVCF mode.")
  → {"supported": True, "run_record_path": "...", "recipe_id": "...", ...}
```

This is the extensibility contract: pipeline-family growth is a `registry/_<family>.py` + `planner_types.py` + `tasks/` + `workflows/` + optional `bundles.py` change, never an MCP-layer change.

## Critical Files

- `src/flytetest/server.py` — reshape `run_task` (line 995), `run_workflow` (line 869), widen `list_entries`; register `list_bundles` / `load_bundle` / `validate_run_recipe` in `create_mcp_server()`; add `source_prompt` empty-warning and decline-to-bundles routing in the reply helpers.
- `src/flytetest/planning.py` — delete the prose heuristics; reshape `plan_typed_request` to structured-only; preserve composition fallback and approval plumbing.
- `src/flytetest/mcp_contract.py` — update tool descriptions; reframe around the scientist's experiment loop; add the resource-hint handoff note to run tools.
- `src/flytetest/bundles.py` — **new**.
- `src/flytetest/staging.py` — **new**. Preflight container / tool-DB / input-path staging checks.
- `src/flytetest/spec_artifacts.py` — add `tool_databases` field on `WorkflowSpec`; wire through `artifact_from_typed_plan`.
- `src/flytetest/spec_executor.py` — `SlurmWorkflowSpecExecutor.submit` calls `check_offline_staging` before `sbatch`, surfaces findings as structured limitations, skips submission on any finding. `classify_slurm_failure()` untouched.
- `src/flytetest/resolver.py` — `_materialize_bindings` handles the `{"$ref": {"run_id":..., "output_name":...}}` shape via existing `LocalManifestAssetResolver.resolve(durable_index=...)`.
- **Call-site sweep (BC migration)**: `tests/test_server.py`, `tests/test_mcp_prompt_flows.py`, `tests/test_planning.py`, `tests/test_spec_executor.py`, any `scripts/` invoking `run_task`/`run_workflow`, `docs/mcp_showcase.md`, `docs/tutorial_context.md`, active `docs/realtime_refactor_plans/*.md`.
- **Agent context**: `AGENTS.md`, `DESIGN.md` (§6.2, §7.5, opening), `CHANGELOG.md`, `.codex/registry.md`, `.codex/tasks.md`, `.codex/workflows.md`, `.codex/testing.md`, `.codex/code-review.md`, `.codex/agent/registry.md`, `.codex/agent/task.md`, `.codex/agent/workflow.md`, `.codex/agent/test.md`, `.codex/agent/code-review.md`, `.codex/agent/architecture.md`.
- **Realtime refactor tracking**: `docs/realtime_refactor_checklist.md`; active `docs/realtime_refactor_milestone_*_submission_prompt.md`; archive the superseded plan doc on completion.
- **Seed-bundle audit**: audit `data/` against `BUNDLES`; drop bundles whose tool DBs or runtime images don't exist locally (ship fewer, working bundles).
- `tests/test_server.py`, `tests/test_mcp_prompt_flows.py`, `tests/test_planning.py` — exercise new `run_task` / `run_workflow` shapes and bundle flow; add an extensibility test that registers a synthetic `_testfamily.py` entry and asserts `list_entries(pipeline_family="testfamily")` + `run_workflow("test_stage", ...)` work without MCP-layer edits.
- `docs/mcp_showcase.md` — primary walkthrough around `list_entries` → `list_bundles` → `load_bundle` → `run_task` / `run_workflow`, framed as the scientist's experiment loop. Keep `prepare_run_recipe` walkthrough as an Inspect-Before-Execute appendix. Add a short *"Adding a Pipeline Family"* section linking to `.codex/registry.md`.
- `docs/tutorial_context.md` — typed-binding prompt templates.
- `DESIGN.md` §6.2 — update listed MCP tool surface; add a sentence that new pipeline families plug in without MCP-layer edits.
- `CHANGELOG.md` — dated entry.

## Reused Utilities

- `RegistryEntry.category`, `accepted_planner_types`, `produced_planner_types`, `pipeline_family`, `pipeline_stage_order`, `execution_defaults["slurm_resource_hints"]` (`registry/_types.py:47-63`).
- `registry.list_entries(category)`, `registry.get_entry(name)` (`registry/__init__.py:46,60`).
- `TASK_PARAMETERS` (`server.py:125`).
- `artifact_from_typed_plan`, `save_workflow_spec_artifact`, `load_workflow_spec_artifact` (`spec_artifacts.py`).
- `LocalWorkflowSpecExecutor`, `SlurmWorkflowSpecExecutor` (`spec_executor.py`).
- `LocalManifestAssetResolver`, `DurableAssetRef` (`resolver.py`, `spec_artifacts.py`).
- Planner dataclasses (`planner_types.py`, `types/assets.py`).
- `_try_composition_fallback`, `requires_user_approval` plumbing (`planning.py` — keep intact).

## Verification

1. **Compile**: `python -m compileall src/flytetest/server.py src/flytetest/planning.py src/flytetest/bundles.py`.
2. **Heuristic removal**: `rg -n "_extract_prompt_paths|_extract_braker_workflow_inputs|_extract_protein_workflow_inputs|_classify_target|_extract_execution_profile|_extract_runtime_images" src/flytetest/` → zero hits.
3. **Pipeline-map catalog**: `list_entries(category="workflow")` populates `pipeline_family`, `pipeline_stage_order`, `accepted_planner_types`, `produced_planner_types`, `slurm_resource_hints` for every showcased entry. `list_entries(pipeline_family="variant_calling")` returns the `gatk_haplotype_caller` entry once its `showcase_module` is populated in a follow-up.
4. **Bundle availability reporting**: `list_bundles()` returns every seeded bundle with an `available` flag and `reasons` list. A bundle whose tool-DB path is deliberately removed appears with `available=False` and a human-readable reason, without crashing the server or affecting other bundles. `load_bundle()` of an available bundle returns `supported=True` with typed bindings/inputs/images/tool_databases; of an unavailable bundle returns `supported=False` with the same reasons surfaced.
5. **`run_task`**: `run_task("exonerate_align_chunk", bindings=load_bundle("protein_evidence_demo")["bindings"], inputs={"exonerate_model":"protein2genome"})` writes `.runtime/specs/<id>.json` with `source_prompt` captured, executes, and returns a `run_record_path` that exists.
6. **`run_workflow`**: `run_workflow("transcript_evidence_generation", inputs={...})` with local profile produces a frozen recipe + run record.
7. **Slurm render + offline staging**: `run_workflow(..., execution_profile="slurm", resources={...})` writes the sbatch script, directives match. `check_offline_staging` blocks submission when a container path, tool-DB path, or resolved input path is missing or outside `shared_fs_roots`; findings appear in the MCP reply as structured limitations.
8. **`validate_run_recipe`**: pointed at a freshly frozen recipe, returns `supported=True` with empty findings. Pointed at a recipe whose container path is then removed, returns `supported=False` with a `container` finding naming the missing path.
9. **Cross-run reuse**: `run_workflow(..., bindings={"AnnotationGff": {"$ref": {"run_id": "<prior>", "output_name": "annotation_gff"}}})` resolves through the durable asset index, freezes the concrete path into the new recipe, and runs. A bad `$ref` returns a typed decline listing the offending run_id.
10. **`source_prompt` warning**: `run_task(..., source_prompt="")` succeeds but includes the empty-prompt advisory in `limitations`.
11. **Decline-to-bundles**: `run_workflow("braker3_annotation_workflow", inputs={})` returns `suggested_bundles` containing `braker3_small_eukaryote` and a `next_steps` entry.
12. **Resource-hint handoff docs**: `list_entries(category="workflow")` descriptions and `run_workflow` tool description both mention that `queue` and `account` must be user-supplied.
13. **Approval gate preserved**: a planner-composed multi-stage DAG via `prepare_run_recipe` still produces `requires_user_approval=True` and blocks until `approve_composed_recipe`. Registered entrypoints via `run_task` / `run_workflow` auto-approve.
14. **Extensibility test**: a synthetic `_testfamily.py` entry (added via a test fixture) surfaces through `list_entries(pipeline_family="testfamily")` and runs through `run_workflow` without any MCP-layer edits.
15. **Full suite**: `pytest tests/` holds at previous green count (~495 + 1 skipped) minus tests retired with the heuristics plus new tests for staging / validate / $ref / decline-to-bundles / empty-prompt.
16. **Call-site sweep**: `rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/` — no hits use the old flat `inputs=` shape.
17. **Agent context sweep**: `rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md` → zero stale references.
18. **Server boots from any data/ state**: `python -c "import flytetest.server"` succeeds regardless of whether every seeded bundle's backing data is present. Bundles with missing backing data surface as `available: false` through `list_bundles()` rather than blocking startup or an unrelated `run_task` call.
19. **`run_workflow` symmetry**: a bundle's full return value (`bindings`, `inputs`, `runtime_images`, `tool_databases`) spreads cleanly into both `run_task` and `run_workflow` via `**bundle`. A workflow call that provides typed `bindings` resolves them the same way as a task call.
20. **Broad decline next_steps**: a `run_workflow` decline with missing evidence surfaces all three of `suggested_bundles` (available-only), `suggested_prior_runs` (from the durable asset index), and `next_steps` (human-readable strings).
21. **Stable named outputs**: `run_workflow("gatk_haplotype_caller", ...)` returns `outputs: {"results_dir": "/abs/..."}` — keys match the registry's declared `InterfaceField.name` list. A registered output declared but not produced at runtime surfaces as an empty string plus a `limitations` advisory. `output_paths` is not present on any reply.
22. **Expanded `execution_defaults`**: an entry whose `execution_defaults` includes `runtime_images`, `module_loads`, `env_vars`, or `tool_databases` sees those values flow into a run without the scientist passing them; an explicit kwarg on `run_task`/`run_workflow` overrides the entry default; the resolved environment appears in the frozen `WorkflowSpec`.

## Out of Scope

- Server-side LLM parsing (client-side NL chosen).
- Replacing the power-user `prepare_*` / `run_*_recipe` / `approve_composed_recipe` tools.
- Changes to composition fallback, approval-gate logic, Slurm lifecycle observability semantics (`classify_slurm_failure()`), or durable asset index on-disk shape.
- Lighting up GATK (separate milestone — this plan preserves extensibility; it does not implement variant calling).
- New fixture data; bundles curate existing files under `data/`.
- Metadata-keyed asset indexing (stargazer's CID model); flyteTest stays path-based with bundles + durable index for curation.
- Backwards-compatibility shim for the old M21 flat `inputs` shape — this is an intentional compatibility migration (DESIGN §8.7); `CHANGELOG.md` records it.
- **Moving `TASK_PARAMETERS` onto `RegistryCompatibilityMetadata`**. This is a known remaining coupling that prevents the "no MCP-layer edits required to add a new *task*" claim from being unconditional. Slated for an immediate follow-up milestone. The mechanical change: add `task_parameters: tuple[InterfaceField, ...] = ()` to `RegistryCompatibilityMetadata`; populate per-task entries in each `registry/_<family>.py`; replace the `TASK_PARAMETERS[task_name]` lookup in `_scalar_params_for_task` with a registry lookup; delete `TASK_PARAMETERS`. That milestone is out of scope here to keep the current diff focused on the surface reshape, bundle introduction, staging check, and documentation sweep.
- Standalone `environment_profiles.py` module. The same needs are served by expanded `execution_defaults` on the registry entry (§3c); a parallel catalog would create two sources of truth for environment metadata.
- Manifest-backed bundle file format (JSON/YAML instead of Python literals). Deferred — Python literals stay reviewable in PRs and type-checkable at import; a format migration can land later if bundle count grows substantially.

---

## Audience-targeted derivative documents

Two condensed versions of this plan are produced as deliverables of the *planning* step (not the implementation step). On approval of this plan, the implementer copies the two sections below verbatim into the project root as `IMPLEMENTATION_PLAN.md` (coding-agent view) and `SCIENTIST_GUIDE.md` (scientist view). The master plan at `/home/rmeht/.claude/plans/replicated-growing-cookie.md` remains the canonical reference; the two derivatives serve as audience-tuned entry points.

---

### File 1 — `IMPLEMENTATION_PLAN.md` (coding-agent view)

Copy the content between the `<<<BEGIN>>>` / `<<<END>>>` markers into `/home/rmeht/Projects/flyteTest/IMPLEMENTATION_PLAN.md`.

<<<BEGIN IMPLEMENTATION_PLAN.md>>>

# MCP Surface Reshape — Implementation Plan

Master plan: `/home/rmeht/.claude/plans/replicated-growing-cookie.md`. This document is the implementer's checklist.

## Goal

Replace the brittle prose-parsing MCP surface with a typed "experiment loop" (`list_entries` → `list_bundles` → `load_bundle` → `run_task`/`run_workflow`), preserving flyteTest's four DESIGN pillars (typed biological contracts, frozen run recipes with `source_prompt`, pipeline-family stage order, offline-HPC staging). Hard-break the M21 flat `inputs` shape on `run_task` / `run_workflow` as an intentional coordinated migration (DESIGN §8.7).

## Ordered commits

Each bullet is intended as one atomic commit with a descriptive subject. Run `python -m compileall` on touched files + the relevant focused tests before each commit.

1. **Registry payload widening.** `server.py::_entry_payload` returns `pipeline_family`, `pipeline_stage_order`, `biological_stage`, `accepted_planner_types`, `produced_planner_types`, `supported_execution_profiles`, `slurm_resource_hints`, `local_resource_defaults`, full `inputs` + `outputs` InterfaceField lists, and the full `execution_defaults` dict (including any new runtime-image / tool-DB / module-loads / env-vars keys). Add `pipeline_family` cosmetic filter. Return only entries with non-empty `showcase_module`. Tests: category filter, pipeline_family filter, non-showcased exclusion.

2. **New module `src/flytetest/bundles.py`.** `ResourceBundle` dataclass with fields `name, description, pipeline_family, bindings, inputs, runtime_images, tool_databases, applies_to`. `BundleAvailability` dataclass. `_check_bundle_availability(b)` returns structured availability without raising. `list_bundles(pipeline_family=None)` returns all bundles with `available` flag and `reasons`. `load_bundle(name)` returns `supported=True` payload or `supported=False` with reasons; raises `KeyError` only for unknown names. **No module-level validation call.** Seed with bundles for existing fixtures under `data/` — audit first, drop any whose backing data is absent. Tests: listing with mixed availability, loading available and unavailable bundles, startup robustness with broken fixture.

3. **New module `src/flytetest/staging.py`.** `StagingFinding` dataclass, `check_offline_staging(artifact, shared_fs_roots)` walks `artifact.runtime_images`, `artifact.tool_databases`, `artifact.resolved_input_paths` and returns findings. `local` profile skips shared-fs check but verifies existence; `slurm` profile enforces both. Tests: missing container, missing tool DB, path outside shared_fs_roots.

4. **`WorkflowSpec` grows `tool_databases: dict[str, str]`.** Update `spec_artifacts.py`; `artifact_from_typed_plan` wires from plan; `save_workflow_spec_artifact` + `load_workflow_spec_artifact` serialize round-trip; existing frozen artifacts on disk continue to load with an empty dict default (read-path backward compat, since we never modify frozen artifacts per AGENTS.md hard constraint). Tests: round-trip with and without the field.

5. **Expand `execution_defaults` schema.** Document four optional keys on `RegistryCompatibilityMetadata.execution_defaults`: `runtime_images: dict[str, str]`, `module_loads: tuple[str, ...]`, `env_vars: dict[str, str]`, `tool_databases: dict[str, str]`. Populate on existing entries where appropriate (BRAKER3 annotation, BUSCO QC). Add resolution order in `plan_typed_request`: entry defaults → bundle fields → explicit kwargs. Tests: entry-only defaults, bundle override, kwarg override, all layered together; resolved environment frozen into `WorkflowSpec`.

6. **`_materialize_bindings` binding-value grammar.** `resolver.py::_materialize_bindings` dispatches on three mutually-exclusive forms inside each binding dict: raw path (existing), `$manifest` (existing), `$ref` (new — reads `durable_asset_index.json` via `LocalManifestAssetResolver.resolve(..., durable_index=...)`). All three lower to the same concrete planner dataclass, and the resolved concrete path is what gets frozen into the `WorkflowSpec`. Tests: raw form, `$manifest` form, `$ref` form, unknown run_id decline, missing output_name decline, ambiguous resolution decline.

7. **Reshape `run_task`** at `server.py:995`. New signature: `(task_name, bindings=None, inputs=None, resources=None, execution_profile="local", runtime_images=None, tool_databases=None, source_prompt="")`. Validate bindings against `entry.compatibility.accepted_planner_types`. Derive scalars via `_scalar_params_for_task(task_name, bindings)`. Call `plan_typed_request`; freeze via `artifact_from_typed_plan` + `save_workflow_spec_artifact`; dispatch via `LocalWorkflowSpecExecutor` / `SlurmWorkflowSpecExecutor`. Return `outputs: dict` (not `output_paths`) via `_collect_named_outputs(entry, run_record_path)`. Empty `source_prompt` appends advisory to `limitations`. Tests: bundle spread, unknown bindings decline, missing scalar decline, freeze happens, outputs dict keyed by registry.

8. **Reshape `run_workflow`** at `server.py:869` — symmetric signature to `run_task` including `bindings` and `tool_databases`. Preserve the BRAKER3 evidence-check limitation, reworded to accept either scalar-path inputs OR typed `ReadSet` / `ProteinEvidenceSet` bindings. Tests: bundle spread, symmetric call with `run_task`, named outputs.

9. **Staging preflight wired into Slurm submit.** `SlurmWorkflowSpecExecutor.submit` calls `check_offline_staging(artifact, shared_fs_roots)` before `sbatch`; non-empty findings short-circuit with structured `limitations` and a decline reply — no `sbatch` call made. `classify_slurm_failure()` untouched. Tests: missing container blocks submit; missing tool-DB blocks submit; all-present path proceeds.

10. **Add `validate_run_recipe` MCP tool.** Takes `artifact_path`, `execution_profile`, optional `shared_fs_roots`. Loads the artifact, resolves every binding through `LocalManifestAssetResolver` (catching exceptions as findings), runs `check_offline_staging`, returns `{"supported": bool, "recipe_id": ..., "findings": [...]}`. Register in `create_mcp_server()`. Tests: clean recipe passes, missing binding fails, missing container fails.

11. **Structured decline routing.** `_limitation_reply` / `_unsupported_target_reply` populate `suggested_bundles` (filtering out unavailable bundles via `_check_bundle_availability`), `suggested_prior_runs` (reads durable asset index for entries whose `produced_planner_types` match what the declined target accepts), and a human-readable `next_steps` list. Tests: decline for BRAKER3 with no inputs returns all three channels populated; decline with no available bundle returns only `next_steps`.

12. **Remove prose heuristics from `planning.py`.** Delete `_extract_prompt_paths`, `_extract_braker_workflow_inputs`, `_extract_protein_workflow_inputs`, `_extract_execution_profile`, `_extract_runtime_images`, `_classify_target`, M18 BUSCO keyword branch. `plan_typed_request` becomes structured-only with no prose parameter parsing. `plan_request` tool returns a structured decline pointing at `list_entries` / `list_bundles` / `run_task` / `run_workflow` rather than attempting prose parsing. `_try_composition_fallback` preserved unchanged. Tests: previously prose-parsed flows now either work via structured calls or decline cleanly.

13. **Call-site sweep.** `rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/` — every hit is a call-site review. Update test fixtures, smoke scripts, `docs/mcp_showcase.md`, `docs/tutorial_context.md`, any active milestone planning docs that quote the old flat `inputs=` shape. Acceptance: green CI with no uses of the old shape.

14. **MCP contract and tool descriptions.** `mcp_contract.py`: reframe around the experiment loop; add a one-sentence note to `run_task`/`run_workflow`/`run_slurm_recipe` descriptions that `queue` and `account` must be user-supplied (DESIGN §7.5); mark `prepare_run_recipe` / `run_local_recipe` / `run_slurm_recipe` / `approve_composed_recipe` as inspect-before-execute power-user tools. Tests: MCP schema reflects new signatures.

15. **Documentation + agent-context refresh.** Update in the same branch:
    - `AGENTS.md` — add `bundles.py`, `staging.py`, `validate_run_recipe`, binding-grammar to Project Structure; note experiment loop in Prompt/MCP/Slurm; note staging preflight invariant.
    - `DESIGN.md` — update §6.2 (MCP tool surface list), §7.5 (preflight staging check by name), opening (family extensibility claim, with the `TASK_PARAMETERS` coupling called out honestly).
    - `CHANGELOG.md` — dated entry covering all of the above including the BC break and the two audience-targeted derivative docs.
    - `.codex/registry.md` — "Adding a Pipeline Family" walkthrough; link `_gatk.py`.
    - `.codex/tasks.md` — bindings/inputs split; `TASK_PARAMETERS` still present as known coupling; follow-up pointer.
    - `.codex/workflows.md` — workflows accept bindings via the symmetric shape.
    - `.codex/testing.md` — patterns for `$ref` resolution, staging findings, decline-to-bundles, empty-prompt advisory, availability reporting.
    - `.codex/code-review.md` — MCP-layer-branch-free checklist item.
    - `.codex/agent/{registry,task,workflow,test,code-review,architecture}.md` — mirror the above.
    - `docs/realtime_refactor_checklist.md` — tick closed items; archive superseded planning doc on completion.
    - `docs/mcp_showcase.md` — rewrite as the experiment loop; `prepare_run_recipe` moves to an Inspect-Before-Execute appendix.
    - `docs/tutorial_context.md` — typed-binding prompt templates; `$ref` cross-run reuse example.
    - Grep-sweep verification: `rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md` → zero stale references.

16. **Copy this file and `SCIENTIST_GUIDE.md`** into the project root at `/home/rmeht/Projects/flyteTest/`. Commit separately with a descriptive subject.

## Hard constraints (never violate)

- Do not modify frozen saved artifacts at retry/replay time (AGENTS.md).
- Do not submit a Slurm job without a frozen run record.
- Do not change `classify_slurm_failure()` semantics without a decision record.
- Do not silently rewrite the baseline; only change what this task requires.
- Preserve the M15 P2 approval gate: `requires_user_approval` must remain set for planner-composed novel DAGs; only registered single-entry targets via `run_task` / `run_workflow` bypass it.

## Pitfalls

- Don't reintroduce prose parsing in the decline-to-bundles router. `suggested_bundles` / `suggested_prior_runs` are structured queries, not keyword matches.
- Don't make `_validate_bundles()` a module-level call. Call-site validation only (`list_bundles`, `load_bundle`). Startup must succeed regardless of `data/` state.
- Don't introduce a parallel `environment_profiles.py` catalog. Environment metadata lives on `RegistryCompatibilityMetadata.execution_defaults`; bundles inherit from and override it.
- Don't keep `output_paths` as a transitional alias. The BC break covers it too.
- Don't expand `TASK_PARAMETERS` in this milestone if it can be avoided; the follow-up moves the whole table onto the registry.

## Verification commands (run before merge)

```
python -m compileall src/flytetest/
rg -n "_extract_prompt_paths|_extract_braker_workflow_inputs|_extract_protein_workflow_inputs|_classify_target|_extract_execution_profile|_extract_runtime_images" src/flytetest/   # zero hits
rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/                                                                                                                                      # zero old-shape hits
rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md                                                            # zero stale refs
python -c "import flytetest.server"                                                                                                                                                                  # startup robust
pytest tests/                                                                                                                                                                                        # full suite green
```

<<<END IMPLEMENTATION_PLAN.md>>>

---

### File 2 — `SCIENTIST_GUIDE.md` (scientific-user view)

Copy the content between the `<<<BEGIN>>>` / `<<<END>>>` markers into `/home/rmeht/Projects/flyteTest/SCIENTIST_GUIDE.md`.

<<<BEGIN SCIENTIST_GUIDE.md>>>

# FlyteTest MCP — What's Changing for You

A practical guide for biologists driving FlyteTest through an MCP-aware client (Claude Code, an IDE assistant, etc.). This document describes the scientist-facing experience after the MCP surface reshape. For the implementation-level plan, see `IMPLEMENTATION_PLAN.md`.

## TL;DR

- **Four-step experiment loop replaces the old "prepare → approve → run" dance.** You browse, pick a starter kit (or supply your own inputs), and run.
- **Bundles** are curated starter kits for common analyses (e.g. BRAKER3 on a small eukaryote, BUSCO protein QC). `load_bundle("braker3_small_eukaryote")` hands you everything you need.
- **Outputs from prior runs can feed the next run.** A `$ref` in place of a file path says "use the GFF from recipe `2026-04-16T12-00-00Z-abc123`." No more copy-pasting result paths.
- **Submit-time staging checks catch unreachable containers and tool DBs.** You find out in 30 seconds, not after a 2-hour queue wait.
- **You need to pass a `source_prompt`** containing your original plain-language question. This is the provenance field that gets frozen into the reproducibility recipe.

## The experiment loop (what you actually do)

### Step 1 — Browse what's available

```
list_entries(category="workflow", pipeline_family="annotation")
```

Returns every registered annotation workflow with its biological contract: what input types it accepts, what it produces, where it sits in the pipeline ("stage 2 of the annotation family"), and what HPC resources are sensible defaults. Filter by `pipeline_family` to ask "what's in variant_calling?" or "what's in postprocessing?"

You can also browse tasks:

```
list_entries(category="task", pipeline_family="annotation")
```

Tasks are single stages (e.g. one Exonerate chunk, one BUSCO run on a proteome) — useful when you're *tuning* a stage rather than running the whole pipeline.

### Step 2 — Grab a starter kit or supply your own inputs

```
list_bundles(pipeline_family="annotation")
```

Returns curated bundles with an `available` flag. A bundle whose backing data isn't on this machine shows `available: false` with a reason ("BUSCO lineage dir missing at data/busco/lineages/eukaryota_odb10") — you see exactly what to download.

For an available bundle:

```
bundle = load_bundle("braker3_small_eukaryote")
# returns {"bindings": {...typed inputs...},
#          "inputs": {"braker_species": "demo_species"},
#          "runtime_images": {"braker_sif": "...", "star_sif": "..."},
#          "tool_databases": {...},
#          "pipeline_family": "annotation", "description": "..."}
```

Spread it directly into the run tool. If you're using your own data, skip `load_bundle()` and pass `bindings` / `inputs` / `runtime_images` explicitly — the shape is the same.

### Step 3 — Run

**Workflow (full pipeline):**

```
run_workflow(
    "braker3_annotation_workflow",
    **bundle,
    source_prompt="Annotate the new P. tetraurelia assembly using RNA-seq from sample S5 and the Ciliophora protein set.",
)
```

**Task (single stage, for experimentation):**

```
run_task(
    "exonerate_align_chunk",
    bindings={"ReferenceGenome": {"fasta_path": "my_assembly.fa"},
              "ProteinEvidenceSet": {"protein_fasta_path": "my_proteins.fa"}},
    inputs={"exonerate_model": "protein2genome"},
    source_prompt="Tune Exonerate on a single chunk before scaling up.",
)
```

Both return:

```
{
    "supported": True,
    "recipe_id": "2026-04-17T14-22-05Z-abc123",   # save this; it reproduces the run later
    "run_record_path": "results/.../run_record.json",
    "artifact_path": ".runtime/specs/<recipe_id>.json",
    "execution_profile": "local",
    "outputs": {
        "annotation_gff": "/abs/path/to/annotation.gff3",
        "proteins_fasta": "/abs/path/to/proteins.fa",
    },
    "limitations": [],
}
```

**Outputs are named.** No more guessing which positional path is the GFF and which is the FASTA — the keys match what the registry entry declares.

### Step 4 — Check Slurm submissions before they burn queue time

Before `sbatch` is called on an HPC cluster, the server now checks that every container (.sif), tool database, and resolved input path lives on a compute-visible filesystem. If something is unreachable, you get a structured decline listing exactly what's missing — not a 2-hour queue wait followed by a node-side runtime error.

You can also run this check explicitly on any frozen recipe:

```
validate_run_recipe(artifact_path=".runtime/specs/<recipe_id>.json",
                    execution_profile="slurm",
                    shared_fs_roots=["/project/pi-account/", "/scratch/myuser/"])
```

## Reusing prior run outputs

The single best ergonomic improvement for iterative analyses is the `$ref` binding form. Instead of copy-pasting the GFF path from your last BRAKER3 run into your next BUSCO run, you reference it by `recipe_id`:

```
run_workflow(
    "busco_annotation_qc_workflow",
    bindings={
        "ReferenceGenome": {"fasta_path": "my_assembly.fa"},
        "AnnotationGff": {"$ref": {"run_id": "2026-04-16T12-00-00Z-abc123",
                                   "output_name": "annotation_gff"}},
    },
    inputs={"lineage_dataset": "eukaryota_odb10", "busco_mode": "proteins"},
    source_prompt="QC the BRAKER3 annotation from yesterday's run.",
)
```

The server resolves the reference through the durable asset index, freezes the concrete path into the new recipe, and runs. Your reproducibility artifact records the actual path — if the asset index changes later, your recipe still replays correctly.

You can mix forms inside one call: a raw-path `ReferenceGenome`, a `$ref`-based `AnnotationGff`, and a `$manifest`-resolved `ReadSet` are all valid simultaneously.

## When a run declines

Every decline comes with three recovery channels:

- **`suggested_bundles`** — available starter kits that would unblock this exact target.
- **`suggested_prior_runs`** — entries from your durable asset index whose outputs match what this target accepts. "You already have a BAM from last week; use `$ref`."
- **`next_steps`** — human-readable suggestions including reformulating the request, calling `list_available_bindings()` to find unbound workspace files, or switching to a different target.

You should rarely hit a dead-end decline; when you do, the reply tells you what to try next.

## What to do with your existing scripts

If you have client code calling the old `run_task(task_name, inputs={...})` or `run_workflow(workflow_name, inputs={...})` shape, it **will stop working** at this milestone. The coordinated migration is intentional (DESIGN §8.7) — no backwards-compatibility shim is provided. Update your scripts to:

- Pass typed biological inputs in `bindings` (keyed by planner-type name like `"ReferenceGenome"`, `"ReadSet"`, `"ProteinEvidenceSet"`) rather than mixing paths and scalars in one flat dict.
- Pass scalar knobs (species names, model choices, thresholds) in `inputs`.
- Pass HPC resources in `resources` with `queue` and `account` explicitly (the server will never invent these; registry hints are only defaults for cpu/memory/walltime).
- Always pass `source_prompt` — your original plain-language question. This is what makes the run traceable months later. An empty prompt is permitted but surfaces an advisory in the reply's `limitations`.
- Read outputs from `reply["outputs"]` (a name-keyed dict), not from the removed `reply["output_paths"]` list.

## When to use the power-user tools

The old `prepare_run_recipe` → `approve_composed_recipe` → `run_local_recipe` / `run_slurm_recipe` sequence still exists. It is now the "inspect-before-execute" path for planner-composed novel DAGs (multi-stage compositions that don't correspond to a single registered workflow). For every registered workflow entry — BRAKER3, BUSCO, Exonerate, etc. — use `run_workflow` directly; the freeze step happens transparently and no explicit approval is required.

## Things you no longer need to do

- Manage `artifact_path` strings between tool calls — `run_task` / `run_workflow` freeze internally and return a `recipe_id`.
- Remember which positional index in an output list is the GVCF vs. the TBI — outputs are named.
- Copy-paste a result path from one run into the next — use `$ref`.
- Discover a BUSCO lineage download is missing only after a 2-hour Slurm wait — staging preflight catches it before submission.
- Remember that BRAKER3 wants a BAM for RNA-seq evidence and a FASTA for protein evidence — bundles package these for you.

<<<END SCIENTIST_GUIDE.md>>>

---

## Plan completion: file copies

On plan approval, the implementer extracts the two sections above and writes them to the project root:

- `/home/rmeht/Projects/flyteTest/IMPLEMENTATION_PLAN.md` — coding-agent view
- `/home/rmeht/Projects/flyteTest/SCIENTIST_GUIDE.md` — scientist-user view

Both documents are also referenced from `CHANGELOG.md` in the milestone entry, and from `docs/mcp_showcase.md` at the top of the rewritten walkthrough so scientists land on the guide first.
