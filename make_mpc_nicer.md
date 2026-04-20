# Scientist-Centered MCP: Less Heuristic, More Natural, Family-Extensible

*Updated 2026-04-17: inline discussion notes are placed directly under the relevant proposal sections.*

## Context

FlyteTest's purpose (DESIGN.md opening) is to *"minimize the computational and engineering burden on scientists by enabling dynamic composition of bioinformatics pipelines from natural-language requests"* — grounded in four pillars:

1. **Typed biological contracts** — `ReferenceGenome`, `ReadSet`, `ProteinEvidenceSet`, and the M23–M26 generic result bundles — are the scientist's vocabulary.
2. **Frozen run recipes** (`WorkflowSpec` with `source_prompt` captured) — the reproducibility gate and audit artifact.
3. **Pipeline families with stage order** (`pipeline_family`, `pipeline_stage_order`) — the scientist's map: *"where am I in the pipeline and what is next."*
4. **Offline-compute HPC reality** — containers, tool databases, and inputs staged on compute-visible filesystems as a first-class constraint.

The current MCP feels command-line-ish: clients juggle `prepare_run_recipe` → `approve_composed_recipe` → `run_local_recipe`/`run_slurm_recipe` with `artifact_path` strings, and server-side keyword/regex heuristics in `planning.py` (`_extract_prompt_paths`, `_extract_braker_workflow_inputs`, `_extract_protein_workflow_inputs`, `_classify_target`, execution-profile/runtime-image regex, M18 BUSCO branch) try to extract typed plans from prose. These heuristics are brittle and duplicate what the client LLM already does better.

Two ideas borrowed from `../stargazer/` — a **task-vs-workflow split** at the MCP surface and **curated resource bundles** — translate flyteTest's strengths into a surface a biologist can use conversationally, without overwriting flyteTest's unique pillars.

**Updated discussion**

- Keep the scientist-centered framing and the emphasis on typed contracts, frozen recipes, and HPC constraints.
- Preserve `plan_request` and `prompt_and_run` as server-owned natural-language entrypoints in this milestone.
- Treat the task/workflow split and curated bundles as additive UX improvements on top of the current prompt-first contract, not as a handoff of interpretation responsibility to the client.

**Family extensibility is load-bearing.** The immediate test case is `src/flytetest/registry/_gatk.py` (added B5, 2026-04-16): a catalog-only `gatk_haplotype_caller` entry with `pipeline_family="variant_calling"`, `accepted_planner_types=("ReferenceGenome","AlignmentSet")`, `produced_planner_types=("VariantCallSet",)`, `showcase_module=""`. Neither `AlignmentSet` nor `VariantCallSet` exists in `planner_types.py` yet. When a future milestone wires GATK, it must not require touching `server.py`, `planning.py`, `mcp_contract.py`, or bundle-tool code. The plan explicitly preserves that extensibility.

**What already exists (do not reimplement):**

- `run_task` and `run_workflow` MCP tools (M21, 2026-04-15) at `server.py:995` and `:869`. Currently take a flat `inputs` dict and do not freeze. `TASK_PARAMETERS` dispatch at `server.py:125`.
- `list_entries(category=...)` on the registry (`registry/__init__.py:46`) — already filters by category. The **server-side** `list_entries` tool needs to use it and widen its response.
- Registry-as-source-of-truth (B1–B4). `RegistryEntry` carries `category`, `accepted_planner_types`, `produced_planner_types`, `pipeline_family`, `pipeline_stage_order`, `supported_execution_profiles`, `execution_defaults["slurm_resource_hints"]`.
- `_local_node_handlers()` and `SUPPORTED_TASK_NAMES` / `SUPPORTED_WORKFLOW_NAMES` derive automatically from `showcase_module`.
- Approval gating correctly scoped (M15 P2). `requires_user_approval` set only for planner-composed DAGs; registered entrypoints bypass.
- Freeze/execute infrastructure: `artifact_from_typed_plan`, `save_workflow_spec_artifact` (`spec_artifacts.py`); `LocalWorkflowSpecExecutor`, `SlurmWorkflowSpecExecutor` (`spec_executor.py`).
- Durable asset index (M20b): `DurableAssetRef` + `durable_asset_index.json`; `LocalManifestAssetResolver.resolve(durable_index=...)`.
- `_try_composition_fallback` (M15 P2) operates on structured goals, not prose — keeps working after heuristic removal.

**Outcome**

A conversational MCP surface organized around what scientists do (pick a stage or workflow → grab a bundle or supply bindings → run → get reproducible artifact), with all family-specific logic living in `registry/_<family>.py` + `planner_types.py` + `tasks/` + `workflows/` + optional `bundles.py` entries — **no MCP-layer edits required to add a new family**.

**Updated discussion**

- The experiment loop is a useful organizing idea and should stay.
- Implement it alongside, not instead of, `plan_request` and `prompt_and_run`.
- Do not claim **no MCP-layer edits required to add a new family** unless task parameter metadata is also derived from the registry; otherwise document the remaining `server.py` coupling explicitly.

**New from Stargazer/Latch**

- Make the experiment loop expose more of the contract directly: entry discovery should eventually surface registry-defined environment metadata and stable output names, not only execution-profile and resource hints.

**Backward compatibility — intentional migration.** Reshaping `run_task`/`run_workflow` signatures is a hard break against the M21 shape. Per DESIGN §8.7, this is an **intentional compatibility migration**: the old flat `inputs` dict is replaced with the typed `bindings` + scalar `inputs` + `resources` + `execution_profile` + `runtime_images` + `source_prompt` shape. `CHANGELOG.md` records the break, and `mcp_contract.py` tool descriptions advertise the new shape. No shim is provided; clients update at the same time the server does.

**Updated discussion**

- A no-shim hard break is acceptable here if this is a single-developer, coordinated branch change and all dependent callers, tests, and docs are updated in the same cutover.
- If the hard break stays, update callers, tests, prompt flows, and docs in the same branch before merge and record the cutover in `CHANGELOG.md`.
- Keep old and new request shapes from coexisting only if the cutover scope expands beyond one coordinated branch.

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

**Updated discussion**

- This is one of the strongest sections in the proposal. Keep the richer catalog payload and the family filter.
- Return only showcased entries and make the response fields stable enough for clients to use directly for discovery (`pipeline_family`, `pipeline_stage_order`, planner types, execution profiles, resource hints).
- Keep `list_available_bindings` as the separate file-discovery tool and add tests for category filter, `pipeline_family` filter, and non-showcased entry exclusion.

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
        "output_paths": _collect_output_paths(run_record_path),
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

**Updated discussion**

- Replace the planner-type-keyed binding shape unless the implementation explicitly supports nested and repeated planner values; a parameter-centric request shape is safer.
- If `TASK_PARAMETERS` remains the source of scalar metadata for now, document that as a temporary coupling and add a follow-up instead of implying full MCP-layer independence.
- Add tests for unknown bindings, missing scalars, repeated or nested inputs (or explicit rejection of them), and successful recipe freezing plus execution.

### 3. Reshape `run_workflow` in place (`server.py:869`)

```python
@mcp.tool()
def run_workflow(
    workflow_name: str,
    inputs: dict,
    resources: dict | None = None,
    execution_profile: Literal["local", "slurm"] = "local",
    runtime_images: dict[str, str] | None = None,
    source_prompt: str = "",
    runner: Any = subprocess.run,  # internal test seam; not part of MCP schema
) -> dict:
    """Run a registered workflow entrypoint. Scalars-only inputs; the workflow
    owns its internal assembly. Freeze + execute, returning a recipe_id for
    reproducibility.
    """
    if workflow_name not in SUPPORTED_WORKFLOW_NAMES:
        return _unsupported_target_reply(workflow_name, SUPPORTED_WORKFLOW_NAMES, kind="workflow")
    entry = registry.get_entry(workflow_name)

    # existing BRAKER3 evidence-check limitation (server.py:934-949) preserved verbatim
    if workflow_name == BRAKER3_WORKFLOW_NAME and not (inputs.get("rnaseq_bam_path") or inputs.get("protein_fasta_path")):
        return _limitation_reply(workflow_name, "BRAKER3 requires at least one evidence input.")

    plan = plan_typed_request(
        biological_goal=entry.compatibility.biological_stage or workflow_name,
        target_name=workflow_name,
        explicit_bindings={},        # workflow handles own assembly
        scalar_inputs=inputs,
        resource_request=_coerce_resource_spec(resources),
        execution_profile=execution_profile,
        runtime_images=runtime_images or {},
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

    return {
        "supported": True,
        "workflow_name": workflow_name,
        "recipe_id": artifact.recipe_id,
        "run_record_path": str(run_record_path),
        "artifact_path": str(artifact_path),
        "execution_profile": execution_profile,
        "output_paths": _collect_output_paths(run_record_path),
        "limitations": [],
    }
```

**Updated discussion**

- Give `run_workflow` the same top-level request contract as `run_task`, or explicitly document why workflow execution is intentionally different.
- If bundles are supposed to feed workflows, support typed bindings and tool-database inputs here too, or narrow the bundle claim.
- Add tests for workflow invocation with bundle-derived inputs, clear validation failure for missing required evidence, and recipe freezing.

### 4. New module `src/flytetest/bundles.py`

Curated starter fixtures keyed on biological contracts, extensible per family:

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
    manifest_path: str | None          # bundle definition file for inspection/review
    bindings: dict[str, dict]           # planner-type name -> field dict
    inputs: dict[str, object]           # scalar defaults
    runtime_images: dict[str, str]      # optional bundle-specific image overrides
    tool_databases: dict[str, str]      # optional bundle-specific database overrides
    applies_to: tuple[str, ...]         # registered entry names


BUNDLES: dict[str, ResourceBundle] = {
    "braker3_small_eukaryote": ResourceBundle(
        name="braker3_small_eukaryote",
        description="Small-eukaryote BRAKER3 annotation starter kit: reference "
                    "genome, paired RNA-seq reads, protein evidence.",
        pipeline_family="annotation",
        manifest_path="src/flytetest/bundles/braker3_small_eukaryote.yaml",
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
        runtime_images={},
        tool_databases={},
        applies_to=("braker3_annotation_workflow",),
    ),
    "m18_busco_demo": ResourceBundle(
        name="m18_busco_demo",
        description="M18 BUSCO fixture: small eukaryote proteins + lineage path.",
        pipeline_family="annotation",
        manifest_path="src/flytetest/bundles/m18_busco_demo.yaml",
        bindings={"ReferenceGenome": {"fasta_path": "data/busco/fixtures/genome.fa"}},
        inputs={"lineage_dataset": "eukaryota_odb10", "busco_cpu": 2, "busco_mode": "proteins"},
        runtime_images={},
        tool_databases={},
        applies_to=("busco_assess_proteins", "busco_annotation_qc_workflow"),
    ),
    # ... protein_evidence_demo, rnaseq_paired_demo follow the same pattern
}


def list_bundles(pipeline_family: str | None = None) -> list[dict]:
    """Enumerate curated bundles, optionally filtered by pipeline family."""
    return [
        {
            "name": b.name,
            "description": b.description,
            "pipeline_family": b.pipeline_family,
            "manifest_path": b.manifest_path,
            "applies_to": list(b.applies_to),
            "binding_types": sorted(b.bindings.keys()),
        }
        for b in BUNDLES.values()
        if pipeline_family is None or b.pipeline_family == pipeline_family
    ]


def load_bundle(name: str) -> dict:
    """Return a bundle's typed bindings + scalar inputs + runtime images ready
    to spread into run_task / run_workflow.
    """
    if name not in BUNDLES:
        raise KeyError(f"Unknown bundle {name!r}. Available: {sorted(BUNDLES)}")
    b = BUNDLES[name]
    return {
        "bindings": dict(b.bindings),
        "inputs": dict(b.inputs),
        "runtime_images": dict(b.runtime_images),
        "tool_databases": dict(b.tool_databases),
        "description": b.description,
        "pipeline_family": b.pipeline_family,
        "manifest_path": b.manifest_path,
    }


def _validate_bundles() -> None:
    """Import-time validation: catch broken bundles before the server starts."""
    for b in BUNDLES.values():
        # (a) every referenced path exists on disk (bindings, images, tool_databases)
        for type_name, field_dict in b.bindings.items():
            for field_name, value in field_dict.items():
                if field_name.endswith("_path") and not Path(value).exists():
                    raise FileNotFoundError(
                        f"Bundle {b.name!r}: {type_name}.{field_name} -> {value} not found"
                    )
        for key, value in b.runtime_images.items():
            if not Path(value).exists():
                raise FileNotFoundError(f"Bundle {b.name!r}: runtime_image {key} -> {value} not found")
        for key, value in b.tool_databases.items():
            if not Path(value).exists():
                raise FileNotFoundError(f"Bundle {b.name!r}: tool_database {key} -> {value} not found")
        # (b) every applies_to entry exists and accepts the bundle's binding types
        for entry_name in b.applies_to:
            entry = get_entry(entry_name)
            accepted = set(entry.compatibility.accepted_planner_types)
            missing = set(b.bindings) - accepted
            if missing:
                raise ValueError(
                    f"Bundle {b.name!r} declares bindings {sorted(b.bindings)} "
                    f"but entry {entry_name!r} only accepts {sorted(accepted)}"
                )
            if entry.compatibility.pipeline_family != b.pipeline_family:
                raise ValueError(
                    f"Bundle {b.name!r} pipeline_family={b.pipeline_family!r} "
                    f"mismatches entry {entry_name!r} family="
                    f"{entry.compatibility.pipeline_family!r}"
                )


_validate_bundles()
```

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

**Updated discussion**

- Keep bundles as optional starter kits for common workflows and demos.
- Do not validate bundles at import time. Server startup should succeed even if some bundle files are missing.
- Validate bundle paths when `list_bundles()` or `load_bundle()` is called.
- `list_bundles()` should return unavailable bundles with `available: false` and a short reason instead of crashing or silently failing.
- `load_bundle(name)` should return a clear error if the requested bundle is unavailable.
- Bundles are a convenience feature and do not replace `list_available_bindings`, which remains the path for discovering user data in the workspace.

**New from Stargazer/Latch**

- Prefer manifest-backed bundle definitions over Python-only literals so starter kits are inspectable, reviewable, and can carry availability metadata without import-time failures.
- Use the target entry's `compatibility.execution_defaults` as the default environment source of truth; bundle-local `runtime_images` and `tool_databases` should be explicit overrides only.
- Add tests covering: valid bundle listed, invalid bundle marked unavailable, startup unaffected by invalid bundles, and `load_bundle()` failing clearly for unavailable bundles.

**New from Latch, adapted to flyteTest's registry model**

### 4a. Expand `RegistryCompatibilityMetadata.execution_defaults`

Borrow the useful part of LatchBio's per-task environment idea, but keep flyteTest's registry as the source of truth. Extend `RegistryCompatibilityMetadata.execution_defaults` (or promote these keys to typed compatibility fields) so each registered entry already carries its environment defaults.

```python
RegistryCompatibilityMetadata(
    pipeline_family="annotation",
    pipeline_stage_order=3,
    accepted_planner_types=("ReferenceGenome", "ReadSet", "ProteinEvidenceSet"),
    produced_planner_types=("AnnotationGff",),
    supported_execution_profiles=("local", "slurm"),
    execution_defaults={
        "profile": "apptainer",
        "resources": {"cpu": 8, "memory": "32Gi"},
        "slurm_resource_hints": {"cpu": "8", "memory": "32Gi", "walltime": "08:00:00"},
        "runtime_images": {
            "braker_sif": "data/images/braker3_3.0.7.sif",
            "star_sif": "data/images/star_2.7.11a.sif",
        },
        "module_loads": ["python/3.11.9", "apptainer/1.4.1"],
        "env_vars": {},
        "tool_databases": {},
    },
)
```

`run_task` / `run_workflow` should resolve environment defaults from the target entry's registry metadata first. Explicit `runtime_images` overrides continue to apply on top, and if `tool_databases`, `module_loads`, or `env_vars` become runnable-surface overrides, they should merge into the same resolved environment object before freezing. The resolved environment is then captured in the `WorkflowSpec` so execution remains reproducible.

**Updated discussion**

- Expand registry execution metadata instead of introducing a separate environment-profile module.
- Keep the registry as the source of truth for runtime images, module loads, env vars, tool databases, and resource hints.
- Expose the resolved environment metadata through `list_entries()` once the request schema is stable.
- Add tests for default expansion, override precedence, and freezing the resolved environment into saved recipes.

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

`plan_request` remains the free-text planning entrypoint. It should keep attempting natural-language planning for supported requests and return a structured decline only when it cannot produce a supported plan.

**Updated discussion**

- Do not remove prompt-first planning from the server in this milestone.
- Keep `plan_request` as a natural-language entrypoint that returns either a structured planning result or a structured decline.
- Remove only the most brittle prompt heuristics after replacement behavior exists for the same supported cases.
- When `plan_request` cannot produce a supported plan, return a structured decline with the reason, the closest supported task or workflow names when available, and suggested next steps such as `list_entries`, `list_bundles`, `list_available_bindings`, or reuse of prior run outputs.
- Prefer narrowing heuristic scope over deleting prompt interpretation entirely.
- Add tests covering: a supported natural-language request still producing a structured plan, an unsupported request returning a structured decline, actionable next steps in decline payloads, and no regression in existing prompt-first flows such as `plan_request` and `prompt_and_run`.

### 6. Tool descriptions in `src/flytetest/mcp_contract.py`

Reframe the primary surface as *"the scientist's experiment loop"* — `list_entries` → `list_bundles` → `load_bundle` → `run_task` or `run_workflow`. Mark `prepare_run_recipe`, `run_local_recipe`, `run_slurm_recipe`, `approve_composed_recipe` as **inspect-before-execute** power-user tools. Lifecycle tools (`monitor_slurm_job`, `cancel_slurm_job`, `retry_slurm_job`, `wait_for_slurm_job`, `fetch_job_log`, `get_run_summary`, `inspect_run_result`, `get_pipeline_status`, `list_available_bindings`) unchanged.

Every `run_task` / `run_workflow` / `run_slurm_recipe` description carries a one-sentence note on **resource-hint handoff** (DESIGN §7.5): `execution_defaults["slurm_resource_hints"]` supplies sensible defaults for `cpu`/`memory`/`walltime`, but `queue` and `account` must come from the user — the server never invents them.

**Updated discussion**

- Update tool descriptions only after the request schema is settled.
- Keep `plan_request` and `prompt_and_run` in the documented primary surface for prompt-first clients.
- If tool names, arguments, or example payloads change, update MCP contract tests and showcase docs in the same change.

**New from Stargazer**

### 6a. Structured run outputs

Borrow Stargazer's stable output-marshalling direction, but keep flyteTest's run-record emphasis. `run_task` and `run_workflow` should return named outputs in addition to the run record location:

```python
return {
    "supported": True,
    "workflow_name": workflow_name,
    "recipe_id": artifact.recipe_id,
    "run_record_path": str(run_record_path),
    "artifact_path": str(artifact_path),
    "execution_profile": execution_profile,
    "outputs": {
        "annotation_gff": "/abs/path/to/annotation.gff3",
        "proteins_fasta": "/abs/path/to/proteins.fa",
    },
    "limitations": [],
}
```

`outputs` keys come from the registered entry's declared outputs when available; `output_paths` remains only as a temporary compatibility alias during the migration. Multi-output results should use stable declared names, not positional labels.

**Updated discussion**

- Return a stable `outputs` object so clients and scientists do not have to infer meaning from an unordered path list.
- Derive output names from registry metadata whenever possible.
- If `output_paths` is kept for migration, mark it transitional and remove it once callers are updated.
- Add tests for single-output and multi-output run replies.

### 7. Cross-run output reuse via `DurableAssetRef` (bindings)

`run_task` / `run_workflow` accept a special `bindings` field shape pointing at a prior run output, not a raw path:

```python
# raw path form (existing):
bindings={"ReferenceGenome": {"fasta_path": "data/braker3/reference/genome.fa"}}

# durable-ref form (new):
bindings={"AnnotationGff": {"$ref": {"run_id": "2026-04-16T12-00-00Z-abc123",
                                     "output_name": "annotation_gff"}}}
```

Resolution happens in `_materialize_bindings` via the existing `LocalManifestAssetResolver.resolve(durable_index=...)` path (M20b). When a `$ref` resolves, the concrete path is frozen into the WorkflowSpec so the recipe remains replayable even if `durable_asset_index.json` later changes. If resolution fails (ref not found, ambiguous, missing output_name), return a typed decline with the referenced `run_id` surfaced in `limitations`.

**Updated discussion**

- Use one binding representation that can carry raw paths, manifest-derived assets, and `$ref` outputs.
- Resolve refs before execution and freeze the concrete path into the saved recipe.
- Add tests for valid ref resolution, missing ref decline, and ambiguous ref decline.

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

**Updated discussion**

- Keep this section. It aligns well with the offline-compute constraints already documented for Slurm-backed runs.
- Implement `check_offline_staging()` as a reusable validation helper first.
- Make `validate_run_recipe()` and Slurm submission use the same findings schema so behavior stays consistent.
- Add tests for missing container images, missing tool databases, and paths outside the shared filesystem roots.

### 9. `source_prompt` empty-warning

In `run_task` / `run_workflow` / `plan_typed_request`, when `source_prompt == ""`, append a non-fatal advisory to the returned `limitations`:

```python
if not source_prompt:
    limitations.append("source_prompt was empty; the frozen recipe will lack "
                       "the original scientist request in its audit trail. "
                       "Pass source_prompt=<user question> for full provenance.")
```

This keeps pillar #2 (frozen recipes have provenance) honest without breaking clients that haven't adopted the field yet.

**Updated discussion**

- Implement this as a non-blocking advisory returned by `run_task`, `run_workflow`, and `plan_typed_request`.
- Add tests for empty and non-empty `source_prompt` so the warning behavior stays stable.

### 10. Decline-to-bundles routing

`_limitation_reply` and `_unsupported_target_reply` get a new `suggested_bundles` field populated from `bundles.list_bundles(pipeline_family=entry.compatibility.pipeline_family)` when the decline is for a specific registered entry. The reply shape becomes:

```python
{
    "supported": False,
    "target": "braker3_annotation_workflow",
    "limitations": ["BRAKER3 requires at least one evidence input."],
    "suggested_bundles": [
        {"name": "braker3_small_eukaryote",
         "description": "...",
         "applies_to": ["braker3_annotation_workflow"]},
    ],
    "next_steps": [
        "load_bundle('braker3_small_eukaryote') then re-call run_workflow",
    ],
}
```

`plan_request` (the free-text preview tool) uses the same routing when it declines, giving the client LLM an obvious recovery path without parsing prose.

**Updated discussion**

- Extend decline payloads with structured `suggested_bundles` and `next_steps` fields.
- Include `list_available_bindings`, prior run reuse, or prompt reformulation in `next_steps` when those are the better recovery path.
- Add tests for decline payload shape from both `plan_request` and the runnable entrypoint tools.

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

**Updated discussion**

- This is one of the safest and highest-value additions in the proposal.
- Land this tool before changing submission behavior so users can inspect findings without side effects.
- Reuse the same resolver and staging logic that actual execution uses.
- Add tests for a clean recipe, a missing binding target, and staging failures.

### 12. Call-site sweep for the BC migration

Because `run_task` / `run_workflow` change shape (not shimmed), every caller breaks the moment the signature changes. Sweep and update in the same commit series:

- `tests/test_server.py`, `tests/test_mcp_prompt_flows.py`, `tests/test_planning.py`, `tests/test_spec_executor.py`, and any other test referencing the flat `inputs=...` shape.
- Smoke scripts under `scripts/` (if any invoke `run_task`/`run_workflow`).
- `docs/mcp_showcase.md` and `docs/tutorial_context.md` walkthroughs.
- `docs/realtime_refactor_plans/` active plans that quote the old shape.

Grep anchors: `rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/` — every hit is a call-site review. CI green post-sweep is part of the acceptance criteria.

**Updated discussion**

- If the hard break remains, update callers, tests, docs, and scripts in the same branch before merge.
- Fail the milestone if old call patterns remain where the new request shape is supposed to replace them.

### 13. Seed-bundle tool-DB reality check

`_validate_bundles()` fires at import. If a seed bundle references `data/busco/lineages/eukaryota_odb10/` and that directory is absent, the server won't boot. Before merging:

- Audit each seed bundle against what actually ships under `data/`.
- For bundles whose tool DBs already exist: ship as-is.
- For bundles whose tool DBs don't exist locally: either drop the missing bundle from the initial seed set (preferred — ship fewer, working bundles) or mark the specific tool-DB paths with a `demo_only=True` flag that `_validate_bundles()` treats as a soft-warn instead of a hard failure.

Decision: **ship fewer, working bundles** — hard-fail validation stays loud; a bundle is either usable or absent.

**Updated discussion**

- Keep the "ship fewer, working bundles" direction.
- Mark invalid bundles unavailable instead of crashing import, and add tests proving startup still succeeds when a seed bundle is broken.

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

**Updated discussion**

- Defer this sweep until the request schema and prompt-planning behavior are final.
- Once those are final, update `AGENTS.md`, `DESIGN.md`, `docs/mcp_showcase.md`, `docs/tutorial_context.md`, and the `.codex/` guidance in the same change series.
- Keep the grep-based stale-reference checks as acceptance criteria.

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

**Files that do NOT change:**

- `src/flytetest/server.py` — `run_task` / `run_workflow` / `list_entries` / `list_bundles` / `load_bundle` pick up the new entry automatically through `REGISTRY_ENTRIES`, `SUPPORTED_TASK_NAMES`, `SUPPORTED_WORKFLOW_NAMES`, and `_local_node_handlers()` (all registry-derived since B3+B4).
- `src/flytetest/planning.py` — structured-only `plan_typed_request` validates against the new entry's `accepted_planner_types` without family-specific branches.
- `src/flytetest/mcp_contract.py` — surface constants derive from the registry.
- `src/flytetest/spec_artifacts.py`, `spec_executor.py` — freeze/execute infrastructure is generic over any registered target.
- `src/flytetest/resolver.py` — already handles manifest + durable-index resolution generically.
- `src/flytetest/registry/__init__.py` — one-line import of `GATK_ENTRIES` already landed (B5).

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

**Updated discussion**

- Keep the registry-driven family growth goal.
- Do not promise full MCP-layer independence until task parameter metadata and request validation no longer depend on `TASK_PARAMETERS`.
- If that remains a goal, add an explicit follow-up to move task interface metadata behind the registry or another derived source.

## Critical Files

- `src/flytetest/server.py` — reshape `run_task` (line 995), `run_workflow` (line 869), widen `list_entries`; register `list_bundles` / `load_bundle` / `validate_run_recipe` in `create_mcp_server()`; add `source_prompt` empty-warning and decline-to-bundles routing in the reply helpers.
- `src/flytetest/planning.py` — delete the prose heuristics; reshape `plan_typed_request` to structured-only; preserve composition fallback and approval plumbing.
- `src/flytetest/mcp_contract.py` — update tool descriptions; reframe around the scientist's experiment loop; add the resource-hint handoff note to run tools.
- `src/flytetest/bundles.py` — **new**.
- `src/flytetest/registry/_types.py` — expand `RegistryCompatibilityMetadata.execution_defaults` or promote its environment keys to typed compatibility fields.
- `src/flytetest/registry/_<family>.py` — populate per-entry environment defaults (`runtime_images`, `module_loads`, `env_vars`, `tool_databases`) alongside existing resource hints.
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

**Updated discussion**

- Treat request-shape changes across `server.py`, `planning.py`, `spec_artifacts.py`, docs, and tests as one coordinated change set.
- Do not land partial schema edits in only one layer.

## Reused Utilities

- `RegistryEntry.category`, `accepted_planner_types`, `produced_planner_types`, `pipeline_family`, `pipeline_stage_order`, `execution_defaults["slurm_resource_hints"]` (`registry/_types.py:47-63`).
- `registry.list_entries(category)`, `registry.get_entry(name)` (`registry/__init__.py:46,60`).
- `TASK_PARAMETERS` (`server.py:125`).
- `artifact_from_typed_plan`, `save_workflow_spec_artifact`, `load_workflow_spec_artifact` (`spec_artifacts.py`).
- `LocalWorkflowSpecExecutor`, `SlurmWorkflowSpecExecutor` (`spec_executor.py`).
- `LocalManifestAssetResolver`, `DurableAssetRef` (`resolver.py`, `spec_artifacts.py`).
- Planner dataclasses (`planner_types.py`, `types/assets.py`).
- `_try_composition_fallback`, `requires_user_approval` plumbing (`planning.py` — keep intact).
- Existing execution metadata in registry compatibility entries should be expanded into the single environment source of truth.

**Updated discussion**

- Reuse existing `prompt_and_run`, `list_available_bindings`, resolver, and recipe-freezing code before adding new helper paths.
- If a new helper duplicates existing behavior, remove the duplication or document why both paths are needed.

**New from Stargazer/Latch**

- Prefer expanding existing registry execution metadata and named outputs before introducing parallel sources of truth.

## Verification

1. **Compile**: `python -m compileall src/flytetest/server.py src/flytetest/planning.py src/flytetest/bundles.py`.
2. **Heuristic removal**: `rg -n "_extract_prompt_paths|_extract_braker_workflow_inputs|_extract_protein_workflow_inputs|_classify_target|_extract_execution_profile|_extract_runtime_images" src/flytetest/` → zero hits.
3. **Pipeline-map catalog**: `list_entries(category="workflow")` populates `pipeline_family`, `pipeline_stage_order`, `accepted_planner_types`, `produced_planner_types`, `slurm_resource_hints` for every showcased entry. `list_entries(pipeline_family="variant_calling")` returns the `gatk_haplotype_caller` entry once its `showcase_module` is populated in a follow-up.
4. **Registry environment defaults**: each showcased entry carries runtime images, module loads, env vars, and tool-database defaults in `compatibility.execution_defaults`; explicit overrides win; the resolved environment is frozen into the saved recipe.
5. **Bundle validation**: `list_bundles()` returns the seeded bundles and their availability status without import-time failure.
6. **`run_task`**: `run_task("exonerate_align_chunk", bindings=load_bundle("protein_evidence_demo")["bindings"], inputs={"exonerate_model":"protein2genome"})` writes `.runtime/specs/<id>.json` with `source_prompt` captured, executes, and returns a `run_record_path` plus stable named `outputs`.
7. **`run_workflow`**: `run_workflow("transcript_evidence_generation", inputs={...})` with local profile produces a frozen recipe + run record + stable named `outputs`.
8. **Slurm render + offline staging**: `run_workflow(..., execution_profile="slurm", resources={...})` writes the sbatch script, directives match. `check_offline_staging` blocks submission when a container path, tool-DB path, or resolved input path is missing or outside `shared_fs_roots`; findings appear in the MCP reply as structured limitations.
9. **`validate_run_recipe`**: pointed at a freshly frozen recipe, returns `supported=True` with empty findings. Pointed at a recipe whose container path is then removed, returns `supported=False` with a `container` finding naming the missing path.
10. **Cross-run reuse**: `run_workflow(..., bindings={"AnnotationGff": {"$ref": {"run_id": "<prior>", "output_name": "annotation_gff"}}})` resolves through the durable asset index, freezes the concrete path into the new recipe, and runs. A bad `$ref` returns a typed decline listing the offending run_id.
11. **`source_prompt` warning**: `run_task(..., source_prompt="")` succeeds but includes the empty-prompt advisory in `limitations`.
12. **Decline-to-bundles**: `run_workflow("braker3_annotation_workflow", inputs={})` returns `suggested_bundles` containing `braker3_small_eukaryote` and a `next_steps` entry.
13. **Resource-hint handoff docs**: `list_entries(category="workflow")` descriptions and `run_workflow` tool description both mention that `queue` and `account` must be user-supplied.
14. **Approval gate preserved**: a planner-composed multi-stage DAG via `prepare_run_recipe` still produces `requires_user_approval=True` and blocks until `approve_composed_recipe`. Registered entrypoints via `run_task` / `run_workflow` auto-approve.
15. **Extensibility test**: a synthetic `_testfamily.py` entry (added via a test fixture) surfaces through `list_entries(pipeline_family="testfamily")` and runs through `run_workflow` without any MCP-layer edits.
16. **Full suite**: `pytest tests/` holds at previous green count (~495 + 1 skipped) minus tests retired with the heuristics plus new tests for registry environment defaults, staging, validate, named outputs, `$ref`, decline-to-bundles, and empty-prompt advisories.
17. **Call-site sweep**: `rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/` — no hits use the old flat `inputs=` shape.
18. **Agent context sweep**: `rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md` → zero stale references.
19. **Server boots from a clean clone**: bundle loading and registry compatibility metadata import succeed even when some optional bundle assets are unavailable.

**Updated discussion**

- Keep prompt-first flow coverage (`plan_request`, `prompt_and_run`) alongside structured-tool coverage.
- Add verification for bundle unavailability behavior and decline payload next steps, not just happy-path execution.

## Out of Scope

- Server-side LLM parsing (client-side NL chosen).
- Replacing the power-user `prepare_*` / `run_*_recipe` / `approve_composed_recipe` tools.
- Changes to composition fallback, approval-gate logic, Slurm lifecycle observability semantics (`classify_slurm_failure()`), or durable asset index on-disk shape.
- Lighting up GATK (separate milestone — this plan preserves extensibility; it does not implement variant calling).
- New fixture data; bundles curate existing files under `data/`.
- Metadata-keyed asset indexing (stargazer's CID model); flyteTest stays path-based with bundles + durable index for curation.
- Backwards-compatibility shim for the old M21 flat `inputs` shape — this is an intentional compatibility migration (DESIGN §8.7); `CHANGELOG.md` records it.

**Updated discussion**

- State explicitly that this milestone retains prompt-first planning in the server.
- Do not remove power-user recipe tools or shift to client-side-only planning in this slice.
