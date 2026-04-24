# Step 04 — Closure

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Mirrors Milestone D Step 05 closure
exactly: tool ref additions, milestone CHANGELOG entry, submission prompt,
verification, merge.

## Goal

1. Add `merge_bam_alignment` section to `docs/tool_refs/gatk4.md`.
2. Write milestone-level CHANGELOG entry.
3. Author `docs/gatk_milestone_e_submission_prompt.md` (≤100 lines).
4. Run all §8 verification gates.
5. Mark milestone Complete; merge `gatkport-e` into `main`.

## What to build

### `docs/tool_refs/gatk4.md`

Append after `apply_vqsr` section:

- **`## merge_bam_alignment`** — GATK MergeBamAlignment, FLyteTest path,
  command shape (all 9 flags), key argument rationale (why
  `--PRIMARY_ALIGNMENT_STRATEGY MostDistant`, why no sort_sam),
  Stargazer citation:
  `stargazer/src/stargazer/tasks/gatk/merge_bam_alignment.py`,
  Milestone E scope notes (ubam must be queryname-sorted; uBAM path
  alternative to preprocess_sample).

### Milestone-level CHANGELOG entry

Above Step 01–03 entries:

```
### GATK Milestone E — Complete (YYYY-MM-DD)
uBAM preprocessing path: UnmappedBAM type, merge_bam_alignment (stage 14),
preprocess_sample_from_ubam workflow (stage 5).
- [x] YYYY-MM-DD UnmappedBAM planner type + round-trip test.
- [x] YYYY-MM-DD merge_bam_alignment task (stage 14) + 4 unit tests.
- [x] YYYY-MM-DD preprocess_sample_from_ubam workflow (stage 5) + 4 unit tests.
- [x] YYYY-MM-DD docs/tool_refs/gatk4.md updated.
- [x] YYYY-MM-DD full pytest green.
- Deferred: interval-scoped HaplotypeCaller (Milestone F),
  CalculateGenotypePosteriors (Milestone G).
```

### Submission prompt — `docs/gatk_milestone_e_submission_prompt.md`

≤100 lines, matching voice of `docs/gatk_milestone_a_submission_prompt.md`.
Include: branch, scope summary, what-was-built table, verification commands,
scope boundaries, not-implemented note.

### Checklist + merge

- Mark Step 04 + milestone Complete in `docs/gatk_milestone_e/checklist.md`.
- Merge `gatkport-e` → `main` (no force-push, no skip-hooks).

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling_workflows.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_planner_types.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py
rg "merge_bam_alignment|preprocess_sample_from_ubam" src/flytetest/registry/_variant_calling.py
git diff --stat main... | grep -E '\.py$'
wc -l docs/gatk_milestone_e_submission_prompt.md
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c "import flytetest.server"
```

## Commit message

```
variant_calling: close Milestone E — uBAM path, merge_bam_alignment, tool ref
```

## Merge

```bash
git checkout main && git merge --no-ff gatkport-e && git branch -d gatkport-e
```
