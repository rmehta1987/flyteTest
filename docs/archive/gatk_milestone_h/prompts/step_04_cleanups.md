# Step 04 — Workflow + Task Signature Cleanups

## Model

**Haiku 4.5** or **Sonnet 4.6** (`claude-haiku-4-5-20251001` /
`claude-sonnet-4-6`). Three small, independent changes with clear
scope. Haiku is acceptable here; pick Sonnet if the idempotency logic
needs careful branch handling.

## Goal

1. Drop the unused `ref_path` parameter from `post_genotyping_refinement`.
2. Add `force: bool = False` idempotency to `prepare_reference`.
3. Document GenomicsDB workspace as ephemeral-only in the pipeline
   overview doc.

## Context

- Milestone H plan §4 Step 04.
- `src/flytetest/workflows/variant_calling.py:463-493` —
  `post_genotyping_refinement` signature.
- `src/flytetest/workflows/variant_calling.py:44-85` —
  `prepare_reference` signature and body.
- `docs/gatk_pipeline_overview.md` — end-to-end pipeline reference.
- Branch: `gatkport-h`.

## What to build

### Drop `ref_path` from `post_genotyping_refinement`

**Before** (`workflows/variant_calling.py:463`):

```python
@variant_calling_env.task
def post_genotyping_refinement(
    ref_path: str,
    vcf_path: str,
    cohort_id: str,
    results_dir: str,
    supporting_callsets: list[str] | None = None,
    sif_path: str = "",
) -> dict:
    cgp = calculate_genotype_posteriors(
        ref_path=ref_path,
        vcf_path=vcf_path,
        ...
    )
```

**After:**

```python
@variant_calling_env.task
def post_genotyping_refinement(
    vcf_path: str,
    cohort_id: str,
    results_dir: str,
    supporting_callsets: list[str] | None = None,
    sif_path: str = "",
) -> dict:
    cgp = calculate_genotype_posteriors(
        # The underlying GATK CGP CLI has no -R flag.
        # calculate_genotype_posteriors accepts ref_path for interface
        # consistency but ignores it; pass empty string.
        ref_path="",
        vcf_path=vcf_path,
        ...
    )
```

Update the registry entry in `registry/_variant_calling.py` to drop
`ref_path` from the `inputs` tuple (leaving `vcf_path`, `cohort_id`,
`results_dir`, `supporting_callsets`, `sif_path`).

Update `accepted_planner_types` if it currently includes `ReferenceGenome`
— drop it. `VariantCallSet` is the only accepted planner type.

### Idempotent `prepare_reference`

**Current behavior** (line ~45): unconditionally runs
`CreateSequenceDictionary`, `IndexFeatureFile` per VCF, and
`bwa_mem2_index`. Concurrent runs on shared reference data race on these
files.

**New signature:**

```python
@variant_calling_env.task
def prepare_reference(
    ref_path: str,
    known_sites: list[str],
    results_dir: str,
    sif_path: str = "",
    force: bool = False,
) -> dict:
    """Prepare a reference genome for GATK germline variant calling.

    Steps (each skipped when the expected output already exists and
    ``force=False``):
      1. CreateSequenceDictionary — produces .dict file.
      2. IndexFeatureFile — indexes each known-sites VCF.
      3. bwa_mem2_index — creates BWA-MEM2 index files.
    """
```

**Skip conditions:**

- CreateSequenceDictionary: skip if `Path(ref_path).with_suffix('.dict')`
  exists.
- IndexFeatureFile: for each VCF, skip if `.idx` (plain VCF) or `.tbi`
  (vcf.gz) exists.
- `bwa_mem2_index`: skip if all five expected index files exist next to
  the index prefix (`.0123`, `.amb`, `.ann`, `.bwt.2bit.64`, `.pac`).

When `force=True`, always rerun each step regardless of existing output.

**Manifest assumption update:** add

```python
"Re-running with force=False skips steps whose outputs are present; pass force=True to rerun unconditionally.",
```

Track which steps were skipped in the workflow manifest:

```python
outputs={"prepared_ref": ref_path, "skipped_steps": skipped_steps}
```

where `skipped_steps` is a `list[str]` of step names.

Update the registry entry `inputs` tuple to include `force` (bool, optional).

### Tests (`tests/test_variant_calling_workflows.py`)

Add `PrepareReferenceIdempotencyTests`:

- `test_skips_sequence_dictionary_when_dict_exists` — pre-create the
  `.dict` file; assert `CreateSequenceDictionary` is not called and
  manifest `skipped_steps` contains `"create_sequence_dictionary"`.
- `test_skips_index_feature_file_when_tbi_exists` — pre-create `.tbi`;
  assert `IndexFeatureFile` not called for that VCF.
- `test_skips_bwa_index_when_all_suffixes_present` — pre-create all 5
  BWA index files; assert `bwa_mem2_index` not called.
- `test_force_true_reruns_all_steps` — with all outputs pre-existing,
  pass `force=True`; assert every inner step was called.

Add `PostGenotypingRefinementSignatureTests`:

- `test_signature_has_no_ref_path` — use `inspect.signature` on
  `post_genotyping_refinement` and assert `ref_path` is not a parameter.
- `test_registry_inputs_match_signature` — load the registry entry,
  compare its `inputs` names against the signature.

### GenomicsDB ephemeral-only doc

In `docs/gatk_pipeline_overview.md`, under the existing `## Deferred
Items` section, add:

```markdown
- GenomicsDB workspace incremental update — out of scope; `joint_call_gvcfs`
  builds the workspace in a `TemporaryDirectory` and deletes it on
  function exit, precluding GATK's `--genomicsdb-update-workspace-path`
  re-entry pattern. Acceptable for cohorts that are re-joint-called from
  per-sample GVCFs each run; not suitable for incremental-cohort designs.
```

## CHANGELOG

```
### GATK Milestone H Step 04 — Workflow cleanups (YYYY-MM-DD)
- [x] YYYY-MM-DD dropped unused ref_path from post_genotyping_refinement; registry inputs and accepted_planner_types updated.
- [x] YYYY-MM-DD prepare_reference gained force=False idempotency; steps skip when outputs present; manifest tracks skipped_steps.
- [x] YYYY-MM-DD documented GenomicsDB ephemeral-only workspace as non-goal in pipeline overview.
- [x] YYYY-MM-DD added 4 PrepareReferenceIdempotencyTests + 2 PostGenotypingRefinementSignatureTests.
- [!] Breaking: post_genotyping_refinement no longer accepts ref_path. Any caller passing it must drop the keyword.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_variant_calling_workflows.py tests/test_registry.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c \
  "import inspect; from flytetest.workflows.variant_calling import post_genotyping_refinement, prepare_reference
sig_cgp = inspect.signature(post_genotyping_refinement)
assert 'ref_path' not in sig_cgp.parameters, sig_cgp
sig_pr = inspect.signature(prepare_reference)
assert 'force' in sig_pr.parameters and sig_pr.parameters['force'].default is False, sig_pr
print('signatures ok')"
grep -q "GenomicsDB workspace incremental update" docs/gatk_pipeline_overview.md
echo "pipeline overview updated: $?"
```

## Commit message

```
variant_calling: drop unused ref_path from post_genotyping_refinement; idempotent prepare_reference
```

## Checklist

- [ ] `post_genotyping_refinement` signature no longer has `ref_path`.
- [ ] Registry entry `inputs` updated to match.
- [ ] `accepted_planner_types` on `post_genotyping_refinement` no longer includes `ReferenceGenome`.
- [ ] `prepare_reference` gained `force: bool = False`.
- [ ] Each inner step skips on existing output when `force=False`.
- [ ] Workflow manifest records `skipped_steps` list.
- [ ] `docs/gatk_pipeline_overview.md` documents GenomicsDB ephemeral-only.
- [ ] 6 new tests passing.
- [ ] CHANGELOG breaking-change note present.
- [ ] Step 04 marked Complete in checklist.
