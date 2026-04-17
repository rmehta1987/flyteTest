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

All work on branch `datatypes`.

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

Status: Complete

Prompt: `docs/dataserialization/prompts/step_A0_regression_fixtures_prompt.md`

- [x] Create `tests/fixtures/` directory
- [x] Create and commit `tests/fixtures/run_manifest_regression.json` (sanitized from a real manifest under `results/`)
- [x] Create `tests/test_serialization_regression.py`
- [x] Spec layer snapshot: serialize representative spec, assert exact output
- [x] Planner layer snapshot: round-trip planner type, assert field equality
- [x] Asset layer snapshot: serialize manifest asset, assert exact JSON output
- [x] Asset reload-from-disk: test loading committed fixture, assert expected asset objects
- [x] Edge cases: None/Optional, Path, tuple, nested dataclass
- [x] Full test suite passes alongside new tests (442 tests, 0 failures)
- [x] `CHANGELOG.md` updated

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

Status: Complete

Prompt: `docs/dataserialization/prompts/step_A1_serialization_module_prompt.md`

- [x] Create `src/flytetest/serialization.py`
- [x] Shared primitives: `_is_optional`, `_serialize_core`, `_deserialize_core`
- [x] Layer-specific serialize wrappers: `serialize_value_plain`, `serialize_value_with_dicts`, `serialize_value_full`
- [x] Layer-specific deserialize wrappers: `deserialize_value_strict`, `deserialize_value_coercing`
- [x] `SerializableMixin` class (plain class, not dataclass)
- [x] Create `tests/test_serialization.py` with edge-case round-trips (52 tests)
- [x] Tests cover both deserializer variants
- [x] A0 regression fixtures still pass
- [x] Full test suite passes (494 tests, 0 failures)
- [x] `CHANGELOG.md` updated

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

Status: Complete

Prompt: `docs/dataserialization/prompts/step_A2_A3_A4_rewire_serializers_prompt.md`

- [x] Remove `_serialize()`, `_is_optional()`, `_deserialize()` from `specs.py`
- [x] `SpecSerializable` uses `SerializableMixin` with `serialize_value_with_dicts` + `deserialize_value_strict`
- [x] A0 regression fixtures pass
- [x] Spec-specific tests pass: `test_specs`, `test_spec_artifacts`, `test_spec_executor`, `test_recipe_approval`

---

### Step A3 — Rewire planner_types.py

Goal: Remove duplicate serialization helpers from `planner_types.py`, wire to shared module.

Status: Complete

Prompt: `docs/dataserialization/prompts/step_A2_A3_A4_rewire_serializers_prompt.md`

- [x] Remove `_serialize_value()`, `_is_optional()`, `_deserialize_value()` from `planner_types.py`
- [x] `PlannerSerializable` uses `SerializableMixin` with `serialize_value_plain` + `deserialize_value_strict`
- [x] A0 regression fixtures pass
- [x] Planner-specific tests pass: `test_planner_types`, `test_planning`

---

### Step A4 — Rewire types/assets.py

Goal: Remove duplicate serialization helpers from `types/assets.py`, wire to shared module.

Status: Complete

Prompt: `docs/dataserialization/prompts/step_A2_A3_A4_rewire_serializers_prompt.md`

- [x] Remove `_serialize_manifest_value()`, `_is_optional_manifest_type()`, `_deserialize_manifest_value()` from `types/assets.py`
- [x] `ManifestSerializable` uses `SerializableMixin` with `serialize_value_full` + `deserialize_value_coercing`
- [x] A0 regression fixtures pass (including manifest reload-from-disk)
- [x] Full test suite passes (494 tests, 0 failures)
- [x] `rg "def _serialize|def _deserialize" src/flytetest/` — only in `serialization.py` + unrelated helpers
- [x] `CHANGELOG.md` updated

### Track A acceptance evidence

- Three duplicate `_serialize*`/`_deserialize*` helper sets eliminated
- All serialization flows through `src/flytetest/serialization.py`
- A0 regression fixtures pass at every step
- Full test suite passes (494 tests as of 2026-04-16)

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

Status: Complete (2026-04-16)

Prompt: `docs/dataserialization/prompts/step_B1_B2_registry_package_prompt.md`

Phase 1 — Package structure:
- [x] Create `src/flytetest/registry/__init__.py`
- [x] Create `src/flytetest/registry/_types.py` with dataclass definitions
- [x] Add `showcase_module: str = ""` field to `RegistryEntry`
- [x] Override `to_dict()` to exclude `showcase_module`

Phase 2 — Family files with self-contained entries:
- [x] Create `_transcript_evidence.py` (8 entries)
- [x] Create `_consensus.py` (16 entries)
- [x] Create `_protein_evidence.py` (6 entries)
- [x] Create `_annotation.py` (5 entries)
- [x] Create `_evm.py` (12 entries)
- [x] Create `_postprocessing.py` (21 entries)
- [x] Create `_rnaseq.py` (5 entries)

Phase 3 — Wire up and delete monolith:
- [x] `__init__.py` collects all family tuples + re-exports types + query functions
- [x] Delete `src/flytetest/registry.py` (monolith)
- [x] No `_registry_legacy.py` exists

Phase 4 — Verify:
- [x] All existing `from flytetest.registry import ...` work (12 known consumers)
- [x] `len(REGISTRY_ENTRIES) == 73`
- [x] `to_dict()` output identical for all entries (no `showcase_module` leakage)
- [x] `_WORKFLOW_COMPATIBILITY_METADATA`, `_WORKFLOW_LOCAL_RESOURCE_DEFAULTS`, `_WORKFLOW_SLURM_RESOURCE_HINTS` — 0 hits in codebase
- [x] `get_pipeline_stages("annotation")` returns correct order (15 stages)
- [x] Full test suite passes (494 tests, 1 skipped)
- [x] `CHANGELOG.md` updated

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

Status: Complete (2026-04-16)

Prompt: `docs/dataserialization/prompts/step_B3_B4_derive_mcp_and_server_prompt.md`

- [x] Add `showcase_module` values to appropriate registry entries
- [x] Derive `SHOWCASE_TARGETS` from `REGISTRY_ENTRIES`
- [x] Delete 12 hardcoded `ShowcaseTarget(...)` blocks
- [x] Delete 8 replaceable `SUPPORTED_*_NAME` constants
- [x] Preserve 4 named policy constants as explicit string assignments
- [x] Update `SHOWCASE_LIMITATIONS` name list (keep curated prose, review output)
- [x] Safety test: derived `SUPPORTED_TARGET_NAMES` matches expected set
- [x] MCP tests pass: `test_server`, `test_mcp_prompt_flows`

---

### Step B4 — Derive Server Handler Dispatch

Goal: Simplify `_local_node_handlers()` using derived workflow/task name tuples.

Status: Complete (2026-04-16)

Prompt: `docs/dataserialization/prompts/step_B3_B4_derive_mcp_and_server_prompt.md`

- [x] Update `server.py` imports (remove 8 deleted constants, add derived tuples)
- [x] Replace explicit handler map with derived loop
- [x] `TASK_PARAMETERS` stays manual (4 entries)
- [x] Full test suite passes (495 tests, 1 skipped)
- [x] `CHANGELOG.md` updated

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

Status: Complete (2026-04-16)

Prompt: `docs/dataserialization/prompts/step_B5_gatk_proof_of_concept_prompt.md`

- [x] Create `src/flytetest/registry/_gatk.py` with `GATK_ENTRIES`
- [x] Add import + concatenation in `__init__.py`
- [x] GATK entry visible in `list_entries()` and `get_pipeline_stages("variant_calling")`
- [x] GATK entry NOT in MCP showcase targets (showcase_module empty)
- [x] `len(REGISTRY_ENTRIES) == 74`
- [x] Full test suite passes (495 tests, 1 skipped)
- [x] `CHANGELOG.md` updated

### Acceptance evidence

- One file created, one line added to `__init__.py`
- Entry visible in catalog queries, invisible on MCP surface
- Demonstrates 1-file workflow registration

### Compatibility risks

- None significant — additive change only

---

## Post-Refactor Documentation

Goal: Update all project documentation to reflect the new structure.

Status: Complete (2026-04-16)

Prompt: `docs/dataserialization/prompts/step_post_refactor_docs_prompt.md`

- [x] Create `.codex/registry.md` — registry package guide
- [x] Create `.codex/agent/registry.md` — specialist role prompt
- [x] Update `AGENTS.md` — add Project Structure quick-map section
- [x] Update `CLAUDE.md` — add registry guide to specialist guides table
- [x] Update `DESIGN.md` — reflect registry package split and serialization consolidation
- [x] Update 9 `.codex/` files — change `registry.py` references to `registry/`
  - [x] `.codex/workflows.md`
  - [x] `.codex/documentation.md`
  - [x] `.codex/testing.md`
  - [x] `.codex/code-review.md`
  - [x] `.codex/agent/workflow.md`
  - [x] `.codex/agent/code-review.md`
  - [x] `.codex/agent/test.md`
  - [x] `.codex/agent/architecture.md`
  - [x] `.codex/agent/README.md`
- [x] `rg "src/flytetest/registry.py" .codex/ AGENTS.md CLAUDE.md DESIGN.md` — 0 hits
- [x] `CHANGELOG.md` updated with comprehensive refactor entry

### Acceptance evidence

- `.codex/registry.md` and `.codex/agent/registry.md` exist
- 0 references to `registry.py` monolith path in documentation
- AGENTS.md has Project Structure section

---

## Deferred TODOs

### Remove flyte_stub.py

Now that `flyte` (v2.1.2) is installed in the venv, the real `flyte.io.File` and
`flyte.io.Dir` are available. All task and test code already uses `File(path=str(...))`
keyword construction, which works with the real types. `Dir.download_sync()` returns
the same local path; `File.download_sync()` copies to a new temp path (minor behavioral
difference from the stub).

Work involved:
1. Remove per-file `from flyte_stub import install_flyte_stub; install_flyte_stub()` calls
   from every test file — redundant since `tests/__init__.py` already fires first under
   `python3 -m unittest discover`
2. Run the suite without the stub entirely (comment out the `tests/__init__.py` call);
   fix any File-path assertion failures from `File.download_sync()` copying to a new temp
   path instead of returning the original (expected to be small; `Dir.download_sync()`
   already returns the same local path)
3. If step 2 passes cleanly: delete `tests/flyte_stub.py` and gut `tests/__init__.py`

Note: `conftest.py` is NOT an option — we keep `python3 -m unittest discover` as the
runner. The `tests/__init__.py` hook is the correct place for any remaining setup.

Deferred because: nothing is currently broken; verification cost is non-trivial.
Do after B5 is complete.

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
