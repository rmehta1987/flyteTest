# Serialization Consolidation + Registry Restructure Checklist

This checklist tracks the serialization consolidation (Track A) and registry
package restructure (Track B) described in
`docs/dataserialization/serialization_registry_restructure_plan.md`.

It is separate from `docs/realtime_refactor_checklist.md`, which tracks
platform architecture milestones. This checklist tracks structural cleanup
that unblocks GATK pipeline expansion.

Use this file as the canonical shared tracker for this refactor.
Future sessions should mark completed tasks, record partial progress, and
note blockers here.

Keep this checklist short and scannable.
Detailed implementation plans live in
`docs/dataserialization/serialization_registry_restructure_plan.md`.
Submission prompts live under `docs/dataserialization/prompts/`.

## Branch

All work on branch `refactor/serialization-registry` (create from `main`).

## Status Labels

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

## Compatibility Guardrails

The refactor must preserve these surfaces throughout:

- `src/flytetest/registry.py` (now `src/flytetest/registry/`)
  Current listing helpers (`list_entries`, `get_entry`, `get_pipeline_stages`)
  stay callable. `REGISTRY_ENTRIES` stays importable. `RegistryEntry.to_dict()`
  output shape is unchanged.
- `src/flytetest/mcp_contract.py`
  4 named policy constants (`SUPPORTED_WORKFLOW_NAME`,
  `SUPPORTED_PROTEIN_WORKFLOW_NAME`, `SUPPORTED_TASK_NAME`,
  `SUPPORTED_BUSCO_FIXTURE_TASK_NAME`) are preserved as explicit string
  assignments. `SUPPORTED_TARGET_NAMES` set is identical before and after.
- `src/flytetest/server.py`
  MCP tool names, resource URIs, and `TASK_PARAMETERS` are unchanged.
  Handler dispatch covers the same set of targets.
- `src/flytetest/planning.py`
  No modifications in this refactor. Prompt classification behavior unchanged.
- Serialization round-trips
  All three layers (specs, planner types, assets) produce identical serialized
  output and accept identical deserialized input after rewiring.
- `run_manifest.json` wire format unchanged.

## Sequencing

```
Track A:  A0 -> A1 -> A2 -> A3 -> A4       (serialization, regression-gated)
Track B:  B1+B2 -> B3 -> B4 -> B5          (registry consolidation)
```

**Tracks A and B are fully independent.** They touch different files, have no
shared prerequisites, and can be developed, reviewed, and merged as separate
PRs with no ordering constraint between them. Only the steps *within* each
track have sequential dependencies (A0 gates A1-A4; B1+B2 gates B3-B5).

B1+B2 is one atomic commit (no intermediate `_registry_legacy.py`).

Recommended merge order: A0, A1, B1+B2, A2-A4, B3, B4, B5, Docs

---

## Track A: Serialization Consolidation

### Step A0 — Regression Fixtures

Goal: Lock current serialization behavior with snapshot tests before any rewiring.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_A0_regression_fixtures_prompt.md`

- [ ] Create `tests/fixtures/` directory
- [ ] Create and commit `tests/fixtures/run_manifest_regression.json` (sanitized from a real manifest under `results/`)
- [ ] Create `tests/test_serialization_regression.py`
- [ ] Spec layer snapshot: serialize representative spec, assert exact output
- [ ] Planner layer snapshot: round-trip planner type, assert field equality
- [ ] Asset layer snapshot: serialize manifest asset, assert exact JSON output
- [ ] Asset reload-from-disk: test loading committed fixture, assert expected asset objects
- [ ] Edge cases: None/Optional, Path, tuple, nested dataclass
- [ ] Full test suite passes alongside new tests
- [ ] `CHANGELOG.md` updated

### Acceptance evidence

- `tests/test_serialization_regression.py` exists with passing tests
- Tests cover all three serialization layers
- `tests/fixtures/run_manifest_regression.json` committed (portable, no absolute paths)

### Compatibility risks

- Snapshot tests that are too brittle (field ordering, float precision)
- Missing edge cases that only surface during A2-A4 rewiring

---

### Step A1 — Shared Serialization Module

Goal: Create `src/flytetest/serialization.py` with shared primitives and
layer-specific wrappers, independently testable.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_A1_serialization_module_prompt.md`

- [ ] Create `src/flytetest/serialization.py`
- [ ] Shared primitives: `_is_optional`, `_serialize_core`, `_deserialize_core`
- [ ] Layer-specific serialize wrappers: `serialize_value_plain`, `serialize_value_with_dicts`, `serialize_value_full`
- [ ] Layer-specific deserialize wrappers: `deserialize_value_strict`, `deserialize_value_coercing`
- [ ] `SerializableMixin` class (plain class, not dataclass)
- [ ] Create `tests/test_serialization.py` with edge-case round-trips
- [ ] Tests cover both deserializer variants
- [ ] A0 regression fixtures still pass
- [ ] Full test suite passes
- [ ] `CHANGELOG.md` updated

### Acceptance evidence

- `src/flytetest/serialization.py` is independently testable
- `tests/test_serialization.py` covers Path, nested dataclass, Optional, tuple, dict, scalar coercion, None
- No existing serialization code was modified

### Compatibility risks

- Behavioral mismatch between shared primitives and layer-specific originals
- MRO conflicts with frozen/slotted dataclass consumers

---

### Step A2 — Rewire specs.py

Goal: Remove duplicate serialization helpers from `specs.py`, wire to shared module.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_A2_A3_A4_rewire_serializers_prompt.md`

- [ ] Remove `_serialize()`, `_is_optional()`, `_deserialize()` from `specs.py`
- [ ] `SpecSerializable` uses `SerializableMixin` with `serialize_value_with_dicts` + `deserialize_value_strict`
- [ ] A0 regression fixtures pass
- [ ] Spec-specific tests pass: `test_specs`, `test_spec_artifacts`, `test_spec_executor`, `test_recipe_approval`

---

### Step A3 — Rewire planner_types.py

Goal: Remove duplicate serialization helpers from `planner_types.py`, wire to shared module.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_A2_A3_A4_rewire_serializers_prompt.md`

- [ ] Remove `_serialize_value()`, `_is_optional()`, `_deserialize_value()` from `planner_types.py`
- [ ] `PlannerSerializable` uses `SerializableMixin` with `serialize_value_plain` + `deserialize_value_strict`
- [ ] A0 regression fixtures pass
- [ ] Planner-specific tests pass: `test_planner_types`, `test_planning`

---

### Step A4 — Rewire types/assets.py

Goal: Remove duplicate serialization helpers from `types/assets.py`, wire to shared module.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_A2_A3_A4_rewire_serializers_prompt.md`

- [ ] Remove `_serialize_manifest_value()`, `_is_optional_manifest_type()`, `_deserialize_manifest_value()` from `types/assets.py`
- [ ] `ManifestSerializable` uses `SerializableMixin` with `serialize_value_full` + `deserialize_value_coercing`
- [ ] A0 regression fixtures pass (including manifest reload-from-disk)
- [ ] Full test suite passes
- [ ] `rg "def _serialize|def _deserialize" src/flytetest/` — only in `serialization.py` + unrelated helpers
- [ ] `CHANGELOG.md` updated

### Track A acceptance evidence

- Three duplicate `_serialize*`/`_deserialize*` helper sets eliminated
- All serialization flows through `src/flytetest/serialization.py`
- A0 regression fixtures pass at every step
- Full test suite passes (421+ tests)

---

## Track B: Registry Package Restructure

### Step B1+B2 — Registry Package (Atomic: Scaffold + Fold + Split)

Goal: Replace the `registry.py` monolith with a `registry/` package in one
atomic commit. Create the package structure, move dataclass definitions, add
`showcase_module` field, fold the 3 parallel dicts into self-contained entries,
split into 7 family files, and delete the monolith. No intermediate
`_registry_legacy.py` file.

Why atomic: Creating a `_registry_legacy.py` intermediate state is fragile —
if the session stalls or CI runs between scaffold and split, the legacy file
becomes a confusing artifact that invites accidental direct imports. The
monolith goes directly to package in one commit.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_B1_B2_registry_package_prompt.md`

Phase 1 — Package structure:
- [ ] Create `src/flytetest/registry/__init__.py`
- [ ] Create `src/flytetest/registry/_types.py` with dataclass definitions
- [ ] Add `showcase_module: str = ""` field to `RegistryEntry`
- [ ] Override `to_dict()` to exclude `showcase_module`

Phase 2 — Family files with self-contained entries:
- [ ] Create `_transcript_evidence.py` (8 entries)
- [ ] Create `_consensus.py` (16 entries)
- [ ] Create `_protein_evidence.py` (6 entries)
- [ ] Create `_annotation.py` (5 entries)
- [ ] Create `_evm.py` (12 entries)
- [ ] Create `_postprocessing.py` (21 entries)
- [ ] Create `_rnaseq.py` (5 entries)

Phase 3 — Wire up and delete monolith:
- [ ] `__init__.py` collects all family tuples + re-exports types + query functions
- [ ] Delete `src/flytetest/registry.py` (monolith)
- [ ] No `_registry_legacy.py` exists

Phase 4 — Verify:
- [ ] All existing `from flytetest.registry import ...` work (12 known consumers)
- [ ] `len(REGISTRY_ENTRIES) == 73`
- [ ] `to_dict()` output identical for all entries (no `showcase_module` leakage)
- [ ] `_WORKFLOW_COMPATIBILITY_METADATA`, `_WORKFLOW_LOCAL_RESOURCE_DEFAULTS`, `_WORKFLOW_SLURM_RESOURCE_HINTS` — 0 hits in codebase
- [ ] `get_pipeline_stages("annotation")` returns correct order
- [ ] Full test suite passes
- [ ] `CHANGELOG.md` updated

### Acceptance evidence

- `from flytetest.registry import ...` still works for all 12 existing consumers
- 7 family files, 73 total entries (8+16+6+5+12+21+5)
- 3 parallel dicts eliminated, `_backfill_workflow_compatibility_metadata()` eliminated
- All entries self-contained with inline compatibility metadata
- `to_dict()` output contains no `showcase_module` key
- No `_registry_legacy.py` file exists

### Compatibility risks

- Broken imports from consumers that use deep paths
- `to_dict()` shape change if `showcase_module` leaks into output
- Entry data drift during manual folding (mismatched resource values)
- Missing entries (count must total 73)

---

### Step B3 — Derive MCP Showcase Targets from Registry

Goal: Replace 12 hardcoded ShowcaseTarget entries with registry-derived targets.
Preserve 4 named policy constants.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_B3_B4_derive_mcp_and_server_prompt.md`

- [ ] Add `showcase_module` values to appropriate registry entries
- [ ] Derive `SHOWCASE_TARGETS` from `REGISTRY_ENTRIES`
- [ ] Delete 12 hardcoded `ShowcaseTarget(...)` blocks
- [ ] Delete 8 replaceable `SUPPORTED_*_NAME` constants
- [ ] Preserve 4 named policy constants as explicit string assignments
- [ ] Update `SHOWCASE_LIMITATIONS` name list (keep curated prose, review output)
- [ ] Safety test: derived `SUPPORTED_TARGET_NAMES` matches expected set
- [ ] MCP tests pass: `test_server`, `test_mcp_prompt_flows`

---

### Step B4 — Derive Server Handler Dispatch

Goal: Simplify `_local_node_handlers()` using derived workflow/task name tuples.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_B3_B4_derive_mcp_and_server_prompt.md`

- [ ] Update `server.py` imports (remove 8 deleted constants, add derived tuples)
- [ ] Replace explicit handler map with derived loop
- [ ] `TASK_PARAMETERS` stays manual (4 entries)
- [ ] Full test suite passes
- [ ] `CHANGELOG.md` updated

### Track B3-B4 acceptance evidence

- 0 hardcoded `ShowcaseTarget(...)` blocks in `mcp_contract.py`
- 4 policy constants preserved
- Derived target set identical to pre-refactor set
- Handler dispatch covers same targets

### Compatibility risks

- Deleting a policy constant that planning.py branches on
- Derived target set accidentally includes/excludes an entry

---

### Step B5 — GATK Proof of Concept

Goal: Demonstrate the new structure by adding a GATK entry in one file.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_B5_gatk_proof_of_concept_prompt.md`

- [ ] Create `src/flytetest/registry/_gatk.py` with `GATK_ENTRIES`
- [ ] Add import + concatenation in `__init__.py`
- [ ] GATK entry visible in `list_entries()` and `get_pipeline_stages("variant_calling")`
- [ ] GATK entry NOT in MCP showcase targets (showcase_module empty)
- [ ] `len(REGISTRY_ENTRIES) == 74`
- [ ] Full test suite passes
- [ ] `CHANGELOG.md` updated

### Acceptance evidence

- One file created, one line added to `__init__.py`
- Entry visible in catalog queries, invisible on MCP surface
- Demonstrates 1-file workflow registration

### Compatibility risks

- None significant — additive change only

---

## Post-Refactor Documentation

Goal: Update all project documentation to reflect the new structure.

Status: Not started

Prompt: `docs/dataserialization/prompts/step_post_refactor_docs_prompt.md`

- [ ] Create `.codex/registry.md` — registry package guide
- [ ] Create `.codex/agent/registry.md` — specialist role prompt
- [ ] Update `AGENTS.md` — add Project Structure quick-map section
- [ ] Update `CLAUDE.md` — add registry guide to specialist guides table
- [ ] Update `DESIGN.md` — reflect registry package split and serialization consolidation
- [ ] Update 9 `.codex/` files — change `registry.py` references to `registry/`
  - [ ] `.codex/workflows.md`
  - [ ] `.codex/documentation.md`
  - [ ] `.codex/testing.md`
  - [ ] `.codex/code-review.md`
  - [ ] `.codex/agent/workflow.md`
  - [ ] `.codex/agent/code-review.md`
  - [ ] `.codex/agent/test.md`
  - [ ] `.codex/agent/architecture.md`
  - [ ] `.codex/agent/README.md`
- [ ] `rg "src/flytetest/registry.py" .codex/ AGENTS.md CLAUDE.md DESIGN.md` — 0 hits
- [ ] `CHANGELOG.md` updated with comprehensive refactor entry

### Acceptance evidence

- `.codex/registry.md` and `.codex/agent/registry.md` exist
- 0 references to `registry.py` monolith path in documentation
- AGENTS.md has Project Structure section

---

## Final Verification

After all steps complete:

1. `python3 -m compileall src/flytetest/` — no import errors
2. `python3 -m unittest discover -s tests` — full suite passes
3. `python3 -c "from flytetest.registry import REGISTRY_ENTRIES; print(len(REGISTRY_ENTRIES))"` — 74
4. `rg "def _serialize|def _deserialize" src/flytetest/` — only in `serialization.py` + unrelated helpers
5. `rg "_WORKFLOW_COMPATIBILITY_METADATA|_WORKFLOW_LOCAL_RESOURCE|_WORKFLOW_SLURM" src/flytetest/` — 0 hits
6. `rg "ShowcaseTarget(" src/flytetest/mcp_contract.py` — 0 hits
7. `rg "src/flytetest/registry.py" .codex/ AGENTS.md CLAUDE.md DESIGN.md` — 0 hits

## Before vs After Summary

**Before:** 6 insertion points across 2 files to add one workflow.
**After:** 1 insertion point in one family file.
