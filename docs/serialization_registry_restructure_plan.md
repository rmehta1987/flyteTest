# Serialization Consolidation + Registry Package Restructure

**Date:** 2026-04-16
**Status:** Final draft — ready for implementation
**Branch:** Create a new branch from `main` (e.g. `refactor/serialization-registry`)
**Prerequisite:** M23-26 complete (generic asset subclasses landed)

---

## Context

Two problems block easy GATK pipeline expansion:

1. **Serialization duplication** — Three modules each maintain ~80 lines of
   near-identical `_serialize*`/`_deserialize*` helpers. New types must pick
   which to inherit, and subtle behavioral differences cause round-trip bugs.

2. **Manual registration explosion** — Adding ONE workflow requires 6+
   insertion points across 2 files (`registry.py` x4 dicts,
   `mcp_contract.py` x2). GATK variant calling could add 10+ workflows;
   this doesn't scale.

### Design Rationale

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

| File | Role | Lines |
|---|---|---|
| `src/flytetest/registry.py` | Monolith: 73 entries + 3 parallel dicts + query functions | 2679 |
| `src/flytetest/specs.py` | `SpecSerializable` mixin, `_serialize`/`_deserialize` (lines 22-103) | 331 |
| `src/flytetest/planner_types.py` | `PlannerSerializable` mixin, `_serialize_value`/`_deserialize_value` (lines 38-109) | 308 |
| `src/flytetest/types/assets.py` | `ManifestSerializable` mixin (superset), `_serialize_manifest_value`/`_deserialize_manifest_value` (lines 32-115) | 903 |
| `src/flytetest/mcp_contract.py` | 12 hardcoded `ShowcaseTarget` entries + `SUPPORTED_*` constants | 310 |
| `src/flytetest/server.py` | `_local_node_handlers()` dispatch, `TASK_PARAMETERS` | 3131 |
| `src/flytetest/planning.py` | Prompt classification, target-specific stage policy | -- |
| `src/flytetest/config.py` | `TaskEnvironmentConfig` entries (stays manual) | -- |

### Scope Boundaries

This refactor improves **catalog registration** (fewer insertion points per
workflow) and **serialization consistency** (one source of truth for
serialize/deserialize). It does **not** automatically make newly registered
workflows plannable or MCP-runnable. The following still require manual work
per new workflow:

- Prompt-classification heuristics in `planning.py`
- Target-specific execution guards and stage policy in `server.py`
- Runtime binding rules and example prompts in `mcp_contract.py`
- `TaskEnvironmentConfig` entries in `config.py`

---

## Track A: Serialization Consolidation

**Guiding principle:** Behavioral preservation matters more than deduplication.
The three serializers are similar but not identical. Each layer must retain its
current round-trip semantics after consolidation.

### Step A0 — Regression fixtures (prerequisite for all A steps)

Before touching any serializer, lock current behavior with snapshot tests:

- **Spec layer:** serialize a representative spec to dict, assert exact output.
- **Planner layer:** round-trip a planner type through `to_dict()`/`from_dict()`,
  assert field-level equality.
- **Asset layer:** serialize a representative manifest asset, assert exact JSON
  output. Also test reloading from a saved `run_manifest.json` fixture on disk
  (not just freshly serialized in-memory objects).

These fixtures gate all subsequent A steps — if a rewiring changes behavior,
the snapshot test catches it immediately.

**Files:** `tests/test_serialization_regression.py` (new)

### Step A1 — Create `src/flytetest/serialization.py`

New file with **shared primitives** plus **layer-specific wrappers**:

**Shared primitives** (used by all layers):
- `_is_optional(annotation)` — shared Optional unwrapping logic
- `_serialize_core(value)` — Path->str, tuple->list, dataclass
  field-by-field, scalar passthrough. This is the **common subset** that
  all three current serializers share.
- `_deserialize_core(annotation, value)` — None/Any passthrough, Path,
  tuple, Optional unwrapping, dataclass `from_dict()` with field-by-field
  fallback. Common subset of all three current deserializers.

**Layer-specific serializers** (preserve current behavioral differences):

The three current serializers differ on both serialize and deserialize:

| Capability | Planner | Specs | Assets |
|---|---|---|---|
| Dict recursion (serialize) | No | Yes | Yes |
| `to_dict()` fallback (serialize) | No | No | Yes |
| Scalar coercion (deserialize) | No | No | Yes |
| Dict recursion (deserialize) | No | Yes | Yes |

Layer wrappers preserve these exact behaviors:

- `serialize_value_plain(value)` — for planner types: Path, tuple,
  dataclass field-by-field only. No dict recursion.
- `serialize_value_with_dicts(value)` — for specs: adds dict recursion.
- `serialize_value_full(value)` — for assets: adds dict recursion +
  `to_dict()` fallback on nested dataclasses.
- `deserialize_value_strict(annotation, value)` — for specs and planner
  types: delegates to `_deserialize_core` without scalar coercion.
- `deserialize_value_coercing(annotation, value)` — for assets only:
  adds scalar coercion (str/int/bool). Preserves `ManifestSerializable`
  behavior.

**Mixin:**
- `class SerializableMixin` — plain class (not dataclass), provides
  `to_dict()`/`from_dict()` via `dataclasses.fields(self)` iteration.
  Subclasses override `_deserialize_field` to select strict vs coercing.
  Works with `@dataclass(frozen=True, slots=True)` consumers via MRO.

Create `tests/test_serialization.py` with edge-case round-trips (Path,
nested dataclass, Optional, tuple, dict, scalar coercion, None) testing
**both** deserializer variants.

**Files:** `src/flytetest/serialization.py` (new), `tests/test_serialization.py` (new)

### Step A2 — Rewire `specs.py`

Remove `_serialize()`, `_deserialize()`, `_is_optional()` (lines 22-103).
`SpecSerializable` becomes a thin subclass of `SerializableMixin` using
`deserialize_value_strict` — preserving current spec deserialize semantics
(no scalar coercion, no dict recursion beyond what specs already handle).

Must pass the A0 regression fixtures unchanged.

**Validation:** `python3 -m unittest tests.test_serialization_regression tests.test_specs tests.test_spec_artifacts tests.test_spec_executor tests.test_recipe_approval`

### Step A3 — Rewire `planner_types.py`

Remove `_serialize_value()`, `_deserialize_value()`, `_is_optional()` (lines 38-109).
`PlannerSerializable` becomes a thin subclass of `SerializableMixin` using
`deserialize_value_strict` — preserving current planner round-trip behavior.

Must pass the A0 regression fixtures unchanged.

**Validation:** `python3 -m unittest tests.test_serialization_regression tests.test_planner_types tests.test_planning`

### Step A4 — Rewire `types/assets.py`

Remove `_serialize_manifest_value()`, `_deserialize_manifest_value()`,
`_is_optional_manifest_type()` (lines 32-115). `ManifestSerializable` becomes
a thin subclass of `SerializableMixin` using `deserialize_value_coercing` —
preserving current asset behavior including scalar coercion.

Must pass the A0 regression fixtures unchanged, **including** the manifest
reload-from-disk test.

**Validation:** Full suite `python3 -m unittest discover -s tests`, plus
A0 manifest reload fixture.

---

## Track B: Registry Package (Fold Dicts + Split By Pipeline Family)

### Design

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

Create the package with two files first:

**`_types.py`** — move the pure dataclass definitions from `registry.py`:
- `Category` type alias (line 15)
- `InterfaceField` (line 19)
- `RegistryCompatibilityMetadata` (line 32)
- `RegistryEntry` (line 54)
- Add `showcase_module: str = ""` as a **new field on `RegistryEntry`**
  (not on `RegistryCompatibilityMetadata`). MCP exposure is a separate
  concern from planner/type-graph behavior.
- **`to_dict()` compatibility:** `RegistryEntry.to_dict()` currently uses
  `asdict(self)`, which serializes all fields. Adding `showcase_module`
  changes the payload shape. To preserve compatibility, override `to_dict()`
  to exclude `showcase_module` from the serialized output (it is internal
  infrastructure metadata, not part of the catalog entry's public payload).
  Add a separate `showcase_module` property or access it directly on the
  dataclass — callers that need it (B3) read the field, not the dict.

**`__init__.py`** — re-export everything from `_types.py` plus the query
functions (`list_entries`, `get_entry`, `get_pipeline_stages`). For now,
still import the entries from the old `registry.py` so nothing breaks.

Rename old `src/flytetest/registry.py` to `src/flytetest/_registry_legacy.py`
temporarily, import from it in the new `__init__.py`.

**Note:** B1 and B2 are not purely mechanical — moving metadata into entries
changes the shape of `RegistryEntry.to_dict()` output. Verify that any
downstream consumers (tests, MCP tools that serialize entries) still receive
the expected payload shape.

**Files:** `src/flytetest/registry/` (new package)
**Validation:** `python3 -m compileall src/flytetest/` + full test suite.
All existing `from flytetest.registry import ...` must still work.

### Step B2 — Fold parallel dicts into entries and split by family

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
        ),
        showcase_module="flytetest.workflows.annotation",
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
73 entries with identical `to_dict()` output. `get_pipeline_stages("annotation")`
must return same order. Verify any test or MCP tool that serializes
`RegistryEntry` still produces expected payloads.

### Step B3 — Derive `mcp_contract.py` showcase targets from registry

The `showcase_module` field on `RegistryEntry` (added in B1) replaces
the 12 hardcoded `ShowcaseTarget` entries. Use a tested helper to resolve
both `module_name` and `source_path` consistently:

```python
from flytetest.registry import REGISTRY_ENTRIES


def _resolve_source_path(module_name: str) -> Path:
    """Resolve a dotted module name to its source file path."""
    relative = module_name.replace("flytetest.", "").replace(".", "/")
    return (_PACKAGE_ROOT / relative).with_suffix(".py")


SHOWCASE_TARGETS: tuple[ShowcaseTarget, ...] = tuple(
    ShowcaseTarget(
        name=e.name,
        category=e.category,
        module_name=e.showcase_module,
        source_path=_resolve_source_path(e.showcase_module),
    )
    for e in REGISTRY_ENTRIES
    if e.showcase_module
)
SUPPORTED_TARGET_NAMES = tuple(t.name for t in SHOWCASE_TARGETS)
SUPPORTED_WORKFLOW_NAMES = tuple(
    t.name for t in SHOWCASE_TARGETS if t.category == "workflow"
)
SUPPORTED_TASK_NAMES = tuple(
    t.name for t in SHOWCASE_TARGETS if t.category == "task"
)
```

Delete the 12 hardcoded `ShowcaseTarget(...)` blocks.

Derive `SHOWCASE_LIMITATIONS` strings dynamically from
`SUPPORTED_TARGET_NAMES` instead of hardcoding the name list.

**Named constants that MUST be preserved as policy seams:**

The following named constants are used as policy branch points in
`planning.py` and `server.py` — they cannot be deleted or replaced
with derived tuples because code branches on them by identity:

| Constant | Used in |
|---|---|
| `SUPPORTED_WORKFLOW_NAME` | `planning.py` (prompt classification, BRAKER3 evidence guard, input extraction, assumptions), `server.py` (default workflow, evidence validation) |
| `SUPPORTED_PROTEIN_WORKFLOW_NAME` | `planning.py` (protein workflow classification, input extraction, assumptions) |
| `SUPPORTED_TASK_NAME` | `planning.py` (task intent classification, assumptions) |
| `SUPPORTED_BUSCO_FIXTURE_TASK_NAME` | `planning.py` (BUSCO fixture goal construction) |

These stay as explicit named constants in `mcp_contract.py`. The 8 other
`SUPPORTED_*_NAME` constants (BUSCO_WORKFLOW, EGGNOG, AGAT x3, TABLE2ASN,
FASTQC, GFFREAD) are only used in the handler map and `ShowcaseTarget`
construction — those can be replaced by derived `SUPPORTED_WORKFLOW_NAMES`
and `SUPPORTED_TASK_NAMES` tuples.

**Important:** After this step, assert that the set of supported runnable
targets is identical to what existed before the derivation. A test should
compare the derived `SUPPORTED_TARGET_NAMES` against a hardcoded expected
tuple to catch accidental additions or removals.

What stays manual: the 4 named policy constants above, example prompts,
tool names, resource URIs, runtime binding rules.

**Files:** `src/flytetest/mcp_contract.py`
**Validation:** `python3 -m unittest tests.test_server tests.test_mcp_prompt_flows`

### Step B4 — Derive `server.py` handler dispatch from the registry

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

**Note:** Target-specific validation guards, stage-to-input translation
logic, and execution policy elsewhere in `server.py` and `planning.py`
still remain manual after this step. This change only simplifies the
handler map construction.

**Files:** `src/flytetest/server.py`
**Validation:** `python3 -m unittest tests.test_server`

### Step B5 — GATK proof of concept

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
        ),
        # showcase_module="" — no handler yet, not on MCP surface
    ),
)
```

Add one import + concatenation line in `__init__.py`. Shows up in
`list_entries()` and `get_pipeline_stages("variant_calling")` immediately.

**Important:** Setting `showcase_module` alone is **not** sufficient to make
a workflow fully MCP-runnable. The workflow also needs: a local execution
handler pattern that the generic `workflow_handler` supports, appropriate
prompt-classification coverage in `planning.py`, and any target-specific
validation guards in `server.py`. The `showcase_module` field only controls
whether the entry appears in the `SHOWCASE_TARGETS` list — it does not
bypass these other requirements.

---

## What Stays Manual

| Item | Why |
|---|---|
| `TaskEnvironmentConfig` entries in `config.py` | Flyte runtime config, not registry metadata |
| `TASK_PARAMETERS` in `server.py` (4 entries) | MCP tool-validation schemas, not biological metadata |
| Prompt-classification heuristics in `planning.py` | Target-specific stage policy, not derivable from catalog |
| Stage-to-input translation logic in `server.py` | Workflow-specific execution semantics |
| Target-specific validation guards (e.g. BRAKER3 evidence check) | Domain logic in `server.py` |
| Example prompts in `mcp_contract.py` | Handcrafted |
| Primary/default workflow choice (`SUPPORTED_WORKFLOW_NAME`) | Policy decision |
| Runtime binding rules in `mcp_contract.py` | Protocol documentation, not derivable |

---

## What Does NOT Change

- `run_manifest.json` wire format
- Flyte `@task`/`@workflow` signatures
- `spec_artifacts._json_ready()` and `_write_json_atomically()`
- Public API names (`REGISTRY_ENTRIES`, `list_entries`, `get_entry`, etc.)
- Prompt planning surface — newly registered workflows do not automatically
  become plannable or MCP-runnable

---

## Sequencing

```
Track A:  A0 -> A1 -> A2 -> A3 -> A4   (serialization, regression-gated)
Track B:  B1 -> B2 -> B3 -> B4 -> B5   (registry consolidation)

A and B are independent — can run in parallel.
A0 must complete before any A1-A4 rewiring begins.
B1+B2 fold data and split files — verify to_dict() output stability.
B3+B4 derive MCP/server surfaces — verify target sets unchanged.
B5 is the proof: GATK entry in one file, visible in catalog queries.
```

Recommended merge order: A0, A1, B1, B2, A2-A4, B3, B4, B5

A0 first (regression fixtures), then A1 (shared module) and B1 (package
scaffold) can proceed in parallel. B2 is the largest step — fold and split
all 73 entries.

---

## Before vs After: Adding a New Workflow

**Before (6 insertion points across 2 files for catalog registration):**
1. `registry.py` — `RegistryEntry(...)` block (~30 lines)
2. `registry.py` — `_WORKFLOW_COMPATIBILITY_METADATA[name]` (~15 lines)
3. `registry.py` — `_WORKFLOW_LOCAL_RESOURCE_DEFAULTS[name]` (1 line)
4. `registry.py` — `_WORKFLOW_SLURM_RESOURCE_HINTS[name]` (1 line)
5. `mcp_contract.py` — `ShowcaseTarget(...)` + `SUPPORTED_*` constant
6. `mcp_contract.py` — update limitation strings

**After (1 insertion point for catalog + MCP exposure):**
1. `registry/_<family>.py` — ONE `RegistryEntry(...)` with full inline
   metadata (set `showcase_module` to appear in MCP showcase target list)

**Still required for full MCP/planner support (unchanged by this refactor):**
- Prompt-classification coverage in `planning.py`
- Any target-specific execution guards in `server.py`
- `TaskEnvironmentConfig` in `config.py`

---

## Post-Refactor: Documentation Updates

After Track B lands, update project documentation:

### New files

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
  3. Set `showcase_module` only when the workflow is fully supported by the
     execution surface (handler, planning policy, validation guards)
  4. New pipeline families get their own `_<family>.py` file + import in `__init__.py`
  5. Do not duplicate entries across family files
- **Validation**: `python3 -m compileall`, full test suite,
  `get_pipeline_stages()` returns correct order
- **Handoff**: report entries added, pipeline family, type-graph connections,
  whether MCP surface was extended

### Updates to existing files

**`AGENTS.md`** — add a **Project Structure** quick-map section (~30 lines).
Two-tier design: AGENTS.md = orientation layer (loaded every conversation),
`.codex/` guides = depth layer (read only when editing that area).
Sections: Registry package, Types, Tasks, Workflows, Core Concepts.

**`CLAUDE.md`** — add registry guide to specialist guides table.

**`DESIGN.md`** — update architecture description to reflect the registry
package split and the serialization consolidation.

**`CHANGELOG.md`** — dated notes for this refactor per repository rules.

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

After each step:
1. `python3 -m compileall src/flytetest/` — no import errors
2. `python3 -m unittest discover -s tests` — full suite passing (421 tests as of 2026-04-16)
3. A0 regression fixtures pass at every A-step (behavioral preservation)
4. Step-specific checks:
   - After A4: `rg "def _serialize|def _deserialize" src/flytetest/` — only
     in `serialization.py` (plus unrelated helpers in `spec_executor.py`,
     `server.py`, `planning.py` that are not part of this refactor)
   - After B2: `rg "_WORKFLOW_COMPATIBILITY_METADATA|_WORKFLOW_LOCAL_RESOURCE|_WORKFLOW_SLURM" src/flytetest/` — 0 hits
   - After B2: `python3 -c "from flytetest.registry import REGISTRY_ENTRIES; print(len(REGISTRY_ENTRIES))"` — must be 73
   - After B3: `rg "ShowcaseTarget(" src/flytetest/mcp_contract.py` — 0 hits
     (all derived from registry)
   - After B3: assert derived `SUPPORTED_TARGET_NAMES` matches expected set
     (no accidental additions or removals)
