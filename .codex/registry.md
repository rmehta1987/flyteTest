# Registry Guide

This file is the deep reference for the `src/flytetest/registry/` package.

## Purpose

Use this guide when:

- adding a new registry entry to an existing family file
- creating a new pipeline family file
- understanding how `showcase_module` controls MCP exposure
- understanding how `pipeline_family` and `pipeline_stage_order` drive pipeline
  sequencing

## Package Structure

The registry is a package, not a monolith. Each pipeline family lives in its
own private submodule:

```
src/flytetest/registry/
  __init__.py              # public surface: REGISTRY_ENTRIES, query functions, re-exports
  _types.py                # RegistryEntry, RegistryCompatibilityMetadata, InterfaceField, Category
  _transcript_evidence.py  # 8 entries: transcript evidence generation family
  _consensus.py            # 16 entries: PASA/TransDecoder consensus family
  _protein_evidence.py     # 6 entries: Exonerate protein-evidence family
  _annotation.py           # 5 entries: BRAKER3 ab initio annotation family
  _evm.py                  # 12 entries: EVM consensus preparation and execution
  _postprocessing.py       # 21 entries: repeat filtering, QC, functional annotation, AGAT, table2asn
  _rnaseq.py               # 5 entries: RNA-seq QC and quantification
  _variant_calling.py      # GATK4 germline variant calling family (skeleton; entries added in Steps 03–09)
  _gatk.py                 # catalog-only placeholder — reference example only, not imported
```

`REGISTRY_ENTRIES` is the concatenation of all family tuples in `__init__.py`.

### Public surface

All of the following continue to work via `from flytetest.registry import ...`:

- `REGISTRY_ENTRIES` — full ordered tuple of all entries
- `list_entries()` — list entries as plain dicts, optionally filtered by category
- `get_entry(name)` — look up one entry by name; raises `KeyError` on miss
- `get_pipeline_stages(family)` — ordered list of `(name, biological_stage)` for a
  pipeline family
- `RegistryEntry`, `RegistryCompatibilityMetadata`, `InterfaceField`, `Category`

## Field Semantics

### `RegistryEntry`

| Field | Type | Required | Purpose |
|---|---|---|---|
| `name` | `str` | yes | Unique identifier; must match the registered workflow or task name |
| `category` | `"workflow"` or `"task"` | yes | Entry type |
| `description` | `str` | yes | Human-readable summary used in catalog output and prompts |
| `inputs` | `tuple[InterfaceField, ...]` | yes | Named inputs with type hints and descriptions |
| `outputs` | `tuple[InterfaceField, ...]` | yes | Named outputs with type hints and descriptions |
| `tags` | `tuple[str, ...]` | yes | Searchable keyword labels |
| `compatibility` | `RegistryCompatibilityMetadata` | no | Planner and pipeline metadata; defaults to empty |
| `showcase_module` | `str` | no | Import path of the implementation module; empty string means not on MCP surface |

### `RegistryCompatibilityMetadata`

| Field | Default | Purpose |
|---|---|---|
| `biological_stage` | `"unspecified"` | Human-readable name for the pipeline position |
| `accepted_planner_types` | `()` | Planner dataclass names this entry can consume |
| `produced_planner_types` | `()` | Planner dataclass names this entry emits |
| `reusable_as_reference` | `False` | Whether outputs can be reused as an upstream reference |
| `execution_defaults` | `{}` | Default profile, resources, manifest key, and Slurm hints |
| `supported_execution_profiles` | `("local",)` | Which profiles the entry supports |
| `runtime_image_policy` | prose | Notes on optional SIF path inputs |
| `synthesis_eligible` | `False` | Whether the planner may include this in a composed plan |
| `composition_constraints` | `()` | Human-readable notes about what this entry requires or defers |
| `pipeline_family` | `""` | Groups entries across families; drives `get_pipeline_stages()` |
| `pipeline_stage_order` | `0` | Sort key within the family; lower = earlier in the pipeline |

### `InterfaceField`

| Field | Purpose |
|---|---|
| `name` | Parameter name as it appears in the task or workflow signature |
| `type` | Type hint string (`"File"`, `"Dir"`, `"str"`, `"int"`, `"list[File]"`, etc.) |
| `description` | One sentence describing the expected content and provenance |

## How to Add a New Entry

### Adding to an existing family

1. Open the appropriate family file (e.g. `_postprocessing.py`).
2. Add a `RegistryEntry(...)` tuple element.
3. Fill in all required fields. Include `compatibility=RegistryCompatibilityMetadata(...)`
   if the entry has a `pipeline_family` or resource defaults.
4. Set `showcase_module` only if you also add a handler in `server.py`.
5. Run `python3 -m compileall src/flytetest/registry/ -q` and the full test suite.

### Creating a new pipeline family

1. Create `src/flytetest/registry/_<family>.py` following the pattern of an
   existing family file.
2. Define `<FAMILY>_ENTRIES: tuple[RegistryEntry, ...] = (...)`.
3. In `src/flytetest/registry/__init__.py`:
   - Add `from flytetest.registry._<family> import <FAMILY>_ENTRIES`
   - Add `+ <FAMILY>_ENTRIES` to the `REGISTRY_ENTRIES` concatenation
4. Verify with:
   ```python
   python3 -c "from flytetest.registry import REGISTRY_ENTRIES, get_pipeline_stages; print(len(REGISTRY_ENTRIES))"
   ```

## Adding a Pipeline Family (End-to-End Walkthrough)

**Family-extensibility contract:** plugging in a new pipeline family must be
a self-contained change that lands under `src/flytetest/registry/_<family>.py`
plus `planner_types.py` plus `src/flytetest/tasks/` plus
`src/flytetest/workflows/` plus (optionally) `src/flytetest/bundles.py`.
Nothing in `mcp_contract.py`, `server.py`, or `planning.py` should need to
grow a branch for the new family.  If a family proposal wants an MCP-layer
edit, treat that as a sign the planner-type or registry model is missing a
generalization — push the fix there instead.

Worked example: the GATK4 variant-calling placeholder entry in
`_gatk.py` (`gatk_haplotype_caller`, `showcase_module=""`).  It is a
reference-only file showing the catalog-only shape; the live family is
`_variant_calling.py` (wired into `REGISTRY_ENTRIES` via `VARIANT_CALLING_ENTRIES`).

Steps to add a new family (`<family>`):

1. **Planner types.**  Add typed dataclasses to
   `src/flytetest/planner_types.py` that name the biology concepts the family
   produces and consumes (e.g. `AlignedReadSet`, `VariantCallSet`).  Reuse an
   existing type whenever the biology already has one; only introduce a new
   type when the biological meaning is genuinely new.
2. **Tasks.**  Add `src/flytetest/tasks/<family>.py` following `.codex/tasks.md`.
   Tasks must expose `MANIFEST_OUTPUT_KEYS` at module level so the
   registry-manifest contract test can validate them.
3. **Workflows.**  Add `src/flytetest/workflows/<family>.py` following
   `.codex/workflows.md`.  Workflows consume scalar `inputs` and typed
   `bindings` only at the MCP boundary; internal stage assembly stays inside
   the workflow.
4. **Registry family file.**  Add `src/flytetest/registry/_<family>.py` and
   re-export `<FAMILY>_ENTRIES` through `registry/__init__.py` per the section
   above.  For each entry:
   - Set `accepted_planner_types` and `produced_planner_types` to the exact
     dataclass names from step 1.
   - Set `pipeline_family=<family>` and `pipeline_stage_order` leaving gaps
     for later insertion.
   - Seed `execution_defaults` with `runtime_images`, `tool_databases`, and
     `slurm_resource_hints` if the family has real container / database /
     resource defaults.  `queue` and `account` MUST NOT be seeded — those
     always come from the user.
   - Set `showcase_module` to the implementation module path only when the
     entry has a handler in `_local_node_handlers()`.  Leave it empty for
     catalog-only placeholders (GATK pattern).
5. **Optional bundle.**  If the family has a turn-key starter fixture set,
   append a `ResourceBundle(...)` to `BUNDLES` in
   `src/flytetest/bundles.py`.  Bundle availability is checked at call time
   (not at import), so a bundle whose backing data is missing from disk does
   not prevent server startup.
6. **Verify.**
   ```bash
   python3 -m compileall src/flytetest/ -q
   python3 -c "from flytetest.registry import REGISTRY_ENTRIES, get_pipeline_stages; \
     print(len(REGISTRY_ENTRIES), get_pipeline_stages('<family>'))"
   pytest tests/test_registry_manifest_contract.py tests/test_bundles.py
   ```

If the walkthrough starts pushing edits into `mcp_contract.py`, `server.py`,
or `planning.py` to handle the new family, stop — that is the signal to
generalize a planner type or a registry field rather than branching the MCP
layer.

## How `showcase_module` Controls MCP Exposure

`mcp_contract.py` derives `SHOWCASE_TARGETS` by iterating `REGISTRY_ENTRIES` and
yielding one `ShowcaseTarget` for each entry where `showcase_module != ""`:

```python
SHOWCASE_TARGETS = tuple(
    ShowcaseTarget(
        name=entry.name,
        category=entry.category,
        module_name=entry.showcase_module,
        source_path=_resolve_source_path(entry.showcase_module),
    )
    for entry in REGISTRY_ENTRIES
    if entry.showcase_module
)
```

Setting `showcase_module` alone is **not sufficient** to make a workflow
MCP-runnable. You must also:

1. Add a handler in `_local_node_handlers()` in `server.py` (because
   `SUPPORTED_WORKFLOW_NAMES` and `SUPPORTED_TASK_NAMES` are now derived from
   `SHOWCASE_TARGETS`, the handler map is automatically populated — but only
   after the showcase target appears in the derived tuples).
2. Add planning coverage in `planning.py` if the target needs typed planning.
3. Add `TASK_PARAMETERS` entry in `server.py` for tasks that have parameter
   validation schemas.

For catalog-only placeholder entries (e.g. `gatk_haplotype_caller`), leave
`showcase_module=""`.

## How `pipeline_family` and `pipeline_stage_order` Drive Sequencing

`get_pipeline_stages(family)` returns entries where
`compatibility.pipeline_family == family`, sorted by `pipeline_stage_order`:

```python
# Example
>>> get_pipeline_stages("annotation")
[
    ("transcript_evidence_generation", "transcript evidence generation"),
    ("pasa_transcript_alignment", "PASA transcript alignment"),
    ...
    ("annotation_postprocess_table2asn", "NCBI submission preparation"),
]
```

Use `pipeline_stage_order` integers that leave gaps between families so new
stages can be inserted later without renumbering. The annotation pipeline uses
1–15; the variant-calling family starts at 3.

## `to_dict()` and Serialization

`RegistryEntry.to_dict()` excludes `showcase_module` from the output. This
keeps the public serialized shape stable for downstream consumers (MCP tool
responses, list_entries output). Do not rely on `showcase_module` being present
in dict output.

## Conventions

- Private submodules are named `_<family>.py` with a leading underscore.
- The exported tuple constant is named `<FAMILY>_ENTRIES` in SCREAMING_SNAKE_CASE.
- All entries in a family file share the same `pipeline_family` value.
- Descriptions are single sentences or short paragraphs; no bullet lists.
- Tags use kebab-case for multi-word labels.
