# Step 05 — Closure: Tool Ref, Agent-Context Sweep, CHANGELOG, Submission Prompt

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Synthesises across the whole milestone:
adds VQSR sections to `docs/tool_refs/gatk4.md`, writes the milestone
CHANGELOG entry, and authors the submission prompt. Voice and structure must
mirror Milestone A's closure.

## Goal

Finish Milestone D:

1. Add two sections to `docs/tool_refs/gatk4.md` (`variant_recalibrator`,
   `apply_vqsr`).
2. Update `DESIGN.md` §5.6 with a Milestone D note.
3. Write the milestone-level CHANGELOG entry.
4. Author `docs/gatk_milestone_d_submission_prompt.md` (≤100 lines).
5. Run every verification gate from the plan §8.
6. Mark Step 05 and the milestone Complete in
   `docs/gatk_milestone_d/checklist.md`.
7. Merge `gatkport-d` into `main` once gates pass.

## Context

- Milestone A submission prompt for voice reference:
  `docs/gatk_milestone_a_submission_prompt.md`.
- Milestone B closure prompt for structural reference:
  `docs/gatk_milestone_b/prompts/step_09_closure.md`.
- `docs/tool_refs/gatk4.md` — existing sections for all prior tasks;
  append after `mark_duplicates` (the last Milestone B entry).
- Stargazer citations for the two new tasks:
  - `stargazer/src/stargazer/tasks/gatk/variant_recalibrator.py` (whole file)
  - `stargazer/src/stargazer/tasks/gatk/apply_vqsr.py` (whole file)

## What to build

### 1. `docs/tool_refs/gatk4.md` — two new sections

Add after the `mark_duplicates` section, before the final `---`:

#### `## variant_recalibrator`

- **GATK tool:** `VariantRecalibrator`
- **FLyteTest task path:**
  `src/flytetest/tasks/variant_calling.py::variant_recalibrator`
- **Command shape:** `-R ref -V vcf -mode SNP|INDEL -O recal --tranches-file tranches --resource:name,known=...,training=...,truth=...,prior=... vcf [-an ...]`
- **Key argument rationale:**
  - `-mode SNP`: annotations QD, MQ, MQRankSum, ReadPosRankSum, FS, SOR
  - `-mode INDEL`: annotations QD, FS, SOR (MQ-based annotations unreliable for indels)
  - `prior` encodes prior belief in the resource quality; hapmap/omni at 15/12,
    1000G at 10, dbsnp at 2 (known-only, not training)
- **Stargazer citation:**
  `stargazer/src/stargazer/tasks/gatk/variant_recalibrator.py:1-117`
- **Scope notes:** Requires a cohort VCF with sufficient variant count
  (≥30k SNPs for SNP mode; ≥2k indels for INDEL mode). The chr20 NA12878
  slice in `variant_calling_germline_minimal` is too small; use the full
  chr20 WGS data from `variant_calling_vqsr_chr20` bundle.

#### `## apply_vqsr`

- **GATK tool:** `ApplyVQSR`
- **FLyteTest task path:**
  `src/flytetest/tasks/variant_calling.py::apply_vqsr`
- **Command shape:** `-R ref -V vcf --recal-file recal --tranches-file tranches --truth-sensitivity-filter-level level --create-output-variant-index true -mode SNP|INDEL -O out.vcf.gz`
- **Key argument rationale:**
  - `--truth-sensitivity-filter-level 99.5` (SNP) / `99.0` (INDEL) — GATK Best
    Practices defaults; lower = stricter filtering
  - `--create-output-variant-index true` — writes `.tbi` companion automatically
  - INDEL pass must consume the SNP-filtered VCF from the prior `apply_vqsr`
    call, not the original joint VCF
- **Stargazer citation:**
  `stargazer/src/stargazer/tasks/gatk/apply_vqsr.py:1-114`
- **Scope notes:** Output is always `.vcf.gz`; index is `.vcf.gz.tbi`.

### 2. `DESIGN.md` §5.6 update

Append after the Milestone C paragraph:

> **Milestone D** (complete) — two VQSR tasks (`variant_recalibrator`,
> `apply_vqsr`) and a `genotype_refinement` workflow that runs SNP VQSR
> then INDEL VQSR in sequence. The `variant_calling_vqsr_chr20` fixture
> bundle documents the full-chr20 NA12878 WGS training setup; training VCFs
> are downloaded by `scripts/rcc/download_vqsr_training_vcfs.sh` from the
> Broad public GCS reference bundle.

### 3. Milestone-level CHANGELOG entry

Add under `## Unreleased`, **above** the existing Step 01–04 entries:

```markdown
### GATK Milestone D — Complete (YYYY-MM-DD)

Closes Milestone D of the Phase 3 GATK port (tracker:
`docs/gatk_milestone_d/checklist.md`). Adds VQSR (Variant Quality Score
Recalibration) to the germline variant calling pipeline: two tasks
(`variant_recalibrator`, `apply_vqsr`), a `genotype_refinement` workflow,
a full-chr20 NA12878 fixture bundle, and a training-VCF download script.

- [x] YYYY-MM-DD variant_recalibrator task (stage 12) + 5 unit tests.
- [x] YYYY-MM-DD apply_vqsr task (stage 13) + 7 unit tests.
- [x] YYYY-MM-DD genotype_refinement workflow (stage 4) + 3 unit tests.
- [x] YYYY-MM-DD variant_calling_vqsr_chr20 bundle + download script.
- [x] YYYY-MM-DD docs/tool_refs/gatk4.md updated with VQSR sections.
- [x] YYYY-MM-DD DESIGN.md §5.6 updated.
- [x] YYYY-MM-DD full pytest green; python -m compileall clean.
- Deferred: merge_bam_alignment, interval-scoped HaplotypeCaller,
  CalculateGenotypePosteriors.
```

### 4. Submission prompt — `docs/gatk_milestone_d_submission_prompt.md`

≤100 lines. Structure mirrors `docs/gatk_milestone_a_submission_prompt.md`:

- `# GATK Milestone D — Submission Prompt` title.
- Branch: `gatkport-d`.
- One-paragraph summary of VQSR scope, two-pass design (SNP → INDEL on
  SNP-filtered VCF), and fixture dataset (full-chr20 NA12878 WGS from
  `gs://broad-public-datasets/NA12878/NA12878.cram`, training VCFs from
  `gs://gcp-public-data--broad-references/hg38/v0/`).
- "## What Was Built" — task list, workflow, bundle, script.
- "## Key Files" — table of file → role (mirror Milestone A's table).
- "## Verification" — the §8 gate commands.
- "## Scope Boundaries" — deferred items.
- "## Not Implemented (by design)" — no async/IPFS patterns.

### 5. Checklist update

- Mark Step 05 `Complete`.
- Add `Milestone status: Complete` at the top of
  `docs/gatk_milestone_d/checklist.md`.

## Verification — all must pass

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/

VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling_workflows.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest

rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" \
  src/flytetest/tasks/variant_calling.py \
  src/flytetest/workflows/variant_calling.py

rg "variant_recalibrator|apply_vqsr|genotype_refinement" \
  src/flytetest/registry/_variant_calling.py

test -f docs/gatk_milestone_d_submission_prompt.md
wc -l docs/gatk_milestone_d_submission_prompt.md   # expect <= 100

VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c "import flytetest.server"
```

All must pass. Grep gate must return zero hits. Submission prompt ≤100 lines.

## Commit message

```
variant_calling: close Milestone D — VQSR tasks, workflow, fixture, tool ref
```

## Merge

```bash
git checkout main
git merge --no-ff gatkport-d
git branch -d gatkport-d
```

## Checklist

- [ ] `docs/tool_refs/gatk4.md` has `## variant_recalibrator` and
  `## apply_vqsr` sections with Stargazer citations.
- [ ] `DESIGN.md` §5.6 appended with Milestone D note.
- [ ] Milestone-level CHANGELOG entry above Step 01–04 entries.
- [ ] `docs/gatk_milestone_d_submission_prompt.md` ≤ 100 lines.
- [ ] All §8 verification gates green.
- [ ] Step 05 and milestone marked Complete in checklist.
- [ ] `gatkport-d` merged into `main`.
