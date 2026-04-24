# Step 09 — Closure

## Goal

Finish Milestone B: add the germline fixture bundle, the container-pull
script, update agent-context docs, write the milestone-level CHANGELOG
entry, and run the full verification suite.

## Context

- Milestone B plan §4 (bundle + script): `docs/gatk_milestone_b/milestone_b_plan.md`.
- Milestone A closure for structural reference: `docs/gatk_milestone_a/prompts/step_10_closure.md`.
- Branch: `gatkport-b`. Merge into `main` after this step.

---

## 1. Fixture bundle — `src/flytetest/bundles.py`

Add a `ResourceBundle` named `"variant_calling_germline_minimal"`.
This is documentation-only (no real data in the repo). Pattern: look at
existing bundle entries in `bundles.py` for the correct field names.

The bundle should describe:
- `ref_path` — e.g. `data/references/hg38/chr20.fa`
- `known_sites` — `["data/references/hg38/dbsnp_138.hg38.vcf", "data/references/hg38/Mills_and_1000G_gold_standard.indels.hg38.vcf"]`
- `r1_path` / `r2_path` — e.g. `data/reads/NA12878_chr20_R1.fastq.gz`
- `results_dir` — `results/germline_minimal/`
- `sif_path` — `data/images/gatk4.sif`
- `intervals` — `["chr20"]`
- `cohort_id` — `"NA12878_chr20"`

## 2. Container-pull script — `scripts/rcc/pull_gatk_image.sh`

```bash
#!/usr/bin/env bash
# Pull the GATK4 SIF image used by all variant_calling tasks.
# Usage: bash scripts/rcc/pull_gatk_image.sh [output_path]
set -euo pipefail
OUTPUT="${1:-data/images/gatk4.sif}"
mkdir -p "$(dirname "$OUTPUT")"
apptainer pull "$OUTPUT" docker://broadinstitute/gatk:latest
echo "GATK4 image written to: $OUTPUT"
```

Make it executable (`chmod +x`).

## 3. Agent-context sweep

### `AGENTS.md`

Update the Workflows section to add:
```
- `variant_calling.py` — GATK4 germline variant calling workflows (prepare_reference, preprocess_sample, germline_short_variant_discovery)
```

### `DESIGN.md`

Update §5.6 Germline Variant Calling to note that Milestone B added:
- Four preprocessing tasks (`bwa_mem2_index`, `bwa_mem2_mem`, `sort_sam`, `mark_duplicates`)
- Three workflow compositions (`prepare_reference`, `preprocess_sample`, `germline_short_variant_discovery`)
- Fixture bundle `variant_calling_germline_minimal`

### `docs/tool_refs/gatk4.md`

Add four new sections (after `joint_call_gvcfs`, before the final `---`):

- `bwa_mem2_index` — command shape, key argument rationale, Stargazer citation, scope notes.
- `bwa_mem2_mem` — note the shell pipeline; Stargazer citation.
- `sort_sam` — command shape, `--CREATE_INDEX true` note, Stargazer citation.
- `mark_duplicates` — command shape, both outputs (BAM + metrics), Stargazer citation.

## 4. Milestone-level CHANGELOG entry

Add under `## Unreleased` (above all existing Step entries for this milestone):

```markdown
### GATK Milestone B — Complete (YYYY-MM-DD)

Four preprocessing tasks and three end-to-end workflow compositions.
Full pipeline: raw reads → joint-called VCF.

- [x] YYYY-MM-DD 4 preprocessing tasks: bwa_mem2_index, bwa_mem2_mem, sort_sam, mark_duplicates.
- [x] YYYY-MM-DD 3 workflows: prepare_reference, preprocess_sample, germline_short_variant_discovery.
- [x] YYYY-MM-DD ReadPair planner type.
- [x] YYYY-MM-DD Fixture bundle `variant_calling_germline_minimal` added to bundles.py.
- [x] YYYY-MM-DD scripts/rcc/pull_gatk_image.sh added.
- [x] YYYY-MM-DD AGENTS.md, DESIGN.md §5.6, docs/tool_refs/gatk4.md updated.
- [x] YYYY-MM-DD Full pytest suite green.
- Deferred: merge_bam_alignment (uBAM path), VQSR, Milestone C cluster validation.
```

## 5. Checklist update

Mark Step 09 and the overall milestone Complete in
`docs/gatk_milestone_b/checklist.md`.

## 6. Verification suite

Run all gates from plan §8:

```bash
python -m compileall src/flytetest/
pytest tests/test_variant_calling.py -xvs
pytest tests/test_variant_calling_workflows.py -xvs
pytest tests/test_registry_manifest_contract.py -xvs
pytest tests/test_planner_types.py -xvs
pytest
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" \
  src/flytetest/tasks/variant_calling.py \
  src/flytetest/workflows/variant_calling.py
rg "bwa_mem2_index|sort_sam|mark_duplicates|prepare_reference|preprocess_sample|germline_short_variant_discovery" \
  src/flytetest/registry/_variant_calling.py
python -c "import flytetest.server"
```

All must pass before committing.

## Commit message

```
variant_calling: close Milestone B — fixture bundle, pull script, agent-context sweep
```

## Checklist

- [ ] `variant_calling_germline_minimal` bundle in `bundles.py`.
- [ ] `scripts/rcc/pull_gatk_image.sh` created and executable.
- [ ] `AGENTS.md` Workflows section updated.
- [ ] `DESIGN.md` §5.6 updated with Milestone B scope.
- [ ] `docs/tool_refs/gatk4.md` four new sections added.
- [ ] Milestone-level CHANGELOG entry added.
- [ ] Step 09 and milestone marked Complete in checklist.
- [ ] All verification gates pass.
- [ ] Branch merged into `main`.
