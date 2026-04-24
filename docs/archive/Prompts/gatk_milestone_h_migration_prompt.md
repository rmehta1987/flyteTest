# GATK Milestone H — Migration Prompt for Breaking Changes

**Run after Milestone H merges to `main`. Run before starting Milestone I.**

Milestone H intentionally introduced two breaking changes. This prompt
walks a follow-up session through migrating any consumer that depended
on the old shapes. The in-repo blast radius is small — most consumers
were already updated inside Milestone H itself — but external saved
recipes and any ad-hoc helpers may still reference the old shapes.

## Model

**Haiku 4.5** (`claude-haiku-4-5-20251001`) or **Sonnet 4.6**. Pure
search-and-replace with verification. Haiku is adequate; escalate to
Sonnet only if a conflict appears.

## Breaking Changes Recap

| # | Change | Where |
|---|---|---|
| 1 | Task-level manifests moved from `{results_dir}/run_manifest.json` to `{results_dir}/run_manifest_<stage>.json` | `src/flytetest/tasks/variant_calling.py` — all 16 tasks |
| 2 | `post_genotyping_refinement` no longer accepts `ref_path` | `src/flytetest/workflows/variant_calling.py`, registry, tests |

Workflow-level manifests at `{results_dir}/run_manifest.json` are
**unchanged**. Only per-task output directories now use the namespaced
filename.

## Goal

1. Verify nothing in the repo still reads task-level
   `run_manifest.json` from a task output directory as if it were the
   workflow manifest.
2. Verify no caller passes `ref_path=` to
   `post_genotyping_refinement`.
3. Migrate any saved recipes under `.runtime/specs/` that reference
   the old `post_genotyping_refinement` shape (or document them as
   obsolete).
4. Refresh any doc snippets that show the old shapes.

## Context

- Milestone H plan §5 Backward Compatibility.
- Milestone H Step 01 CHANGELOG note: "Breaking: task-level manifests
  moved from run_manifest.json to run_manifest_<stage>.json."
- Milestone H Step 04 CHANGELOG note: "Breaking:
  post_genotyping_refinement no longer accepts ref_path."
- Do this on a short-lived branch — do not mix with Milestone I work:
  `git checkout -b gatk-h-migration`.

## What to do

### Step 1 — Audit manifest-read sites

Find any code path that constructs
`{some_dir}/run_manifest.json` from a variant_calling task's output
directory (as opposed to a workflow's output directory):

```bash
# Broad manifest reads:
rg -n "run_manifest\.json" src/ tests/ scripts/ docs/ --glob '!docs/gatk_milestone_*/'

# Narrower: manifest reads near variant_calling identifiers:
rg -n -C 3 "run_manifest" src/flytetest/ tests/ | \
  rg -n "variant_calling|bwa_mem2|sort_sam|mark_duplicates|base_recalibrator|apply_bqsr|haplotype_caller|combine_gvcfs|joint_call|variant_recalibrator|apply_vqsr|merge_bam_alignment|gather_vcfs|calculate_genotype_posteriors|create_sequence_dictionary|index_feature_file" -B2 -A2
```

For each hit, classify:

- **Workflow-level read** (reading the workflow's own manifest) — no
  change needed.
- **Task-level read that expects the workflow-level shape** — broken
  by H. Update to read `run_manifest_<stage>.json`.
- **Task-level read that enumerates all stage manifests** — update to
  glob `run_manifest_*.json` instead of a single fixed name.

Add a regression test if any live consumer exists:

`tests/test_variant_calling.py::TaskManifestConsumerTests::test_reads_per_stage_manifests`

### Step 2 — Audit `post_genotyping_refinement` callers

```bash
rg -n "post_genotyping_refinement" src/ tests/ scripts/ docs/ \
  --glob '!docs/gatk_milestone_*/' --glob '!CHANGELOG.md'
```

For each call site that passes `ref_path=` (or the positional
equivalent), drop the kwarg. Verify the registry entry for
`post_genotyping_refinement` has `ref_path` dropped from its `inputs`
tuple (Milestone H Step 04 should have done this; confirm).

Confirm the planner bindings: if `ReferenceGenome` is declared in the
entry's `accepted_planner_types`, drop it — the workflow no longer
consumes it.

### Step 3 — Scan saved recipes under `.runtime/specs/`

```bash
find .runtime/specs -name '*.json' -type f 2>/dev/null | \
  xargs -I {} sh -c 'grep -l "post_genotyping_refinement" "{}" && echo "   in {}"'
```

For each saved recipe that pins `post_genotyping_refinement`:

- Open the JSON. If `ref_path` appears in the recipe's input bindings,
  it is now obsolete.
- Two options:
  - (a) **Preserve history** — append `.obsolete` to the filename so the
    run history tools do not attempt to replay the recipe. Leaves the
    artifact for archival value.
  - (b) **Migrate** — edit the JSON to drop `ref_path` and re-save under
    the same recipe_id (updates `.runtime/specs/latest_*.txt` pointers
    as needed).

Default to (a) unless the user explicitly asks for live migration.

Document the outcome in the CHANGELOG migration note.

### Step 4 — Doc sweep

```bash
rg -n "run_manifest\.json" docs/ --glob '!docs/gatk_milestone_*/'
rg -n "post_genotyping_refinement" docs/ --glob '!docs/gatk_milestone_*/'
```

Update any doc snippet that still shows the old manifest path or the
old `post_genotyping_refinement` signature. Archive docs under
`docs/gatk_milestone_*/` are historical — leave them alone.

Expected update sites:

- `README.md` — "Current local MCP execution" block already updated by
  H Step 02.
- `docs/mcp_showcase.md` — if it shows a `post_genotyping_refinement`
  example.
- `docs/gatk_pipeline_overview.md` — if the DAG or task table referenced
  the old signature.

### Step 5 — CHANGELOG migration note

Prepend under `## Unreleased`:

```
### GATK Milestone H Migration — Breaking-Change Follow-up (YYYY-MM-DD)

Post-H migration sweep for external consumers of the two breaking
changes.

- [x] YYYY-MM-DD audited manifest reads repo-wide; <N> task-level reads
      updated to the per-stage filename convention (or glob pattern).
- [x] YYYY-MM-DD audited post_genotyping_refinement callers; <N> call
      sites migrated; <N> saved recipes marked .obsolete.
- [x] YYYY-MM-DD doc sweep: <files> updated.
- [x] YYYY-MM-DD full pytest green.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg -n "run_manifest\.json" src/flytetest/ tests/ scripts/ docs/ \
  --glob '!docs/gatk_milestone_*/' --glob '!CHANGELOG.md' | \
  rg -v "workflows/variant_calling\.py|# workflow-level"
# Manual review: each remaining hit should be a workflow-level read.
rg -n "post_genotyping_refinement.*ref_path" src/ tests/ scripts/ docs/ \
  --glob '!docs/gatk_milestone_*/' --glob '!CHANGELOG.md'
# expected: zero hits
find .runtime/specs -name '*.json' -type f 2>/dev/null | \
  xargs grep -l '"post_genotyping_refinement".*"ref_path"' 2>/dev/null
# expected: zero hits (or migrated / marked .obsolete)
```

## Commit message

```
variant_calling: migrate consumers after Milestone H breaking changes
```

## Merge

Merge the migration branch immediately after the sweep:

```bash
git checkout main && git merge --no-ff gatk-h-migration && git branch -d gatk-h-migration
```

## Checklist

- [ ] Manifest reads audited; task-level reads updated or confirmed as
      workflow-level.
- [ ] No live caller passes `ref_path=` to
      `post_genotyping_refinement`.
- [ ] Saved recipes under `.runtime/specs/` either migrated or marked
      `.obsolete`.
- [ ] Doc sweep complete (archive milestone dirs untouched).
- [ ] CHANGELOG migration note prepended.
- [ ] Full pytest suite green.
- [ ] Migration branch merged.

## When to skip this prompt

- No external consumers of variant_calling manifests exist.
- No saved recipes reference `post_genotyping_refinement` with
  `ref_path`.
- In that case: run the verification block above, confirm zero hits,
  and skip the remaining steps.
