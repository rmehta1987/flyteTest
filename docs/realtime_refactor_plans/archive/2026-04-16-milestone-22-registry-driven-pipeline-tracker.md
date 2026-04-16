# Milestone 22: Registry-Driven Pipeline Tracker

Date: 2026-04-16
Status: Ready to implement

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 22

---

## Goal

Replace the hardcoded `ANNOTATION_PIPELINE_STAGES` list in `pipeline_tracker.py`
with a registry query. Add `pipeline_family` and `pipeline_stage_order` to
`RegistryCompatibilityMetadata` so each workflow declares which pipeline it
belongs to and its position within that pipeline. The tracker then derives stage
lists from the registry at import time.

This makes the tracker pipeline-agnostic: GATK, scRNA-seq, or any future
pipeline family self-registers by populating these two fields rather than
requiring a parallel hardcoded list.

---

## Background

`pipeline_tracker.py` (Milestone 21d) hardcodes 15 annotation workflow names as
`ANNOTATION_PIPELINE_STAGES`. The registry already has `biological_stage` labels
but lacks two things needed for a registry-driven tracker:

1. **`pipeline_family`** — no field distinguishes annotation workflows from
   standalone workflows (`busco_assess_proteins`, `rnaseq_qc_quant`) or future
   GATK workflows.
2. **`pipeline_stage_order`** — no integer gives deterministic ordering within
   a family. Topological sort from `accepted_planner_types` is ambiguous.

---

## Schema Change: RegistryCompatibilityMetadata

File: `src/flytetest/registry.py`

Add two fields to the frozen dataclass with safe defaults:

```python
pipeline_family: str = ""
pipeline_stage_order: int = 0
```

- `pipeline_family = ""` → standalone/utility workflow; excluded from all
  tracker queries automatically.
- `pipeline_stage_order = 0` → also excluded (used if a workflow is in a
  family but not a numbered pipeline stage).

### Annotation pipeline entries (`family = "annotation"`)

| workflow_name | stage_order |
|---|---|
| `transcript_evidence_generation` | 1 |
| `pasa_transcript_alignment` | 2 |
| `transdecoder_from_pasa` | 3 |
| `protein_evidence_alignment` | 4 |
| `ab_initio_annotation_braker3` | 5 |
| `consensus_annotation_evm_prep` | 6 |
| `consensus_annotation_evm` | 7 |
| `annotation_refinement_pasa` | 8 |
| `annotation_repeat_filtering` | 9 |
| `annotation_qc_busco` | 10 |
| `annotation_functional_eggnog` | 11 |
| `annotation_postprocess_agat` | 12 |
| `annotation_postprocess_agat_conversion` | 13 |
| `annotation_postprocess_agat_cleanup` | 14 |
| `annotation_postprocess_table2asn` | 15 |

### Standalone entries (keep defaults)

| workflow_name | pipeline_family |
|---|---|
| `busco_assess_proteins` | `""` |
| `rnaseq_qc_quant` | `""` |

---

## New Registry Function

Add to `src/flytetest/registry.py`:

```python
def get_pipeline_stages(family: str) -> list[tuple[str, str]]:
    """Return (workflow_name, biological_stage_label) pairs for a pipeline family.

    Entries are ordered by pipeline_stage_order.  Workflows with
    pipeline_family != family or pipeline_stage_order == 0 are excluded.
    Returns an empty list for unknown or empty family strings.
    """
```

- Pure function, no I/O, safe to call at module import time.
- Sources from `_WORKFLOW_COMPATIBILITY_METADATA` (the existing dict at line 2284).

---

## pipeline_tracker.py Changes

Remove the hardcoded literal list. Replace with:

```python
from flytetest.registry import get_pipeline_stages

ANNOTATION_PIPELINE_STAGES: list[tuple[str, str]] = get_pipeline_stages("annotation")
```

- `ANNOTATION_PIPELINE_STAGES` stays as the module-level public name — tests
  import it directly. The value changes from a literal to a registry-derived
  list, but the name is preserved.
- Remove the 15 individual `config.py` workflow name imports that become
  unnecessary once the names come from the registry.

---

## Files

All files listed here exist on `main` (confirmed). The current state is:
- Two milestone-22 plan docs exist side by side (conflict — resolved by renaming
  the old one to 23 as Step 1 below).
- Submission prompts exist for 22–25; no 26 exists yet and no new-22 prompt exists.

### Code changes

| File | Action |
|---|---|
| `src/flytetest/registry.py` | Edit — add fields to `RegistryCompatibilityMetadata`; populate 17 entries; add `get_pipeline_stages()` |
| `src/flytetest/pipeline_tracker.py` | Edit — replace hardcoded list with `get_pipeline_stages("annotation")` |
| `tests/test_pipeline_tracker.py` | Edit — add 3 new tests for `get_pipeline_stages` |
| `CHANGELOG.md` | Edit — add M22 entry |

### Doc changes (renaming + creating)

| Current state | Action |
|---|---|
| `docs/realtime_refactor_plans/2026-04-10-milestone-22-transdecoder-generic-asset-follow-up.md` | `git mv` → `...-milestone-23-...`; update title inside |
| `docs/realtime_refactor_plans/2026-04-10-milestone-23-protein-evidence-nested-asset-cleanup.md` | `git mv` → `...-milestone-24-...`; update title inside |
| `docs/realtime_refactor_plans/2026-04-10-milestone-24-pasa-refinement-asset-generalization-boundary.md` | `git mv` → `...-milestone-25-...`; update title inside |
| `docs/realtime_refactor_plans/2026-04-10-milestone-25-consensus-asset-generalization-boundary.md` | `git mv` → `...-milestone-26-...`; update title inside (**creates 26 for first time**) |
| `docs/realtime_refactor_plans/2026-04-16-milestone-22-registry-driven-pipeline-tracker.md` | **stays as-is** — this is the new Milestone 22 plan |
| `docs/realtime_refactor_milestone_22_submission_prompt.md` | `git mv` → `..._23_...`; update title inside |
| `docs/realtime_refactor_milestone_23_submission_prompt.md` | `git mv` → `..._24_...`; update title inside |
| `docs/realtime_refactor_milestone_24_submission_prompt.md` | `git mv` → `..._25_...`; update title inside |
| `docs/realtime_refactor_milestone_25_submission_prompt.md` | `git mv` → `..._26_...`; update title inside (**creates 26 for first time**) |
| _(does not exist)_ | **Create** `docs/realtime_refactor_milestone_22_submission_prompt.md` (content below) |
| `docs/realtime_refactor_checklist.md` | Rename `## Milestone 25→26`, `24→25`, `23→24`, `22→23` bottom-up; insert new `## Milestone 22` block |

### New Milestone 22 submission prompt content

```markdown
# Milestone 22 Submission Prompt: Registry-Driven Pipeline Tracker

Use the plan at
`docs/realtime_refactor_plans/2026-04-16-milestone-22-registry-driven-pipeline-tracker.md`
to implement Milestone 22.

Goal: add `pipeline_family` and `pipeline_stage_order` to
`RegistryCompatibilityMetadata`, populate all 17 existing entries, add
`get_pipeline_stages(family)` to `registry.py`, and replace the hardcoded
`ANNOTATION_PIPELINE_STAGES` list in `pipeline_tracker.py` with
`get_pipeline_stages("annotation")`.

See the plan doc for the full stage-order table, file list, compatibility risks,
and acceptance criteria.
```

---

## Compatibility Risks

- `RegistryCompatibilityMetadata` is a frozen dataclass in a
  compatibility-critical surface (listed in `.codex/agent/README.md`). The two
  new fields have safe defaults so all existing construction sites that omit them
  remain valid.
- `get_pipeline_stages` must be a pure function with no I/O so it is safe to
  call at module import time in `pipeline_tracker.py`.
- Do not remove `ANNOTATION_PIPELINE_STAGES` as a public name — tests import it
  directly.
- The ordered list produced by the registry must exactly match the 15-entry order
  previously hardcoded. Verify with a test before removing the hardcoded fallback.

---

## Tests to Add

In `tests/test_pipeline_tracker.py`:

```python
def test_get_pipeline_stages_returns_annotation_stages_in_order():
    stages = get_pipeline_stages("annotation")
    assert len(stages) == 15
    assert stages[0][0] == "transcript_evidence_generation"
    assert stages[-1][0] == "annotation_postprocess_table2asn"

def test_get_pipeline_stages_returns_empty_for_unknown_family():
    assert get_pipeline_stages("unknown") == []
    assert get_pipeline_stages("") == []

def test_standalone_workflows_excluded_from_annotation_pipeline():
    names = [name for name, _ in get_pipeline_stages("annotation")]
    assert "busco_assess_proteins" not in names
    assert "rnaseq_qc_quant" not in names
```

---

## Acceptance Criteria

- All existing tests pass; full suite stays green.
- `get_pipeline_stages("annotation")` returns 15 entries in the correct order.
- `get_pipeline_stages("")` and `get_pipeline_stages("unknown")` return `[]`.
- `ANNOTATION_PIPELINE_STAGES` in `pipeline_tracker.py` is registry-derived.
- The tracker still produces the same 15-stage checklist as before.
- Old milestones 22–25 are renumbered 23–26 consistently across plan docs,
  submission prompts, and the checklist.
- `CHANGELOG.md` updated.

---

## Handoff Prompt

```
Implement milestone 22: make the pipeline status tracker registry-driven.

Goal: replace the hardcoded ANNOTATION_PIPELINE_STAGES list in
src/flytetest/pipeline_tracker.py with a registry query, so future pipelines
(GATK, scRNA-seq) add themselves to the tracker by populating two new fields
in RegistryCompatibilityMetadata rather than requiring a parallel hardcoded list.

Plan doc: docs/realtime_refactor_plans/2026-04-16-milestone-22-registry-driven-pipeline-tracker.md

Order of changes:

1. Rename/bump old milestones 22-25 → 23-26 (docs only, no code).
   NOTE: The files to rename exist on the `realtime` branch, not on `main`.
   Switch to or work on `realtime` for this step.
   - git mv the 4 plan docs (22→23, 23→24, 24→25, 25→26) and the 4 submission
     prompts (22→23, 23→24, 24→25, 25→26). Milestone 26 is a new number.
   - Update milestone numbers in titles and self-references inside each renamed file.
   - Create NEW docs/realtime_refactor_milestone_22_submission_prompt.md
     (content in the plan doc under "New Milestone 22 submission prompt").
   - In docs/realtime_refactor_checklist.md: work bottom-up — rename
     ## Milestone 25 → 26 first, then 24→25, 23→24, 22→23. Insert new
     ## Milestone 22 block before the renamed Milestone 23.
   - The plan doc 2026-04-16-milestone-22-registry-driven-pipeline-tracker.md
     already exists on main and stays as-is.

2. src/flytetest/registry.py:
   - Add pipeline_family: str = "" and pipeline_stage_order: int = 0 to
     RegistryCompatibilityMetadata (frozen dataclass at line 32).
   - Populate all 17 _WORKFLOW_COMPATIBILITY_METADATA entries (line 2284):
     15 annotation entries get pipeline_family="annotation" and
     pipeline_stage_order=1..15 per the table in the plan doc.
     busco_assess_proteins and rnaseq_qc_quant keep defaults (family="").
   - Add get_pipeline_stages(family: str) -> list[tuple[str, str]]:
     pure function, no I/O, safe at import time.

3. src/flytetest/pipeline_tracker.py:
   - Replace hardcoded ANNOTATION_PIPELINE_STAGES with:
     ANNOTATION_PIPELINE_STAGES = get_pipeline_stages("annotation")
   - Remove the 15 config.py workflow name imports that are no longer needed.
   - Keep ANNOTATION_PIPELINE_STAGES as the public module-level name.

4. tests/test_pipeline_tracker.py:
   - Existing 11 tests should pass unchanged.
   - Add 3 tests: get_pipeline_stages_returns_annotation_stages_in_order,
     get_pipeline_stages_returns_empty_for_unknown_family,
     standalone_workflows_excluded_from_annotation_pipeline.

5. CHANGELOG.md — add dated M22 entry.

Key files:
- src/flytetest/registry.py — RegistryCompatibilityMetadata at line 32,
  _WORKFLOW_COMPATIBILITY_METADATA at line 2284 (17 entries)
- src/flytetest/pipeline_tracker.py — ANNOTATION_PIPELINE_STAGES at top

Read AGENTS.md before touching registry.py (compatibility-critical surface).
Read .codex/testing.md before writing tests.
Run python -m pytest tests/test_pipeline_tracker.py tests/test_server.py -v
before committing.
```
