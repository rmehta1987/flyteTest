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

**Ground truth today.** Every task writes a `run_manifest.json` to its result directory (helper in `manifest_io.py::write_json`, example in `tasks/functional.py:175-196`) with shape:

```json
{
  "stage": "busco_assess_proteins",
  "assumptions": [...],
  "inputs": {"proteins_fasta": "...", ...},
  "outputs": {
    "run_dir": "...",
    "short_summary": "...",
    "full_table": "...",
    "summary_notation": "C:95.7%[S:93.5%,D:2.2%]..."
  }
}
```

Only `manifest["outputs"]` is relevant here. The other top-level keys (`stage`, `assumptions`, `inputs`) are audit trail — they exist for reproducibility and do not surface in MCP replies. Currently `manifest["outputs"]` keys drift from `registry.outputs[*].name` for several tasks (e.g. BUSCO's registry declares `results_dir` while the manifest carries `run_dir`, `short_summary`, `full_table`, `summary_notation`). Today this drift is benign because `_collect_workflow_output_paths` (`server.py:678`) harvests paths positionally and returns `output_paths: list[str]`. §3b changes that by making the name-correspondence load-bearing.

**Design — registry is the public contract; manifest may carry internal extras.** The registry defines the public subset of outputs that scientists see; the manifest is free to carry additional internal audit data (debug scalars, intermediate-file pointers) without polluting the scientist-facing reply. `_collect_named_outputs` projects `manifest["outputs"]` onto the registry's declared names; undeclared manifest keys are silently omitted (they remain on disk in the manifest for audit). `InterfaceField` grows an optional `required: bool = True` flag so conditional outputs (e.g. GATK's `tbi_path` when `emit_ref_confidence != GVCF`) can surface as soft advisories rather than noisy warnings.

**Strictness rules:**

| Case | Reply behavior |
|---|---|
| Declared output produced in manifest | `outputs[field.name] = value` |
| Declared `required=True` output absent from manifest | `outputs[field.name] = ""`; **prominent** advisory in `limitations` ("required output X not produced; the task may not have completed") |
| Declared `required=False` output absent from manifest | `outputs[field.name] = ""`; **soft** advisory in `limitations` ("optional output Y not produced; may be expected depending on inputs") |
| Manifest key not declared on entry | Silently omitted from reply; remains in `manifest["outputs"]` on disk |
| Malformed input (manifest missing, JSON parse error) | Raises |

No raise path from registry/manifest drift — the projection is total. Raises are reserved for genuinely malformed data that blocks the projection.

New helper in `server.py`:

```python
def _collect_named_outputs(
    entry: RegistryEntry,
    run_record_path: Path,
) -> tuple[dict[str, str], list[str]]:
    """Project a task's run_manifest.json onto the registry-declared outputs.

    Registry is the source of truth for the public output surface. Extra keys
    in manifest["outputs"] (internal audit data like BUSCO's summary_notation)
    are silently omitted — they remain on disk for auditability but don't
    surface in the scientist-facing reply.

    Returns:
        (outputs, limitations). `outputs` is keyed by entry.outputs[*].name;
        missing declared outputs appear with an empty-string value and an
        advisory is appended to `limitations` (prominence depends on
        InterfaceField.required).
    """
    run_record = json.loads(run_record_path.read_text())
    manifest_path = Path(run_record["result_manifest"])
    manifest = json.loads(manifest_path.read_text())
    produced = manifest.get("outputs", {})

    outputs: dict[str, str] = {}
    limitations: list[str] = []
    for field in entry.outputs:
        value = produced.get(field.name)
        if value in (None, ""):
            outputs[field.name] = ""
            if getattr(field, "required", True):
                limitations.append(
                    f"Required output '{field.name}' was not produced by "
                    f"{entry.name}; the task may not have completed successfully."
                )
            else:
                limitations.append(
                    f"Optional output '{field.name}' was not produced by "
                    f"{entry.name}; this may be expected depending on inputs."
                )
        else:
            outputs[field.name] = str(value)
    return outputs, limitations
```

Reply shape becomes (for a GATK-style run with optional TBI skipped):

```python
{
    "supported": True,
    "workflow_name": "gatk_haplotype_caller",
    "recipe_id": "2026-04-17T14-22-05Z-abc123",
    "run_record_path": "results/gatk/2026-04-17T14-22-05Z-abc123/run_record.json",
    "artifact_path": ".runtime/specs/2026-04-17T14-22-05Z-abc123.json",
    "execution_profile": "slurm",
    "outputs": {
        "gvcf_path": "/project/.../NA12878.g.vcf.gz",
        "tbi_path": "",
    },
    "limitations": [
        "Optional output 'tbi_path' was not produced by gatk_haplotype_caller; "
        "this may be expected depending on inputs.",
    ],
}
```

**Registry-manifest name alignment sweep.** Most existing tasks' manifests already use sensible names; the sweep touches only places where `registry.outputs[*].name` and `manifest["outputs"]` keys diverge. Per-task decision: either rename the manifest key or update the registry declaration, with the registry typically being the stale side. Most diff lives in `src/flytetest/registry/_<family>.py`.

**`MANIFEST_OUTPUT_KEYS` convention + contract test.** Each task module exports a `MANIFEST_OUTPUT_KEYS: tuple[str, ...]` constant listing the keys its manifest will contain under `outputs`. A single registry-wide test at `tests/test_registry_manifest_contract.py` asserts, for every showcased entry, that every declared output name is a member of the task module's `MANIFEST_OUTPUT_KEYS`:

```python
def test_every_declared_output_is_a_declared_manifest_key():
    for entry in REGISTRY_ENTRIES:
        if not entry.showcase_module:
            continue
        task_module = importlib.import_module(entry.showcase_module)
        manifest_keys = set(getattr(task_module, "MANIFEST_OUTPUT_KEYS", ()))
        declared = {f.name for f in entry.outputs}
        missing = declared - manifest_keys
        assert not missing, (
            f"{entry.name}: declared outputs {sorted(missing)} are not "
            f"listed in {entry.showcase_module}.MANIFEST_OUTPUT_KEYS"
        )
```

This catches registry/manifest drift at CI time rather than scientist call time. Extras in `MANIFEST_OUTPUT_KEYS` that aren't declared on the registry entry are allowed (internal audit fields); missing declared names fail the test.

**`InterfaceField` change.** `registry/_types.py`:

```python
@dataclass(frozen=True)
class InterfaceField:
    name: str
    type: str
    description: str
    required: bool = True  # new; defaults preserve current behavior
```

All existing call sites (no `required` argument) continue to work unchanged. Only entries with conditional outputs need to set `required=False`.

**Commit sequence for §3b:**

1. Add `InterfaceField.required` default-True field (`registry/_types.py`). Tests: round-trip serialization, defaults preserved on existing entries.
2. Registry-manifest name alignment sweep. Reconcile every showcased task's `manifest["outputs"]` keys with its entry's `outputs[*].name`. One commit; most diff in `src/flytetest/registry/_<family>.py`.
3. Export `MANIFEST_OUTPUT_KEYS: tuple[str, ...]` on every task module in `src/flytetest/tasks/`. One commit, mechanical.
4. Add `tests/test_registry_manifest_contract.py` with the registry-wide assertion.
5. Implement `_collect_named_outputs` in `server.py` and wire into the reshaped `run_task` / `run_workflow` (this step is co-located with commits 7 & 8 in the ordered-commits list rather than a separate commit).

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

**Resolution order — deliberately narrow per-call override surface.** Only two of the four keys are overrideable per call. The other two are overrideable via bundle, and otherwise come from the registry entry. This is a deliberate narrowing: `module_loads` already has a per-call path via `resource_request.module_loads` (AGENTS.md §Prompt/MCP/Slurm), and exposing a second kwarg on `run_task`/`run_workflow` would create two sources of truth for the same cluster concern; `env_vars` is typically static per entry, and the bundle-level override covers the planned-variation case.

Per-key resolution:

| Key              | Entry default | Bundle override | Per-call kwarg | Resolved via |
|------------------|:-------------:|:---------------:|:--------------:|--------------|
| `runtime_images` | yes           | yes             | `runtime_images=` | entry → bundle → kwarg |
| `tool_databases` | yes           | yes             | `tool_databases=` | entry → bundle → kwarg |
| `module_loads`   | yes           | yes             | **no** — use `resources.module_loads` | entry → bundle → `resources.module_loads` |
| `env_vars`       | yes           | yes             | **no**                | entry → bundle |

All four values are frozen into the `WorkflowSpec` so replays are deterministic.

**Bundles inherit, not duplicate.** Bundles can now be much leaner: when the registered entry's defaults already name the BRAKER3+STAR containers, a `braker3_small_eukaryote` bundle lists only the scientist-facing inputs (genome, reads, protein evidence) and omits the container dict entirely. The bundle's `runtime_images` field becomes an *override* channel rather than a duplication. For one-off `env_vars` overrides outside a bundle, the scientist assembles a dict with the same shape a bundle returns and spreads it — there is no per-call kwarg.

**No new module.** The existing `RegistryCompatibilityMetadata` dataclass in `registry/_types.py` grows no new fields; the change is entirely in the documented schema of the existing `execution_defaults` dict and in the resolution code inside `plan_typed_request` / `artifact_from_typed_plan`. That keeps the B1–B4 registry-as-source-of-truth pillar intact without introducing a parallel catalog.

**Catalog surfacing.** `list_entries()` returns the entry's `execution_defaults` verbatim in its payload (the existing `_entry_payload` already exposes the `slurm_resource_hints` and `resources` keys; the new keys ride along on the same dict). Clients inspecting a workflow see its container and tool-DB requirements without reading registry code.

**`env_vars` is for non-secret tool configuration only.** Acceptable values are tool-config paths (`GATK_LOCAL_JAR`, `APPTAINER_BIND`, `TMPDIR`), threading knobs (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`), and cache directories — everything set here is frozen into the `WorkflowSpec` on disk and replayable by anyone with filesystem access, so it must not contain credentials.

Credentials — cluster authentication tokens, cloud API keys, database passwords — **do not belong in `env_vars`, bundles, or registry entries**. They live in the MCP server process's own environment (exported by the operator before starting the server) and are inherited automatically by the `sbatch` child process. Flytetest has no credential-management infrastructure today, and none is introduced by this milestone. If a future milestone brings real secrets (e.g. cloud API integration), it will introduce a dedicated credential channel outside the frozen-recipe path. Until then: this is a docstring rule, not a runtime guard. No denylist regex, no contract test — the smallest change that solves the actual problem.

### 3d. Typed reply dataclasses — one source of truth for the MCP wire format

**Why.** The reshaped run tools, `plan_request`, `validate_run_recipe`, and the decline-routing helpers together project a reply shape that is described in prose across §2, §3, §3b, §10, and §11. When four tools and two helpers all construct the same shape with ad-hoc dict literals, drift is inevitable — one call site returns `outputs` as a plural-keyed dict while another returns it singular-keyed, or `suggested_bundles` is a list of dicts here and a list of strings there. The coordinated BC break in this milestone (`output_paths` → `outputs`, new `suggested_bundles` / `suggested_prior_runs` / `next_steps` channels, new `recipe_id` / `run_record_path` / `artifact_path` trio) is already touching every caller; introducing typed replies in the same cutover means one migration instead of two.

**New module `src/flytetest/mcp_replies.py`:**

```python
"""Typed dataclasses for every MCP tool reply. One source of truth for the
wire format. `asdict()` at the tool boundary preserves JSON-compatibility
for FastMCP's client serialization.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Literal


@dataclass(frozen=True)
class SuggestedBundle:
    name: str
    description: str
    applies_to: tuple[str, ...]
    available: bool


@dataclass(frozen=True)
class SuggestedPriorRun:
    run_id: str
    produced_type: str
    output_name: str
    hint: str


@dataclass(frozen=True)
class RunReply:
    """Success reply from `run_task` / `run_workflow`."""
    supported: Literal[True]
    recipe_id: str
    run_record_path: str
    artifact_path: str
    execution_profile: Literal["local", "slurm"]
    outputs: dict[str, str]
    limitations: tuple[str, ...]
    # carries the target name under the appropriate key
    task_name: str = ""
    workflow_name: str = ""


@dataclass(frozen=True)
class PlanDecline:
    """Structured decline from any run tool, plan_request, or validate_run_recipe.

    Populated by `_limitation_reply` / `_unsupported_target_reply` (§11).
    """
    supported: Literal[False]
    target: str
    pipeline_family: str
    limitations: tuple[str, ...]
    suggested_bundles: tuple[SuggestedBundle, ...] = ()
    suggested_prior_runs: tuple[SuggestedPriorRun, ...] = ()
    next_steps: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanSuccess:
    """Plan preview reply from `plan_request` when structured match or
    composition fallback succeeds (§5, §3j)."""
    supported: Literal[True]
    target: str
    pipeline_family: str
    biological_goal: str
    requires_user_approval: bool  # True for composed novel DAGs (M15 P2)
    bindings: dict[str, dict]
    scalar_inputs: dict[str, object]
    composition_stages: tuple[str, ...]  # empty for single-entry; stage names for composed
    artifact_path: str                   # empty for single-entry; populated for composed (§3j)
    suggested_next_call: dict[str, object]  # {"tool": ..., "kwargs": {...}} (§3j)
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class BundleAvailabilityReply:
    """Per-entry shape returned by `list_bundles()`."""
    name: str
    description: str
    pipeline_family: str
    applies_to: tuple[str, ...]
    binding_types: tuple[str, ...]
    available: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ValidateRecipeReply:
    """Reply from `validate_run_recipe` (§11)."""
    supported: bool
    recipe_id: str
    execution_profile: Literal["local", "slurm"]
    findings: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class DryRunReply:
    """Preview reply from run_task / run_workflow when dry_run=True (§3i).

    Carries the fully-resolved state (concrete bindings, resolved environment,
    staging findings for slurm) without executor dispatch. The frozen artifact
    *is* written to disk so the scientist can chain run_slurm_recipe /
    run_local_recipe against it later without re-resolution.
    """
    supported: Literal[True]
    recipe_id: str
    artifact_path: str
    execution_profile: Literal["local", "slurm"]
    resolved_bindings: dict[str, dict[str, str]]
    resolved_environment: dict[str, object]
    staging_findings: tuple[dict[str, str], ...]
    limitations: tuple[str, ...]
    task_name: str = ""
    workflow_name: str = ""
```

**Construction and serialization.** Every tool and helper returns a typed instance; the FastMCP decorator layer (or a thin wrapper) calls `asdict()` at the boundary so the JSON wire shape is unchanged from Option A. `_limitation_reply` and `_unsupported_target_reply` in §11 return `PlanDecline` instances, not dicts.

**Test impact.** Existing tests that compare `reply["recipe_id"]` continue to work against `asdict()`-ed payloads. New tests construct expected replies as dataclass instances and compare; the type checker catches drift when a new field is added without touching every call site.

**Not in scope for this module.** Lifecycle-tool replies (`monitor_slurm_job`, `inspect_run_result`, `get_pipeline_status`, etc.) keep their current reply shapes — they're out of the current BC-break set and their dict shapes are already stable. Migrating them to typed replies is a trivial follow-up if the pattern proves out here.

### 3e. Operator-side logging — minimal, error-path only

**Why scoped so narrowly.** The repo has no internal logging convention today (only `slurm_monitor.py` instantiates a logger, and barely uses it). Observability has been deliberately centered on persistent structured state: frozen `WorkflowSpec` artifacts, run records on disk, slurm lifecycle tools (`monitor_slurm_job`, `fetch_job_log`, `inspect_run_result`, `get_run_summary`). A scientist's view into "what happened" is the MCP reply (§3d typed replies, §3b named outputs, §11 decline routing) and the disk-persisted run record; scientists do not read server stderr. Slurm *job-side* debugging remains entirely via the existing tools — Option B does not touch the sbatch stdout/stderr path, job-side manifests, `classify_slurm_failure`, or any lifecycle observability.

What Option B adds is narrow **operator-facing** signal at three sites where the MCP reply alone would otherwise leave a shared-deploy operator without a trail:

| Site | Level | Fields |
|---|---|---|
| Uncaught exception in `_materialize_bindings` / `artifact_from_typed_plan` / executor dispatch | `ERROR` | `recipe_id` (if already assigned), `tool_name`, exception type, traceback |
| `SlurmWorkflowSpecExecutor.submit` short-circuit from `check_offline_staging` (§8) | `INFO` | `recipe_id`, finding count, `shared_fs_roots` |
| `$ref` binding resolution failure in `_materialize_bindings` (§7) | `WARNING` | `recipe_id` (pending), offending `run_id`, `output_name`, reason |

**Convention.** `_LOG = logging.getLogger(__name__)` per module (matching the existing `slurm_monitor.py` pattern). No happy-path logs — the run record is the happy-path source of truth. No structured-event stream, no correlation IDs beyond `recipe_id`, no Grafana integration. Exception logs re-raise, not swallow. Tests assert log emission with `caplog` where behavior depends on it (e.g. the staging short-circuit test asserts both the INFO line and the absence of an `sbatch` call).

**Not in scope.** Happy-path event stream; per-tool entry/exit logs; tool-argument redaction beyond the secrets rule in §3c; log-format standardization across the whole project. These can land incrementally if operational needs emerge.

### 3f. `list_available_bindings` — additive `typed_bindings` field

**Why.** `list_available_bindings` (`server.py:2513-2582`) today returns a `bindings` dict keyed by scalar parameter names (from `TASK_PARAMETERS`), mixing file-list candidates with scalar-value hints in one shape. After the reshape, `run_task` / `run_workflow` accept `bindings` keyed by *planner-type* name (`ReferenceGenome`, `ReadSet`, ...) — not by scalar parameter name. Without alignment, a scientist would get a candidate file list from `list_available_bindings` and then have to hand-translate it into the planner-typed shape `run_task` expects. That translation defeats the purpose of a discovery helper.

**Additive change, no BC break.** The existing `bindings` field stays exactly as it is today. A new top-level `typed_bindings` field is added alongside, keyed by planner-type name, with inner dicts keyed by the planner dataclass's own `Path`-annotated field names:

```python
{
    "supported": True,
    "task_name": "exonerate_align_chunk",
    "search_root": "/home/user/...",
    "bindings": {  # existing — unchanged
        "genome": ["/abs/path/genome1.fa", ...],
        "exonerate_model": "(scalar — provide a string value, optional)",
    },
    "typed_bindings": {  # new
        "ReferenceGenome": {
            "fasta_path": ["/abs/path/genome1.fa", ...],
        },
        "ProteinEvidenceSet": {
            "protein_fasta_path": ["/abs/path/proteins1.fa", ...],
        },
    },
    "inputs": ["exonerate_model"],  # scalar knob names (non-binding)
    "limitations": [...]
}
```

Scientist usage:

```python
candidates = list_available_bindings("exonerate_align_chunk")
run_task("exonerate_align_chunk",
         bindings={t: {f: v[0] for f, v in fields.items()}
                   for t, fields in candidates["typed_bindings"].items()},
         inputs={"exonerate_model": "protein2genome"},
         source_prompt="...")
```

**Registry-derived, future-proof by construction.** Two registry-driven inputs, no hardcoding:

1. **Which type keys appear** — `entry.compatibility.accepted_planner_types` on the registered entry.
2. **Which field names appear inside each type** — the planner dataclass's own `Path`-annotated fields, discovered by a helper:

```python
def _path_fields_for(planner_type: type) -> tuple[str, ...]:
    """Return field names whose annotation is Path (or Path | None)."""
    hints = get_type_hints(planner_type)
    return tuple(
        name for name, hint in hints.items()
        if hint is Path or Path in get_args(hint)
    )
```

Why type-annotation-driven rather than `_path`-suffix convention: (a) no naming rule to enforce — a future `bam_dir: Path` field is picked up without a rename; (b) fails closed, not silently — a field mistakenly annotated as `str` simply doesn't surface, versus silently letting a string leak into the resolver; (c) no contract test needed — the registry-as-source-of-truth guarantee holds by construction.

When a future milestone lights up GATK (adding `AlignmentSet` and `VariantCallSet` planner types per the extensibility walkthrough), `list_available_bindings("gatk_haplotype_caller")` automatically emits `typed_bindings` keyed by those new type names with the correct inner field dicts — zero MCP-layer edits.

**Tests.** Existing tests asserting the current `bindings` shape keep passing (additive field). New tests: (a) `typed_bindings` keys equal `entry.compatibility.accepted_planner_types`; (b) inner field dicts match `_path_fields_for(planner_type)`; (c) a synthetic test family with a new planner type surfaces in `typed_bindings` without MCP-layer edits.

### 3g. Error surfacing — typed exceptions + exception-to-decline translation

**Why.** The reshaped run tools do six things in sequence — validate bindings, resolve `$ref`/`$manifest`, build typed plan, freeze artifact, dispatch executor, collect named outputs — and any step can raise. Without an explicit policy, scientists get opaque FastMCP 500 errors with no `recipe_id` to inspect and no `next_steps` to recover. The policy below keeps scientist-addressable failures in the typed-decline channel (§10) and reserves propagation for genuine infrastructure problems (logged per §3e).

**Three handling buckets, each with a defined policy:**

| Bucket | Examples | Policy |
|---|---|---|
| Pre-execute, scientist-addressable | `$ref` unknown run_id; `$manifest` path missing; raw-path missing; `$ref` output_name not in prior run | Convert to typed `PlanDecline` with exception-type-aware `next_steps` |
| Pre-execute, infrastructure | disk full on artifact write; permission denied; JSON parse error on durable index | Log ERROR per §3e, propagate to FastMCP |
| Execute, task-side | local subprocess non-zero exit; slurm job terminal failure | Reply with `supported=True, execution_status="failed"`; point at lifecycle tools |

**New module `src/flytetest/errors.py` — typed exception hierarchy:**

```python
"""Typed exception hierarchy for planner and resolver errors that should
surface as structured PlanDecline replies rather than FastMCP 500s.

Raising one of these types opts the failure into the exception-to-decline
translation layer in server.py::_execute_run_tool. Any other exception
propagates (and is logged by §3e).
"""

class PlannerResolutionError(Exception):
    """Base class for binding-resolution failures that are scientist-addressable."""

class UnknownRunIdError(PlannerResolutionError):
    def __init__(self, run_id: str, available_count: int):
        self.run_id = run_id
        self.available_count = available_count
        super().__init__(
            f"$ref run_id {run_id!r} not in durable asset index "
            f"({available_count} runs indexed)"
        )

class UnknownOutputNameError(PlannerResolutionError):
    def __init__(self, run_id: str, output_name: str, known_outputs: tuple[str, ...]):
        self.run_id = run_id
        self.output_name = output_name
        self.known_outputs = known_outputs
        super().__init__(
            f"$ref output_name {output_name!r} not in run {run_id!r}; "
            f"known outputs: {known_outputs}"
        )

class ManifestNotFoundError(PlannerResolutionError):
    """A $manifest path does not exist on disk."""

class BindingPathMissingError(PlannerResolutionError):
    """A raw-path binding points at a path that does not exist on disk."""
```

`resolver.py::_materialize_bindings` (§6) raises these instead of bare `KeyError` / `FileNotFoundError` so the tool-boundary catch can dispatch on type.

**Tool-boundary wrapper in `server.py`:**

```python
def _execute_run_tool(fn, *, target_name: str, pipeline_family: str) -> dict:
    """Run a reshaped run_task / run_workflow body; convert resolution
    failures into typed PlanDecline replies; let infrastructure failures
    propagate (logged per §3e).
    """
    try:
        return fn()
    except UnknownRunIdError as exc:
        return asdict(PlanDecline(
            supported=False, target=target_name, pipeline_family=pipeline_family,
            limitations=(str(exc),),
            next_steps=(
                "Call list_available_bindings(...) to confirm the run_id",
                "Or re-run the producing workflow to regenerate the output",
                "Or inspect .runtime/durable_asset_index.json",
            ),
        ))
    except UnknownOutputNameError as exc:
        return asdict(PlanDecline(
            supported=False, target=target_name, pipeline_family=pipeline_family,
            limitations=(str(exc),),
            next_steps=(
                f"Known outputs for run {exc.run_id}: {sorted(exc.known_outputs)}",
                "Pick one of those output names, or re-run the producing workflow",
            ),
        ))
    except (ManifestNotFoundError, BindingPathMissingError) as exc:
        return asdict(PlanDecline(
            supported=False, target=target_name, pipeline_family=pipeline_family,
            limitations=(str(exc),),
            next_steps=(
                "Call list_available_bindings(...) to locate substitute inputs",
                "Verify the path exists and is readable from this machine",
            ),
        ))
    # Infrastructure / unknown failures propagate — logged per §3e ERROR path.
```

**`RunReply` gets `execution_status` + `exit_status`** (update to §3d). Executor non-zero exit is not an MCP-layer failure — the request was understood, planned, frozen, and dispatched; the task failed. Scripts that care about task-side success check `execution_status`; scripts that care about MCP-layer success check `supported`.

```python
@dataclass(frozen=True)
class RunReply:
    supported: Literal[True]
    recipe_id: str
    run_record_path: str
    artifact_path: str
    execution_profile: Literal["local", "slurm"]
    execution_status: Literal["success", "failed"]  # new
    exit_status: int | None                          # new; None for slurm in-flight
    outputs: dict[str, str]
    limitations: tuple[str, ...]
    task_name: str = ""
    workflow_name: str = ""
```

On non-zero exit the reply carries a `limitations` advisory such as: *"Task exited with non-zero status (exit_status=2). Outputs may be partial. See run_record_path for stdout/stderr and run fetch_job_log / inspect_run_result for detail."* Local runs: `exit_status` from the run record. Slurm submit: `exit_status=None` (job hasn't terminated); `monitor_slurm_job` surfaces the terminal state later. Slurm terminal at reply time: populated. `classify_slurm_failure()` semantics untouched (hard constraint).

**Interaction with existing pieces:**

- **§3e logging**: typed-exception path does not log (it's an expected decline); only the re-raise path logs at ERROR. No double-logging.
- **§10 decline routing**: typed declines go through `_limitation_reply` / `_unsupported_target_reply`, which already populate `suggested_bundles` + `suggested_prior_runs`. The exception-to-`next_steps` map is additive — exception-specific strings merge into the generic recovery channels.
- **§11 `validate_run_recipe`**: also calls `LocalManifestAssetResolver`; typed resolver errors surface as `findings` entries rather than `PlanDecline` (same data, different container).

**Commit sequence for §3g:**

1. New module `src/flytetest/errors.py` with the typed exception hierarchy.
2. `resolver.py::_materialize_bindings` raises the typed exceptions instead of bare `KeyError` / `FileNotFoundError` (sub-task of §6's reshape).
3. `mcp_replies.py::RunReply` grows `execution_status` + `exit_status` fields.
4. `server.py::_execute_run_tool` wrapper + the exception-to-decline translations; wrap every reshaped `run_task` / `run_workflow` body in it.
5. Tests: each typed exception → corresponding decline shape with expected `next_steps`; local executor non-zero exit → `RunReply` with `execution_status="failed"` + correct `limitations` text; disk-full simulation → propagates (and is logged per §3e's ERROR assertion).

### 3h. `recipe_id` format — millisecond timestamp + target name, no hash

**Why.** Current format `<ISO-second>-<short-hash>` has two problems: (a) second-resolution collides under realistic concurrency (tight-loop submissions, parallel scatter patterns, retry automation) — two calls in the same second, same content, produce identical IDs that clobber each other's `.runtime/specs/<id>.json`; (b) `2026-04-17T14-22-05Z-abc123` tells you *when* but not *what*, so scientists grepping logs, inspecting `sacct` output, or running `ls .runtime/specs/` can't answer "what was this?" without opening the artifact.

**New format.** `<YYYYMMDDThhmmss.mmm>Z-<target_name>`

Example: `20260417T142205.123Z-braker3_annotation_workflow`

Length: 19 timestamp + 1 separator + up to ~30 target name ≈ **47 chars** for the longest current target. Still sortable chronologically (timestamp leads, ISO 8601 basic-format), self-describing in logs/ls/sacct output, filesystem-safe (registry names are already snake_case Python identifiers — no sanitization needed).

**Changes from the current format:**

| Change | Rationale |
|---|---|
| Millisecond subsecond (`.mmm`) | Prevents collision for realistic concurrency; 3 digits is plenty because MCP tool calls serialize through FastMCP's event loop — submissions inside the same millisecond are vanishingly rare. |
| Drop time colons (`142205` not `14-22-05`) | Standard ISO 8601 basic format. Saves 2 chars; still human-readable. |
| Drop the short hash | Uniqueness is now provided by the millisecond timestamp. The hash was a collision salt, not a content-addressed identity. If a future design wants content-addressed idempotency (same inputs → same ID for dedup), that's a separate stance to adopt — see §3h note below. |
| Embed `target_name` | Logs and `ls` become self-describing without needing path-layer grouping (which wouldn't help `sacct` or log-grep anyway). |

**Idempotency note (implementation-time check).** If the current short hash turns out to be content-addressed (deterministic from plan content) and any existing code relies on "same inputs → same recipe_id" — e.g. dedup or caching — the hash must be retained. Implementer should confirm at §3h commit time by reading `spec_artifacts.py::artifact_from_typed_plan`. If the hash is purely a uniqueness salt (which is our current understanding), dropping is lossless.

**Composition-fallback edge case.** Planner-composed novel DAGs from `_try_composition_fallback` don't have a single registered target. Use a sentinel: `composed-<first_stage>_to_<last_stage>` (e.g. `composed-star_align_rnaseq_to_braker3_annotate`) or simply `composed` if the stage names would make the ID unwieldy. No new logic — inherits from the existing composition-fallback path.

**Touch points.**

1. `spec_artifacts.py::artifact_from_typed_plan` — construct the new format string. Pull `target_name` from the plan; use `datetime.now(UTC).strftime(...)` with millisecond precision.
2. Filesystem paths stay `.runtime/specs/<recipe_id>.json` and `results/<recipe_id>/` — recipe_id already carries the target name, no second grouping layer needed.
3. Slurm job name — if `SlurmWorkflowSpecExecutor` sets `--job-name`, pass `recipe_id`. `sacct --format=JobName` becomes self-describing.
4. §3e log sites already emit `recipe_id`; target_name rides along for free.
5. Call-site sweep (§12) — any regex or string-split against the old format needs updating. Loose splits on `-` still work (timestamp has no internal dashes).
6. `validate_run_recipe` accepts recipe_id strings via `artifact_path`; that path still round-trips through `load_workflow_spec_artifact` unchanged.

**Tests.**

- Unit test on the ID generator: two calls inside the same millisecond produce distinct IDs (mock `datetime.now`) — or if implementer accepts the sub-millisecond collision as negligible, assert that distinct mock timestamps produce distinct IDs and document the millisecond-resolution guarantee.
- Format assertion: `run_task("exonerate_align_chunk", ...)` returns a `recipe_id` matching regex `^\d{8}T\d{6}\.\d{3}Z-exonerate_align_chunk$`.
- Filesystem round-trip: `.runtime/specs/<recipe_id>.json` exists after freeze; `load_workflow_spec_artifact(path)` returns an artifact whose `recipe_id` field matches.
- Composition sentinel: a planner-composed novel DAG produces a recipe_id with the `composed-` prefix.

### 3i. Dry-run flag — `dry_run=True` on `run_task` / `run_workflow`

**Why.** The reshaped run tools take a scientist from intent to execution in one call. Useful for production runs, but sometimes a scientist wants to *see* the frozen recipe and its resolved state before committing queue time — is the `$ref` resolving to the right prior run? Did the bundle override the container the scientist expected? For slurm: will the preflight staging check pass? Today's alternatives are either (a) power-user `prepare_run_recipe` → inspect `.runtime/specs/<id>.json` manually → `approve_composed_recipe` → `run_slurm_recipe`, or (b) just submit and see. `dry_run=True` gives a single-call preview that returns the fully-resolved state without dispatching the executor.

**What it does.** The run-tool body executes steps 1–5 of the six-step flow (validate bindings → resolve `$ref`/`$manifest`/raw-path → build typed plan → freeze artifact to disk → staging preflight for slurm) and skips step 6 (executor dispatch). The frozen artifact *is* written to disk — same code path as a real run — so the scientist can later chain `run_slurm_recipe(artifact_path=...)` or `run_local_recipe(artifact_path=...)` to execute the previewed recipe with zero re-resolution (no chance of input drift between preview and run).

**Reply shape — new `DryRunReply` dataclass in `mcp_replies.py` (§3d):**

```python
@dataclass(frozen=True)
class DryRunReply:
    """Preview reply from run_task / run_workflow when dry_run=True."""
    supported: Literal[True]
    recipe_id: str
    artifact_path: str
    execution_profile: Literal["local", "slurm"]
    resolved_bindings: dict[str, dict[str, str]]    # planner-type → field → concrete path
    resolved_environment: dict[str, object]          # runtime_images + tool_databases + module_loads + env_vars
    staging_findings: tuple[dict[str, str], ...]     # empty for local; populated for slurm preflight
    limitations: tuple[str, ...]
    task_name: str = ""
    workflow_name: str = ""
```

`resolved_bindings` and `resolved_environment` project directly from `WorkflowSpec` fields — no new computation, just exposure of state that was already frozen.

Example — a slurm dry-run for BUSCO with an m18 bundle:

```python
{
    "supported": True,
    "workflow_name": "busco_annotation_qc_workflow",
    "recipe_id": "20260420T091205.412Z-busco_annotation_qc_workflow",
    "artifact_path": ".runtime/specs/20260420T091205.412Z-busco_annotation_qc_workflow.json",
    "execution_profile": "slurm",
    "resolved_bindings": {
        "ReferenceGenome": {"fasta_path": "/project/data/busco/fixtures/genome.fa"},
    },
    "resolved_environment": {
        "runtime_images": {"busco_sif": "/project/data/images/busco_5.7.1.sif"},
        "tool_databases": {"busco_lineage_dir": "/project/data/busco/lineages/eukaryota_odb10"},
        "module_loads": ["python/3.11.9", "apptainer/1.4.1"],
        "env_vars": {},
    },
    "staging_findings": [],
    "limitations": [],
}
```

**Interaction with other pieces.**

- **§3g error paths**: resolution failures in dry_run → same typed `PlanDecline` as a real run. Staging failures → `DryRunReply` with populated `staging_findings` (not a decline — the scientist asked for a preview; findings *are* the preview). Infrastructure failures (disk full on freeze) → propagate + log per §3e.
- **§9 source_prompt empty-warning**: still appended to `limitations`.
- **§11 `validate_run_recipe`**: complementary, not redundant. `dry_run=True` creates a new artifact from fresh inputs; `validate_run_recipe` re-validates an artifact already on disk. Both tools keep valid use cases.
- **Approval gate (M15 P2)**: registered targets bypass approval in a real run and continue to do so in dry_run. Planner-composed novel DAGs (via `_try_composition_fallback`) produce `requires_user_approval=True` in the frozen artifact; a dry-run reply surfaces this as a `limitations` advisory so the scientist knows the subsequent execute step needs `approve_composed_recipe`.
- **`source_prompt`**: still captured in the frozen artifact regardless of dry_run. Audit trail retained even for preview-only flows.
- **`.runtime/specs/` accumulation**: dry-run artifacts that never execute stay in the directory. Cheap; existing gitignore covers it; no cleanup logic added.

**Default.** `dry_run=False`. Opt-in preview; typical call still executes.

**Commit sequence.**

1. Add `DryRunReply` dataclass to `mcp_replies.py`.
2. Add `dry_run: bool = False` kwarg to `run_task` and `run_workflow` signatures; branch after step 5 (staging) to either dispatch the executor (existing path) or return `DryRunReply` (new path).
3. Extract `resolved_bindings` + `resolved_environment` from the frozen `WorkflowSpec` into the reply. Projection of existing state, no new computation.
4. Tests: `dry_run=True` freezes but doesn't execute — `.runtime/specs/<id>.json` exists, no `run_record.json`; `resolved_bindings` keys match `accepted_planner_types`; slurm dry-run with missing container surfaces staging findings without calling `sbatch`; local dry-run with missing raw-path binding returns `PlanDecline` via the §3g translation; chained dry-run → `run_slurm_recipe(artifact_path=...)` executes the previewed recipe successfully.

### 3j. `plan_request` asymmetric freeze — NL preview without double-work

**Why.** `plan_request` is the free-text preview path: a scientist (or client-side LLM) hands over a plain-language goal, gets back a structured plan, and then decides whether to commit. After §5 strips prose heuristics, two routes survive:

1. **Single-entry match** — the goal resolves deterministically to one registered entry's `biological_stage` / `name`. The structured call the scientist would make next is fully known.
2. **Composition fallback** — `_try_composition_fallback` assembles a multi-stage DAG that doesn't correspond to a single registered entry. There is no single `run_task` / `run_workflow` call that expresses the plan; the only way to execute is via the power-user `run_local_recipe` / `run_slurm_recipe` tools against a frozen artifact.

These two cases want opposite freeze behavior:

| Case | Freeze? | Rationale |
|---|---|---|
| Single-entry | **No** | Scientist re-issues `run_workflow(...)` with structured kwargs. Freezing here + again at run time means two artifacts on disk for one intended execution; the first is orphaned. Let the freeze happen at run time when inputs are final. |
| Composed | **Yes** | Only way to hand the plan to `run_local_recipe` / `run_slurm_recipe` is via `artifact_path`. No alternative path. Freezing here is load-bearing, not redundant. |

**Reply shape — `PlanSuccess` grows two fields (update to §3d):**

```python
@dataclass(frozen=True)
class PlanSuccess:
    supported: Literal[True]
    target: str
    pipeline_family: str
    biological_goal: str
    requires_user_approval: bool                    # True for composed novel DAGs (M15 P2)
    bindings: dict[str, dict]                        # resolved typed bindings
    scalar_inputs: dict[str, object]
    composition_stages: tuple[str, ...]              # empty for single-entry; stage names for composed
    artifact_path: str                               # empty for single-entry; populated for composed
    suggested_next_call: dict[str, object]           # {"tool": ..., "kwargs": {...}}
    limitations: tuple[str, ...]
```

**Single-entry example** (BRAKER3 request with enough context to resolve bindings):

```python
{
    "supported": True,
    "target": "braker3_annotation_workflow",
    "pipeline_family": "annotation",
    "biological_goal": "Annotate small eukaryote with BRAKER3",
    "requires_user_approval": False,
    "bindings": {
        "ReferenceGenome": {"fasta_path": "data/braker3/reference/genome.fa"},
        "ReadSet": {"sample_id": "demo", "left_reads_path": "...", "right_reads_path": "..."},
    },
    "scalar_inputs": {"braker_species": "demo_species"},
    "composition_stages": (),
    "artifact_path": "",
    "suggested_next_call": {
        "tool": "run_workflow",
        "kwargs": {
            "workflow_name": "braker3_annotation_workflow",
            "bindings": {...},
            "inputs": {"braker_species": "demo_species"},
            "source_prompt": "<echo of the original NL ask>",
        },
    },
    "limitations": [],
}
```

**Composed example** (multi-stage DAG stitched by `_try_composition_fallback`):

```python
{
    "supported": True,
    "target": "composed-star_align_rnaseq_to_braker3_annotate",
    "pipeline_family": "annotation",
    "biological_goal": "Align RNA-seq then run BRAKER3",
    "requires_user_approval": True,
    "bindings": {...},
    "scalar_inputs": {...},
    "composition_stages": ("star_align_rnaseq", "braker3_annotate"),
    "artifact_path": ".runtime/specs/20260417T142205.123Z-composed-star_align_rnaseq_to_braker3_annotate.json",
    "suggested_next_call": {
        "tool": "approve_composed_recipe",
        "kwargs": {"artifact_path": ".runtime/specs/.../....json"},
    },
    "limitations": [
        "This is a planner-composed novel DAG; requires_user_approval=True. "
        "Call approve_composed_recipe(artifact_path=...) before run_local_recipe / run_slurm_recipe.",
    ],
}
```

**Decline shape.** When both structured match and composition fallback fail, `plan_request` returns the same `PlanDecline` shape from §3d with the three recovery channels from §10 (`suggested_bundles`, `suggested_prior_runs`, `next_steps`). No new shape.

**Interaction with other §3 pieces:**

| Tool | Input | Freezes? | Returns |
|---|---|---|---|
| `plan_request` (single-entry) | NL goal | No | `PlanSuccess` with structured kwargs in `suggested_next_call` |
| `plan_request` (composed) | NL goal | Yes | `PlanSuccess` with `artifact_path` populated |
| `run_task` / `run_workflow` (dry_run=True) | Structured | Yes | `DryRunReply` (§3i) — scientist has committed to specific inputs |
| `run_task` / `run_workflow` (dry_run=False) | Structured | Yes + executes | `RunReply` |
| `validate_run_recipe` | Existing `artifact_path` | No (re-reads) | `ValidateRecipeReply` |

The split is: `plan_request` is for *"what would I run?"*; dry-run is for *"what exactly does this call resolve to?"*; real run is for *"do it."* Each tool has a non-overlapping job.

**Approval gate.** Composed plans set `requires_user_approval=True` in the frozen artifact (M15 P2, unchanged). `plan_request` surfaces this as a `limitations` advisory pointing at `approve_composed_recipe` — same rule the execute path enforces, no new logic.

**Commit sequence.**

1. Extend `PlanSuccess` in `mcp_replies.py` with `artifact_path` and `suggested_next_call`.
2. In `planning.py::plan_typed_request` (or a thin wrapper the `plan_request` tool calls), branch on single-entry vs composed: single-entry fills `suggested_next_call` and leaves `artifact_path=""`; composed calls `artifact_from_typed_plan` + `save_workflow_spec_artifact` and fills both.
3. Update `plan_request` MCP tool body to return the new shape; preserve decline routing via `PlanDecline` + §10 channels.
4. Tests: single-entry NL goal → `artifact_path == ""` and no file on disk; `suggested_next_call["tool"] == "run_workflow"` with kwargs the scientist can copy-paste; composed NL goal → `artifact_path` populated, file exists on disk, `requires_user_approval=True`, `suggested_next_call["tool"] == "approve_composed_recipe"`; declining NL goal → `PlanDecline` with `suggested_bundles` populated.

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

`plan_request` (the free-text preview tool) **continues to attempt supported natural-language planning**; it only declines when no supported plan can be formed. What goes away is prose *extraction* (file paths, execution profiles, runtime images parsed out of free text); what remains is structured matching against registered entries. Specifically, `plan_request` still:

1. Accepts a `biological_goal` string — the scientist's plain-language ask.
2. Looks up candidate registered entries by structured match against each entry's `biological_stage` field and `name` (deterministic lookup, not keyword scoring).
3. Runs `_try_composition_fallback` on structured planning goals to assemble multi-stage DAGs when a single registered entry doesn't cover the goal.
4. Returns a plan preview (with `requires_user_approval` set for composed novel DAGs per M15 P2) when a match or composition succeeds.
5. Declines only when both structured match and composition fallback fail — returning the same three recovery channels defined in §10 (`suggested_bundles`, `suggested_prior_runs`, `next_steps`).

The net effect: prompts that the old heuristics *happened to handle* because of keyword luck now either work through structured matching, work through composition fallback, or decline cleanly with a concrete recovery path. No silent mis-parses.

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

**Additional items (from §3 extension design passes)**
- `README.md` — update "Current Status" section: note the experiment loop (`list_entries` → `list_bundles` → `load_bundle` → `run_task`/`run_workflow`) is the primary scientist entrypoint; `prepare_*` tools are inspect-before-execute power-user tools.
- `AGENTS.md` Project Structure — add `errors.py` (§3g typed exception hierarchy) and `mcp_replies.py` (§3d typed replies) alongside the `bundles.py` / `staging.py` entries.
- `.codex/agent/architecture.md` — add `mcp_replies.py` and `errors.py` to the MCP wire-format + error-translation layer description.
- `DESIGN.md` §6.2 / §7.5 — add a one-line note on the new `recipe_id` format (`<YYYYMMDDThhmmss.mmm>Z-<target_name>`, §3h) so downstream docs quoting it match.
- `CHANGELOG.md` — in the dated entry, add a short before/after migration example for the flat-`inputs` → `bindings`+`inputs` reshape so external callers adopting the cutover have a concrete diff to mimic.
- `docs/mcp_showcase.md` — add a short "Binding grammar" subsection (or a dedicated `docs/binding_grammar.md`) showing the three binding forms (raw path / `$manifest` / `$ref`) side-by-side with a short example each.

**Grep sweep for stale context clues**
`rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md` → every hit is a doc to update. Re-run after edits to confirm zero stale references.

### 15. Docstrings to update

Module and function docstrings must reflect the reshape — scientists calling `help(run_task)` or `inspect.getdoc(validate_run_recipe)` see docstrings, not plan prose.

- `server.py`:
  - `run_task`, `run_workflow` — new signatures + freeze semantics + `source_prompt` capture + `execution_status` / `exit_status` fields (§§2, 3, 3g).
  - `list_entries` — `pipeline_family` cosmetic filter (§1).
  - `list_bundles`, `load_bundle`, `validate_run_recipe` — new tools; docstrings define the wire format.
  - `_entry_payload` — widened fields (§1).
  - `_scalar_params_for_task` — derivation from `bindings` (§2 body).
  - `_collect_named_outputs` — projection semantics + required-vs-optional advisory shape (§3b).
  - `_execute_run_tool` — exception-to-decline translation policy (§3g).
  - `_limitation_reply`, `_unsupported_target_reply` — new `suggested_bundles` / `suggested_prior_runs` / `next_steps` channels (§10).
- `planning.py`:
  - `plan_typed_request` — now structured-only; drop references to prose extraction.
  - `plan_request` — structured matching + composition fallback; no prose extraction. Describes single-entry no-freeze vs. composed freeze (§3j).
- `mcp_contract.py` — module docstring adds a cross-reference to `mcp_replies.py` as the canonical reply-shape definition; tool-description strings reframed as the experiment loop (§6); `queue` / `account` handoff note on run tools.
- `bundles.py`, `staging.py`, `mcp_replies.py`, `errors.py` — module docstrings + per-symbol docstrings (most already drafted in §§3d / 3g / 4 / 8).
- `resolver.py::_materialize_bindings` — expanded to cover the three binding forms (§7).
- `spec_artifacts.py::artifact_from_typed_plan` — notes `tool_databases` / `runtime_images` resolution order (§3c) and new `recipe_id` format (§3h).
- `spec_executor.py::SlurmWorkflowSpecExecutor.submit` — notes preflight staging check + short-circuit on findings (§8).
- Task modules that export `MANIFEST_OUTPUT_KEYS` — brief line near the export explaining its role as the registry-manifest contract source (§3b).

### 16. Testing patterns (beyond per-commit test bullets)

- **Test-file layout** — one `tests/test_<module>.py` per new module (`bundles`, `staging`, `mcp_replies`, `errors`). Cross-cutting flows stay in `test_server.py` / `test_mcp_prompt_flows.py`.
- **Shared fixtures**:
  - `tmp_path`-rooted `durable_asset_index.json` with known entries for `$ref` resolution tests.
  - A `monkeypatch`-based `Path.exists` helper for bundle-availability tests so they don't need real files under `data/`.
  - A synthetic `tests/fixtures/_testfamily.py` registered via `importlib` for the extensibility test (see §Critical Files).
- **Heuristic-retirement bracket** — for each deleted helper (`_extract_prompt_paths`, `_extract_braker_workflow_inputs`, `_extract_protein_workflow_inputs`, `_classify_target`, `_extract_execution_profile`, `_extract_runtime_images`, M18 BUSCO keyword branch), find the tests that exercised its happy path; convert to the structured path or retire with a comment citing the deletion commit. Don't delete tests blindly — check the asserted behavior has a replacement in the structured path.
- **Contract test** (§3b) — `tests/test_registry_manifest_contract.py` asserts `entry.outputs[*].name ⊆ MANIFEST_OUTPUT_KEYS` for every showcased entry. Runs once per CI; fails on new registry outputs that skip the `MANIFEST_OUTPUT_KEYS` declaration.
- **Preflight staging test pattern** — `tmp_path` shared-FS root; a `WorkflowSpec` with parametrized container / tool-DB / input paths; monkeypatch the `sbatch` invocation to assert it is NOT called when findings are non-empty; assert it IS called when the happy-path resolves. Inspect the structured `limitations` in the decline reply.
- **Error-surfacing pattern** (§3g) — raise each `PlannerResolutionError` subclass inside `_materialize_bindings`; assert `_execute_run_tool` translates to the expected `PlanDecline` shape with the right `next_steps`; assert `OSError` (disk-full simulation on `save_workflow_spec_artifact`) propagates AND emits an ERROR log via `caplog`.
- **Dry-run chained test** (§3i) — `dry_run=True` → capture `artifact_path` → `run_slurm_recipe(artifact_path=...)` with a mocked `sbatch` → assert the artifact bytes are unchanged between the two calls (no re-resolution).
- **plan_request asymmetric-freeze test** (§3j) — single-entry NL goal asserts `artifact_path == ""` and no file appears in `.runtime/specs/`; composed NL goal asserts a file exists on disk + `requires_user_approval=True` + `suggested_next_call["tool"] == "approve_composed_recipe"`.
- **BC-break smoke** — a one-liner asserting the old flat-`inputs` shape on `run_task` is rejected with a clear `PlanDecline` (not a TypeError), so external migrations get an actionable signal.

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
21. **Stable named outputs**: `run_workflow("gatk_haplotype_caller", ...)` returns `outputs` keyed by the registry's declared `InterfaceField.name` list. A required output declared but not produced surfaces as an empty string plus a prominent `limitations` advisory; an optional output (`required=False`) surfaces as an empty string plus a soft advisory; an undeclared manifest key is silently omitted from the reply (remains in `manifest["outputs"]` on disk). `output_paths` is not present on any reply.
22. **Registry-manifest name alignment**: `tests/test_registry_manifest_contract.py` passes — every showcased entry's declared output names are members of its task module's `MANIFEST_OUTPUT_KEYS`. Introducing a new registry-declared output without updating `MANIFEST_OUTPUT_KEYS` fails the test.
23. **Expanded `execution_defaults`**: an entry whose `execution_defaults` includes `runtime_images`, `module_loads`, `env_vars`, or `tool_databases` sees those values flow into a run without the scientist passing them; an explicit kwarg on `run_task`/`run_workflow` overrides the entry default; the resolved environment appears in the frozen `WorkflowSpec`.
24. **Typed resolver errors**: a `$ref` with an unknown `run_id` returns a `PlanDecline` naming the offending `run_id` and listing the durable-index-lookup `next_steps`; a `$ref` with a valid `run_id` but unknown `output_name` returns a decline listing the run's known outputs; a `$manifest` path that does not exist returns a decline naming the path; a raw-path binding pointing at a missing file returns a decline. No exception propagates to FastMCP for any of these cases; §3e does not emit an ERROR log for them.
25. **Execution failure distinguishable from MCP failure**: a local task that exits non-zero returns `supported=True, execution_status="failed", exit_status=<code>` with partial `outputs` populated where the manifest captured them, plus a `limitations` advisory pointing at `run_record_path`, `fetch_job_log`, and `inspect_run_result`. A successful local run returns `execution_status="success", exit_status=0`. A slurm submission returns `execution_status="success", exit_status=None` at submit time (terminal state is surfaced later by `monitor_slurm_job`).
26. **Infrastructure failure propagates + logs**: a disk-full / permission-denied simulation on `save_workflow_spec_artifact` propagates (scientist sees a FastMCP error), and §3e emits an ERROR log line including the `tool_name` + exception type + traceback.
27. **recipe_id format**: `run_task("exonerate_align_chunk", ...)` returns a `recipe_id` matching `^\d{8}T\d{6}\.\d{3}Z-exonerate_align_chunk$`. `ls .runtime/specs/` shows self-describing filenames. Slurm `sacct --format=JobName` shows the same token. Planner-composed DAGs produce recipe_ids prefixed `composed-`. Two submissions in distinct milliseconds produce distinct recipe_ids; same-millisecond collision is documented as a negligible edge case given FastMCP's serialized event loop.
28. **Dry-run preview**: `run_task(..., dry_run=True)` returns a `DryRunReply` with the frozen `artifact_path` and the fully-resolved `resolved_bindings` + `resolved_environment`; no `run_record_path`, no `outputs`, no subprocess or `sbatch` call. A subsequent `run_slurm_recipe(artifact_path=...)` on that artifact executes the previewed recipe successfully with no re-resolution. A slurm dry-run for a workflow whose container image is unreachable surfaces the missing path in `staging_findings` without dispatching. A dry-run for a planner-composed novel DAG surfaces `requires_user_approval` as a `limitations` advisory.
29. **`plan_request` asymmetric freeze**: `plan_request(biological_goal="annotate small eukaryote with BRAKER3", ...)` that resolves to a single registered entry returns a `PlanSuccess` with `artifact_path=""`, `composition_stages=()`, and `suggested_next_call["tool"] == "run_workflow"` — no file written to `.runtime/specs/`. A request that only resolves via `_try_composition_fallback` returns a `PlanSuccess` with `artifact_path` populated (file exists on disk), `composition_stages` listing the assembled stages, `requires_user_approval=True`, and `suggested_next_call["tool"] == "approve_composed_recipe"`. A request that fails both structured match and composition fallback returns a `PlanDecline` with `suggested_bundles` / `suggested_prior_runs` / `next_steps` populated per §10.

## Out of Scope

- Server-side LLM parsing (client-side NL chosen).
- Replacing the power-user `prepare_*` / `run_*_recipe` / `approve_composed_recipe` tools.
- Changes to composition fallback, approval-gate logic, Slurm lifecycle observability semantics (`classify_slurm_failure()`), or durable asset index on-disk shape.
- Lighting up GATK (separate milestone — this plan preserves extensibility; it does not implement variant calling).
- New fixture data; bundles curate existing files under `data/`.
- Metadata-keyed asset indexing (stargazer's CID model); flyteTest stays path-based with bundles + durable index for curation.
- Backwards-compatibility shim for the old M21 flat `inputs` shape — this is an intentional compatibility migration (DESIGN §8.7); `CHANGELOG.md` records it.
- **Moving `TASK_PARAMETERS` onto `RegistryCompatibilityMetadata`** — a known remaining coupling, slated for an immediate follow-up milestone.

  **What it is today.** `TASK_PARAMETERS` is a hand-maintained dispatch table at `src/flytetest/server.py:125`, structured as `dict[str, tuple[tuple[str, bool], ...]]` — keyed by task name, with each value a tuple of `(param_name, required)` pairs listing the scalar MCP inputs that task accepts. Current entries cover `exonerate_align_chunk`, `busco_assess_proteins`, `fastqc`, and `gffread_proteins` (four tasks, ~15 param tuples total). `run_task` consults this table to validate the `inputs` dict sent over the MCP — rejecting unknown keys and flagging missing required ones before building the typed plan.

  **Why it's a coupling.** Adding a new *task* in a new pipeline family (say, a GATK `bqsr_recalibrate_bam` task) currently requires a one-line edit to `TASK_PARAMETERS` in addition to the family-local files (`registry/_<family>.py`, `tasks/<family>.py`, `planner_types.py`). That single-line edit lives in `server.py`, which is MCP-layer code. It therefore makes the "adding a new pipeline family touches only family-local files" claim conditionally false *for tasks* (it remains unconditionally true for workflows, because workflow entrypoints consume scalars from their own function signatures rather than through MCP-layer validation). Every scientist browsing the extensibility story has to learn this one exception.

  **Why it's mechanical to remove.** Every `TASK_PARAMETERS` entry is shape-equivalent to an `InterfaceField` tuple — both are `(name, ..., required?)` declarations about what a task accepts. The registry's `RegistryEntry.inputs: tuple[InterfaceField, ...]` already carries every input name + type + description for each task; the one piece missing from `InterfaceField` today is a boolean `required` flag (task docstrings indicate this informally). The follow-up introduces that flag (or a parallel `task_parameters: tuple[InterfaceField, ...]` field on `RegistryCompatibilityMetadata` if keeping `RegistryEntry.inputs` stable is preferred), populates per-task entries inside each `registry/_<family>.py` alongside the existing `InterfaceField('genome', 'File', '...')`-style declarations, replaces the `TASK_PARAMETERS[task_name]` lookup in `_scalar_params_for_task` with a registry-backed lookup, and deletes the `TASK_PARAMETERS` table. Net effect: task parameter validation still works identically, but the source of truth shifts from `server.py` to the family-local registry file — aligning tasks with the workflow story, and making the extensibility claim unconditional.

  **Why deferred.** Rolling this into the current milestone would add a fourth touch point to every family file (on top of the `runtime_images` / `tool_databases` / `module_loads` / `env_vars` schema population in §3c and the potential bundle entry), and would require re-exercising every existing task through the new validation path. The current diff is already sizeable (surface reshape, bundle introduction, staging preflight check, decline routing, documentation sweep). The follow-up is trivially mechanical and can land immediately after this milestone closes, at which point the "pipeline-family growth is a `registry/_<family>.py` + `planner_types.py` + `tasks/` + `workflows/` + optional `bundles.py` change, never an MCP-layer change" claim holds unconditionally for both tasks and workflows.
- Manifest-backed bundle file format (JSON/YAML instead of Python literals). Deferred — Python literals stay reviewable in PRs and type-checkable at import; a format migration can land later if bundle count grows substantially.
- **Reply-size caps for scatter-gather workloads.** Deferred follow-up. Most reply shapes are bounded by construction: `outputs` is bounded by `entry.outputs` (registry contract) since undeclared manifest keys are silently dropped per §3b Design C; `DryRunReply.resolved_bindings` / `resolved_environment` is bounded by `accepted_planner_types` × `Path`-annotated fields; scatter tasks dispatch one reply per chunk rather than aggregating. Two spots are bounded by the durable index or input set instead of the registry — (a) `suggested_prior_runs` in §10 decline channels reads the full durable index, (b) `ValidateRecipeReply.findings` can grow large for heavy-scatter workflows with hundreds of chunk inputs. When this becomes a real problem: cap `suggested_prior_runs` at 10 most recent matches with a `total_matches_count` field and a pointer at `list_available_bindings()` for full enumeration; leave `findings` uncapped (actionable) but add a `summary_counts: {"container": N, "tool_database": N, "input_path": N}` companion field.
