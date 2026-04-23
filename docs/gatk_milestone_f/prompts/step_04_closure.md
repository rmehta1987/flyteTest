# Step 04 — Closure

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`).

## Goal

1. Add `gather_vcfs` section to `docs/tool_refs/gatk4.md`.
2. Milestone CHANGELOG entry + submission prompt (≤100 lines).
3. All §8 verification gates.
4. Merge `gatkport-f` → `main`.

## What to build

### `docs/tool_refs/gatk4.md`

Append after `apply_vqsr` (or after `merge_bam_alignment` if Milestone E
landed first):

**`## gather_vcfs`** — GatherVcfs (Picard/GATK4), FLyteTest path, command
shape (`-I` per path, `--CREATE_INDEX true`), key argument rationale (inputs
must be non-overlapping and in genomic order), no-Stargazer note (designed
from GATK docs), Milestone F scope notes (sequential scatter, no job arrays).

### Milestone CHANGELOG entry

```
### GATK Milestone F — Complete (YYYY-MM-DD)
Interval-scoped HaplotypeCaller: optional intervals on haplotype_caller,
gather_vcfs task (stage 15), scattered_haplotype_caller workflow (stage 6).
- [x] YYYY-MM-DD haplotype_caller extended with optional intervals (backward compatible).
- [x] YYYY-MM-DD gather_vcfs task (stage 15) + 4 unit tests.
- [x] YYYY-MM-DD scattered_haplotype_caller workflow (stage 6) + 5 unit tests.
- [x] YYYY-MM-DD docs/tool_refs/gatk4.md updated.
- [x] YYYY-MM-DD full pytest green.
- Deferred: CalculateGenotypePosteriors (Milestone G).
```

### `docs/gatk_milestone_f_submission_prompt.md` (≤100 lines)

### Checklist + merge

Mark Step 04 + milestone Complete. Merge `gatkport-f` → `main`.

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py
rg "gather_vcfs|scattered_haplotype_caller" src/flytetest/registry/_variant_calling.py
# Regression check: existing HaplotypeCaller tests still pass
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs -k "HaplotypeCaller"
wc -l docs/gatk_milestone_f_submission_prompt.md
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c "import flytetest.server"
```

## Commit message

```
variant_calling: close Milestone F — interval-scoped HaplotypeCaller, gather_vcfs, tool ref
```

## Merge

```bash
git checkout main && git merge --no-ff gatkport-f && git branch -d gatkport-f
```
