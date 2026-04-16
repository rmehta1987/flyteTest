# Serialization Consolidation + Registry Package Restructure

**Date:** 2026-04-16
**Status:** Final draft — ready for implementation
**Branch:** Create a new branch from `main` (e.g. `refactor/serialization-registry`)
**Prerequisite:** M23-26 complete (generic asset subclasses landed)

> Assessment: Revise.
> The direction is strong, but I would not call this final or implementation-ready yet. The draft still overstates how much becomes automatic after the registry split and does not fully account for serializer behavior differences across layers.

---

## Context

> Assessment: Agree.
> This section correctly identifies the two real scaling problems: duplicated serializer logic and registry metadata sprawl. That framing is practical and well aligned with the current codebase.

Two problems block easy GATK pipeline expansion:

1. **Serialization duplication** — Three modules each maintain ~80 lines of
   near-identical `_serialize*`/`_deserialize*` helpers. New types must pick
   which to inherit, and subtle behavioral differences cause round-trip bugs.

2. **Manual registration explosion** — Adding ONE workflow requires 6+
   insertion points across 2 files (`registry.py` x4 dicts,
   `mcp_contract.py` x2). GATK variant calling could add 10+ workflows;
   this doesn't scale.

### Design Rationale

> Assessment: Agree.
> Rejecting decorators and metaclasses is the right decision for this repository. The registry is a metadata catalog, not a name-to-callable dispatch table, so the plain-data package approach fits the architecture much better.

Patterns evaluated and why we chose what we did:

- **Stargazer** (`Asset.__init_subclass__`): auto-registers *types* via
  metaclass — great for class hierarchies. FlyteTest's registry is a
  **catalog** (name->metadata), not a dispatch table (name->callable), so
  the metaclass machinery doesn't fit. But the *structural* pattern of
  splitting by family into a package (Stargazer's `assets/` folder) maps
  directly.

- **sbi** (`@register_quality_metric`): decorator on function populates
  module-level dict. Rejected — import side effects, circular import risk,
  30-line decorator args unreadable on functions, testing requires importing
  all workflow modules, ordering guarantees lost, scale mismatch (3 metrics
  vs 73 entries).

- **autoregistry** (`Registry` metaclass): solves name->callable dispatch
  with configurable naming rules. FlyteTest's composition is type-graph-based
  (metadata matching via `produced_planner_types` -> `accepted_planner_types`),
  not dispatch-based. A metaclass registry can't carry the rich metadata
  fields (`execution_defaults`, `pipeline_stage_order`, etc.) that drive
  dynamic pipeline composition.

**Chosen approach**: Plain data (tuples of `RegistryEntry` dataclasses)
organized by pipeline family in a package. No decorators, no metaclasses,
no import-order tricks. Composition via type-graph metadata matching.

### Key Files (current state, read before implementing)

> Assessment: Mostly agree.
> This is a useful map of the impacted surface. I would add `planning.py` explicitly, because prompt classification and target-specific policy still limit how automatic new workflow support actually becomes.

| File | Role | Lines |
|---|---|---|
| `src/flytetest/registry.py` | Monolith: 73 entries + 3 parallel dicts + query functions | 2679 |
| `src/flytetest/specs.py` | `SpecSerializable` mixin, `_serialize`/`_deserialize` (lines 22-103) | 331 |
| `src/flytetest/planner_types.py` | `PlannerSerializable` mixin, `_serialize_value`/`_deserialize_value` (lines 38-109) | 308 |
| `src/flytetest/types/assets.py` | `ManifestSerializable` mixin (superset), `_serialize_manifest_value`/`_deserialize_manifest_value` (lines 32-115) | 903 |
| `src/flytetest/mcp_contract.py` | 12 hardcoded `ShowcaseTarget` entries + `SUPPORTED_*` constants | 310 |
| `src/flytetest/server.py` | `_local_node_handlers()` dispatch, `TASK_PARAMETERS` | 3131 |
| `src/flytetest/config.py` | `TaskEnvironmentConfig` entries (stays manual) | -- |

---

## Track A: Serialization Consolidation

> Assessment: Revise.
> Consolidation is worthwhile, but this section should state that behavioral preservation matters more than deduplication. The three serializers are similar, not identical, and the plan should treat that as a compatibility constraint.

### Step A1 — Create `src/flytetest/serialization.py`

> Assessment: Revise.
> A shared module makes sense, but the current wording implies one universal deserialize behavior. The safer design is shared helpers with layer-specific wrappers so only the asset layer keeps scalar coercion while specs and planner types preserve current pass-through semantics.

New file with the superset behavior (modeled from `ManifestSerializable`
in `types/assets.py` lines 32-145):

- `serialize_value(value)` — Path->str, tuple->list, dict recursion,
  dataclass field-by-field with `to_dict()` fallback, scalar passthrough
- `deserialize_value(annotation, value)` — None, Any passthrough, Path,
  scalar coercion (str/int/bool), tuple, dict, Optional unwrapping,
  dataclass `from_dict()` with field-by-field fallback
- `class SerializableMixin` — plain class (not dataclass), provides
  `to_dict()`/`from_dict()` via `dataclasses.fields(self)` iteration.
  Works with `@dataclass(frozen=True, slots=True)` consumers via MRO —
  `self` is the dataclass instance at runtime.

Create `tests/test_serialization.py` with edge-case round-trips (Path,
nested dataclass, Optional, tuple, dict, scalar coercion, None).

**Files:** `src/flytetest/serialization.py` (new), `tests/test_serialization.py` (new)

### Step A2 — Rewire `specs.py`

> Assessment: Revise.
> This is not a clean swap unless tests first lock current spec behavior. I would explicitly say that `SpecSerializable` delegates to shared helpers while preserving its current deserialize semantics.

Remove `_serialize()`, `_deserialize()`, `_is_optional()` (lines 22-103).
`SpecSerializable` becomes a thin subclass of `SerializableMixin`.
No subclass overrides `to_dict`/`from_dict` — this is a clean swap.

**Validation:** `python3 -m unittest tests.test_specs tests.test_spec_artifacts tests.test_spec_executor tests.test_recipe_approval`

### Step A3 — Rewire `planner_types.py`

> Assessment: Revise.
> The same caution applies here. `PlannerSerializable` should move to shared helpers only if planner-facing round-trips remain behaviorally unchanged.

Remove `_serialize_value()`, `_deserialize_value()`, `_is_optional()` (lines 38-109).
`PlannerSerializable` becomes a thin subclass of `SerializableMixin`.

**Validation:** `python3 -m unittest tests.test_planner_types tests.test_planning`

### Step A4 — Rewire `types/assets.py`

> Assessment: Mostly agree.
> Migrating assets last is the right order, and the golden-output fixture requirement is important. I would strengthen this by requiring representative manifest reload tests, not only freshly serialized in-memory objects.

Remove `_serialize_manifest_value()`, `_deserialize_manifest_value()`,
`_is_optional_manifest_type()` (lines 32-115). `ManifestSerializable` becomes
a thin subclass of `SerializableMixin`.

Add a golden-output fixture test **before** this step to guard wire-format
stability — serialize a representative asset, assert exact JSON output.

**Validation:** Full suite `python3 -m unittest discover -s tests`, plus manifest reload check.

---

## Track B: Registry Package (Fold Dicts + Split By Pipeline Family)

> Assessment: Agree.
> This is the strongest part of the proposal. Folding the parallel dicts into self-contained entries and splitting the monolith by pipeline family is the right structural change for scaling into additional workflow families.

### Design

> Assessment: Mostly agree.
> The family-package split is good, but showcase exposure metadata should not live inside compatibility metadata. Compatibility should remain about planner/type-graph behavior, while MCP exposure should be modeled separately.

Two changes working together:

1. **Fold the 3 parallel dicts into each `RegistryEntry`** — eliminate
   `_WORKFLOW_COMPATIBILITY_METADATA` (line 2286),
   `_WORKFLOW_LOCAL_RESOURCE_DEFAULTS` (line 2509),
   `_WORKFLOW_SLURM_RESOURCE_HINTS` (line 2535),
   and the `_backfill_workflow_compatibility_metadata()` merge step (line 2606).
   Each entry becomes self-contained.

2. **Split `registry.py` into a package by pipeline family** — same
   pattern as Stargazer's `assets/` folder. Each family file contains
   the full type graph for that pipeline, scannable in one place. Adding
   a new pipeline family = creating one new file.

```
src/flytetest/registry/
    __init__.py               (collect + query functions)
    _types.py                 (dataclass definitions)
    _transcript_evidence.py   (8 entries)
    _consensus.py             (16 entries)
    _protein_evidence.py      (6 entries)
    _annotation.py            (5 entries)
    _evm.py                   (12 entries)
    _postprocessing.py        (21 entries)
    _rnaseq.py                (5 entries)
    _gatk.py                  (future — B5 proof of concept)
```

**No decorators, no metaclasses, no import-order tricks.** Each family
file exports a tuple of `RegistryEntry(...)` constructions. `__init__.py`
concatenates them and provides the query functions.

### Step B1 — Create `src/flytetest/registry/` package structure

> Assessment: Mostly agree.
> Preserving the public `flytetest.registry` import surface is the right compatibility choice. I would avoid adding `showcase_module` to `RegistryCompatibilityMetadata` at this stage and keep the package split independent from MCP concerns.

Create the package with two files first:

**`_types.py`** — move the pure dataclass definitions from `registry.py`:
- `Category` type alias (line 15)
- `InterfaceField` (line 19)
- `RegistryCompatibilityMetadata` (line 32)
- `RegistryEntry` (line 54)
- Add `showcase_module: str = ""` field to `RegistryCompatibilityMetadata`

**`__init__.py`** — re-export everything from `_types.py` plus the query
functions (`list_entries`, `get_entry`, `get_pipeline_stages`). For now,
still import the entries from the old `registry.py` so nothing breaks.

Rename old `src/flytetest/registry.py` to `src/flytetest/_registry_legacy.py`
temporarily, import from it in the new `__init__.py`.

**Files:** `src/flytetest/registry/` (new package)
**Validation:** `python3 -m compileall src/flytetest/` + full test suite.
All existing `from flytetest.registry import ...` must still work.

### Step B2 — Fold parallel dicts into entries and split by family

> Assessment: Agree with one revision.
> Moving compatibility and resource defaults inline with each entry is exactly the maintainability improvement the codebase needs. I would keep runtime and exposure metadata distinct so each entry becomes self-contained without mixing unrelated concerns into the compatibility object.

One family at a time, create the family file with self-contained entries.
Each entry gets its compatibility metadata + resources inline.

**Example — `_annotation.py`:**
```python
from flytetest.registry._types import (
    RegistryEntry, InterfaceField, RegistryCompatibilityMetadata,
)

ANNOTATION_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name="ab_initio_annotation_braker3",
        category="workflow",
        description="BRAKER3 ab initio annotation ...",
        inputs=( ... ),   # existing InterfaceField tuples
        outputs=( ... ),
        tags=( ... ),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage="BRAKER3 ab initio annotation",
            accepted_planner_types=("AnnotationEvidenceSet",),
            produced_planner_types=("ConsensusAnnotation",),
            execution_defaults={
                "profile": "local",
                "result_manifest": "run_manifest.json",
                "resources": {"cpu": "16", "memory": "64Gi"},
                "slurm_resource_hints": {"cpu": "16", "memory": "64Gi"},
            },
            supported_execution_profiles=("local", "slurm"),
            synthesis_eligible=True,
            pipeline_family="annotation",
            pipeline_stage_order=5,
            showcase_module="flytetest.workflows.annotation",
        ),
    ),
    # ... stage_braker3_inputs, braker3_predict, normalize_braker3_for_evm,
    #     collect_braker3_results (4 tasks)
)
```

**Family file assignment (73 entries = 57 tasks + 16 workflows):**

| File | Tasks | Workflows | Total |
|---|---|---|---|
| `_transcript_evidence.py` | trinity_denovo, star_genome_index, star_align, samtools_merge, trinity_gg, stringtie, collect_transcript_evidence (7) | transcript_evidence_generation (1) | 8 |
| `_consensus.py` | pasa_accession, combine_trinity, pasa_seqclean, pasa_create_db, pasa_align, collect_pasa, prepare_pasa_update, pasa_load, pasa_update_gene, finalize_pasa_update, collect_pasa_update, transdecoder_train, collect_transdecoder (13) | pasa_transcript_alignment, annotation_refinement_pasa, transdecoder_from_pasa (3) | 16 |
| `_protein_evidence.py` | stage_protein, chunk_protein, exonerate_align, exonerate_to_gff3, exonerate_concat (5) | protein_evidence_alignment (1) | 6 |
| `_annotation.py` | stage_braker3, braker3_predict, normalize_braker3, collect_braker3 (4) | ab_initio_annotation_braker3 (1) | 5 |
| `_evm.py` | prepare_evm_transcript/protein/prediction, collect_evm_prep, prepare_evm_execution, evm_partition/write/execute/recombine, collect_evm (10) | consensus_annotation_evm_prep, consensus_annotation_evm (2) | 12 |
| `_postprocessing.py` | repeatmasker_to_bed, gffread_proteins, funannotate_remove/blast, remove_overlap/blast_hits, collect_repeat_filter, busco_assess, collect_busco, eggnog_map, collect_eggnog, agat_statistics/convert/cleanup (14) | annotation_repeat_filtering, annotation_qc_busco, annotation_functional_eggnog, annotation_postprocess_agat/conversion/cleanup, annotation_postprocess_table2asn (7) | 21 |
| `_rnaseq.py` | salmon_index, fastqc, salmon_quant, collect_results (4) | rnaseq_qc_quant (1) | 5 |

Each file is ~150-500 lines — the full type graph for that pipeline
segment, scannable in one place.

**`__init__.py`** collects them:
```python
from flytetest.registry._types import *  # noqa: F401,F403 — re-export dataclasses
from flytetest.registry._transcript_evidence import TRANSCRIPT_EVIDENCE_ENTRIES
from flytetest.registry._consensus import CONSENSUS_ENTRIES
from flytetest.registry._protein_evidence import PROTEIN_EVIDENCE_ENTRIES
from flytetest.registry._annotation import ANNOTATION_ENTRIES
from flytetest.registry._evm import EVM_ENTRIES
from flytetest.registry._postprocessing import POSTPROCESSING_ENTRIES
from flytetest.registry._rnaseq import RNASEQ_ENTRIES

REGISTRY_ENTRIES: tuple[RegistryEntry, ...] = (
    TRANSCRIPT_EVIDENCE_ENTRIES
    + CONSENSUS_ENTRIES
    + PROTEIN_EVIDENCE_ENTRIES
    + ANNOTATION_ENTRIES
    + EVM_ENTRIES
    + POSTPROCESSING_ENTRIES
    + RNASEQ_ENTRIES
)
_REGISTRY: dict[str, RegistryEntry] = {e.name: e for e in REGISTRY_ENTRIES}


def list_entries(category: Category | None = None) -> tuple[RegistryEntry, ...]:
    ...  # moved from registry.py line 2634


def get_entry(name: str) -> RegistryEntry:
    ...  # moved from registry.py line 2648


def get_pipeline_stages(family: str) -> list[tuple[str, str]]:
    ...  # moved from registry.py line 2664
```

**Delete from `_registry_legacy.py`:**
- `_WORKFLOW_COMPATIBILITY_METADATA` dict (line 2286)
- `_WORKFLOW_LOCAL_RESOURCE_DEFAULTS` dict (line 2509)
- `_WORKFLOW_SLURM_RESOURCE_HINTS` dict (line 2535)
- `_with_resource_defaults()` (line 2566)
- `_backfill_workflow_compatibility_metadata()` (line 2606)
- Then delete `_registry_legacy.py` entirely.

**Validation:** Full test suite. `REGISTRY_ENTRIES` must contain the same
73 entries. `get_pipeline_stages("annotation")` must return same order.

### Step B3 — Derive `mcp_contract.py` showcase targets from registry

> Assessment: Revise.
> Deriving showcase target lists from registry data is a good cleanup, but this step currently over-couples MCP exposure to compatibility metadata and assumes source paths can be reconstructed safely from module names. It would be better to use explicit exposure metadata or one tested helper that resolves both `module_name` and `source_path` consistently.

The `showcase_module` field on `RegistryCompatibilityMetadata` (added in
B1) replaces the 12 hardcoded `ShowcaseTarget` entries:

```python
from flytetest.registry import REGISTRY_ENTRIES

SHOWCASE_TARGETS: tuple[ShowcaseTarget, ...] = tuple(
    ShowcaseTarget(
        name=e.name,
        category=e.category,
        module_name=e.compatibility.showcase_module,
        source_path=(_PACKAGE_ROOT / e.compatibility.showcase_module
                     .replace("flytetest.", "").replace(".", "/")).with_suffix(".py"),
    )
    for e in REGISTRY_ENTRIES
    if e.compatibility.showcase_module
)
SUPPORTED_TARGET_NAMES = tuple(t.name for t in SHOWCASE_TARGETS)
SUPPORTED_WORKFLOW_NAMES = tuple(
    t.name for t in SHOWCASE_TARGETS if t.category == "workflow"
)
SUPPORTED_TASK_NAMES = tuple(
    t.name for t in SHOWCASE_TARGETS if t.category == "task"
)
```

Delete the 12 hardcoded `ShowcaseTarget(...)` blocks and the 12
`SUPPORTED_*_NAME` constants (lines 88-99 in current file).

Derive `SHOWCASE_LIMITATIONS` strings dynamically from
`SUPPORTED_TARGET_NAMES` instead of hardcoding the name list.

What stays manual: `SUPPORTED_WORKFLOW_NAME` (primary default), example
prompts, tool names, resource URIs, runtime binding rules.

**Files:** `src/flytetest/mcp_contract.py`
**Validation:** `python3 -m unittest tests.test_server tests.test_mcp_prompt_flows`

### Step B4 — Derive `server.py` handler dispatch from the registry

> Assessment: Mostly agree.
> Deriving the handler map from supported workflow and task names is a good simplification. This section should also say clearly that target-specific validation and stage policy elsewhere in `server.py` still remain manual after this step.

`_local_node_handlers()` (line 1249) currently lists 8 workflow name
constants mapped to `workflow_handler` plus `SUPPORTED_TASK_NAMES` mapped
to `task_handler`. After B3, both `SUPPORTED_WORKFLOW_NAMES` and
`SUPPORTED_TASK_NAMES` are derived from the registry, so replace the 8
explicit constants:

```python
return {
    **{name: workflow_handler for name in SUPPORTED_WORKFLOW_NAMES},
    **{name: task_handler for name in SUPPORTED_TASK_NAMES},
}
```

`TASK_PARAMETERS` (4 entries at line 131 — exonerate, busco, fastqc,
gffread) stays manual in `server.py`. These are MCP tool-validation
schemas, not biological metadata.

**Files:** `src/flytetest/server.py`
**Validation:** `python3 -m unittest tests.test_server`

### Step B5 — GATK proof of concept

> Assessment: Revise.
> As a metadata-only proof of concept, this is a strong validation step. I would remove the implication that setting `showcase_module` later is enough for safe MCP exposure, because planning and execution still contain named target policies that are not generalized yet.

Create `src/flytetest/registry/_gatk.py`:

```python
from flytetest.registry._types import (
    RegistryEntry, InterfaceField, RegistryCompatibilityMetadata,
)

GATK_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        name="gatk_haplotype_caller",
        category="workflow",
        description="Call germline SNPs and indels via local re-assembly.",
        inputs=( ... ),
        outputs=( ... ),
        tags=("gatk", "variant-calling"),
        compatibility=RegistryCompatibilityMetadata(
            biological_stage="germline variant calling",
            pipeline_family="variant_calling",
            pipeline_stage_order=3,
            execution_defaults={
                "resources": {"cpu": "8", "memory": "32Gi"},
                "slurm_resource_hints": {"cpu": "8", "memory": "32Gi"},
            },
            supported_execution_profiles=("local", "slurm"),
            # showcase_module="" — no handler yet, not on MCP surface
        ),
    ),
)
```

Add one import + concatenation line in `__init__.py`. Shows up in
`list_entries()` and `get_pipeline_stages("variant_calling")` immediately.
Setting `showcase_module="flytetest.workflows.gatk"` later auto-adds it
to the MCP surface.

---

## What Stays Manual

> Assessment: Mostly agree.
> This list is directionally correct, but incomplete. I would also call out prompt-classification heuristics, target-specific assumptions, stage-to-input translation logic, and other workflow-specific execution guards that still live outside the registry.

| Item | Why |
|---|---|
| `TaskEnvironmentConfig` entries in `config.py` | Flyte runtime config, not registry metadata |
| `TASK_PARAMETERS` in `server.py` (4 entries) | MCP tool-validation schemas, not biological metadata |
| Example prompts in `mcp_contract.py` | Handcrafted |
| Primary/default workflow choice (`SUPPORTED_WORKFLOW_NAME`) | Policy decision |
| Workflow-specific validation guards (BRAKER3 evidence check) | Domain logic in `server.py` |
| Runtime binding rules in `mcp_contract.py` | Protocol documentation, not derivable |

---

## What Does NOT Change

> Assessment: Mostly agree.
> These non-goals are useful and should stay. I would add one more explicit non-change: this refactor does not automatically broaden the prompt planning surface or make newly registered workflows runnable through MCP.

- `run_manifest.json` wire format
- Flyte `@task`/`@workflow` signatures
- `spec_artifacts._json_ready()` and `_write_json_atomically()`
- Public API names (`REGISTRY_ENTRIES`, `list_entries`, `get_entry`, etc.)

---

## Sequencing

> Assessment: Revise.
> The high-level order is reasonable, but Track A should not proceed past helper design until regression fixtures are in place. I would also soften the claim that B1 and B2 are purely mechanical, because moving metadata affects public payloads, tests, and downstream assumptions.

```
Track A:  A1 -> A2 -> A3 -> A4   (serialization, each step testable)
Track B:  B1 -> B2 -> B3 -> B4 -> B5  (registry consolidation)

A and B are independent — can run in parallel.
B1+B2 are mechanical: fold data from dicts onto entries.
B3+B4 are the payoff: MCP and server derive from registry.
B5 is the proof: GATK entry in one file, auto-visible everywhere.
```

Recommended merge order: A1, B1, B2, A2-A4, B3, B4, B5

B1+B2 first because they're the simplest high-value change — immediate
reduction from 6 insertion points to 1 per workflow.

---

## Before vs After: Adding a New Workflow

> Assessment: Revise.
> The "one insertion point" claim is accurate only for catalog registration. It is not yet true for fully supported prompt-plannable or MCP-runnable workflows, so the section should distinguish catalog expansion from runtime exposure.

**Before (6 insertion points across 2 files):**
1. `registry.py` — `RegistryEntry(...)` block (~30 lines)
2. `registry.py` — `_WORKFLOW_COMPATIBILITY_METADATA[name]` (~15 lines)
3. `registry.py` — `_WORKFLOW_LOCAL_RESOURCE_DEFAULTS[name]` (1 line)
4. `registry.py` — `_WORKFLOW_SLURM_RESOURCE_HINTS[name]` (1 line)
5. `mcp_contract.py` — `ShowcaseTarget(...)` + `SUPPORTED_*` constant
6. `mcp_contract.py` — update limitation strings

**After (1 insertion point in 1 family file):**
1. `registry/_<family>.py` — ONE `RegistryEntry(...)` with full inline
   metadata (set `showcase_module` to auto-appear on MCP surface)

---

## Post-Refactor: Documentation Updates

> Assessment: Mostly agree.
> The documentation follow-up is thoughtful and necessary. I would explicitly add `DESIGN.md` and `CHANGELOG.md` here so the plan matches the repository rules for architecture and behavior changes.

After Track B lands, update project documentation:

### New files

> Assessment: Agree.
> A dedicated registry guide and agent-specific registry instructions fit the existing repository pattern well. This is a good way to preserve the intent of the refactor after the monolith is split.

**`.codex/registry.md`** — deep guide for the registry package structure,
conventions, and field semantics.

**`.codex/agent/registry.md`** — specialist role prompt (same pattern as
`.codex/agent/task.md` and `.codex/agent/workflow.md`) for agents adding
new pipelines or entries:
- **Purpose**: Use when adding/modifying entries in `src/flytetest/registry/`
- **Read First**: `AGENTS.md`, `DESIGN.md`, `.codex/registry.md`,
  the target family file, `mcp_contract.py` if setting `showcase_module`
- **Role**: Register new biological stages with complete, self-contained
  metadata — one entry per task/workflow, all compatibility + resources inline
- **Core Principles**:
  1. Every entry must have accurate `accepted_planner_types`/`produced_planner_types`
     for the type graph to compose correctly
  2. Set `pipeline_family` and `pipeline_stage_order` for correct pipeline sequencing
  3. Set `showcase_module` only when a local handler exists in `server.py`
  4. New pipeline families get their own `_<family>.py` file + import in `__init__.py`
  5. Do not duplicate entries across family files
- **Validation**: `python3 -m compileall`, full test suite,
  `get_pipeline_stages()` returns correct order
- **Handoff**: report entries added, pipeline family, type-graph connections,
  whether MCP surface was extended

### Updates to existing files

> Assessment: Mostly agree.
> Updating existing `.codex` references from the monolith path to the package path is necessary. I would also review any user-facing supported-target documentation so the new derived registry surface does not drift from how the MCP showcase is actually described.

**`AGENTS.md`** — add a **Project Structure** quick-map section (~30 lines).
Two-tier design: AGENTS.md = orientation layer (loaded every conversation),
`.codex/` guides = depth layer (read only when editing that area).
Sections: Registry package, Types, Tasks, Workflows, Core Concepts.

**`CLAUDE.md`** — add registry guide to specialist guides table.

**9 `.codex/` files** reference `src/flytetest/registry.py` as a monolith
path — update all to `src/flytetest/registry/` (package):

| File | Approximate lines to update |
|---|---|
| `.codex/workflows.md` | 21, 160 |
| `.codex/documentation.md` | 34 |
| `.codex/testing.md` | 18 |
| `.codex/code-review.md` | 32, 53 |
| `.codex/agent/workflow.md` | 19 |
| `.codex/agent/code-review.md` | 20, 50 |
| `.codex/agent/test.md` | 22, 50 |
| `.codex/agent/architecture.md` | 71, 123 |
| `.codex/agent/README.md` | 40 |

(Line numbers are approximate — verify at implementation time.)

---

## Verification

> Assessment: Mostly agree.
> The compile, test, and grep checks are good baseline gates. I would add explicit assertions that the current supported runnable targets remain unchanged after the MCP derivation steps, and serializer regression fixtures that prove specs, planner types, and assets still preserve their current behavior.

After each step:
1. `python3 -m compileall src/flytetest/` — no import errors
2. `python3 -m unittest discover -s tests` — full suite passing (421 tests as of 2026-04-16)
3. Step-specific `rg` checks:
   - After A4: `rg "def _serialize|def _deserialize" src/flytetest/` — only
     in `serialization.py` (plus unrelated helpers in `spec_executor.py`,
     `server.py`, `planning.py` that are not part of this refactor)
   - After B2: `rg "_WORKFLOW_COMPATIBILITY_METADATA|_WORKFLOW_LOCAL_RESOURCE|_WORKFLOW_SLURM" src/flytetest/` — 0 hits
   - After B3: `rg "ShowcaseTarget(" src/flytetest/mcp_contract.py` — 0 hits
     (all derived from registry)
   - After B2: verify entry count: `python3 -c "from flytetest.registry import REGISTRY_ENTRIES; print(len(REGISTRY_ENTRIES))"` — must be 73
