# Step 03 — Planning Intent + Bundle Integrity + Stale-Assumption Sweep

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). The planning intent branch is the
largest piece; it follows the existing `_typed_goal_for_target` pattern
closely. No novel architecture.

## Goal

1. Add a `variant_calling` intent branch in `planning.py` so natural-
   language prompts route to registered GATK targets.
2. Fix the `variant_calling_germline_minimal` bundle's typed-binding /
   scalar-input mismatch.
3. Remove stale "out of scope for Milestone A" text from
   `haplotype_caller`'s manifest assumptions.

## Context

- Milestone H plan §4 Step 03.
- `src/flytetest/planning.py` — `_typed_goal_for_target`,
  `_target_name_advisories`, `plan_typed_request` (lines ~706-1863) are
  the existing intent-matching surface.
- `src/flytetest/bundles.py:126-174` — `variant_calling_germline_minimal`
  entry.
- `src/flytetest/tasks/variant_calling.py:260` — stale assumption line.
- Branch: `gatkport-h`.

## What to build

### Planning intent branch (`src/flytetest/planning.py`)

The existing file has a pattern where biological_goal + target_name map
to a `TypedPlanningGoal`. Extend `_typed_goal_for_target` (or the
surrounding intent matcher, depending on how prompt heuristics are
currently organized) so prompts mentioning variant-calling concepts
resolve to the right registered target.

Minimum keyword set (tune against existing prompt-flow tests):

```python
VARIANT_CALLING_KEYWORDS = frozenset({
    "variant", "variants", "vcf", "gvcf", "germline",
    "haplotype", "haplotypecaller",
    "genotype", "genotyping", "joint-calling", "joint calling",
    "vqsr", "bqsr", "recalibration", "recalibrator",
    "dedup", "mark duplicates",
    "bwa", "bwa-mem", "bwa-mem2",
})
```

Target mapping (scope to the 14 exposed entries from Step 02):

| Phrase cluster | Target |
|---|---|
| "prepare reference / index reference / create sequence dictionary" | `prepare_reference` |
| "preprocess / align / sort / dedup / recalibrate reads" | `preprocess_sample` |
| "preprocess from ubam" | `preprocess_sample_from_ubam` |
| "call germline variants / end-to-end / GVCF → VCF" | `germline_short_variant_discovery` |
| "VQSR / recalibrate variants / filter cohort VCF" | `genotype_refinement` |
| "scatter haplotype calls by interval" | `scattered_haplotype_caller` |
| "refine genotype posteriors / CGP / population priors" | `post_genotyping_refinement` |
| "haplotype caller / per-sample GVCF / HaplotypeCaller" | `haplotype_caller` |
| "combine GVCFs / cohort GVCF" | `combine_gvcfs` |
| "joint-call GVCFs / GenomicsDBImport / GenotypeGVCFs" | `joint_call_gvcfs` |
| "base recalibrator / BQSR table" | `base_recalibrator` |
| "apply BQSR" | `apply_bqsr` |
| "create sequence dictionary" | `create_sequence_dictionary` |
| "index VCF / index feature file" | `index_feature_file` |

Prefer the most specific match. When multiple targets match ambiguously,
return a decline with `suggested_bundles=["variant_calling_germline_minimal"]`
and `next_steps` pointing at `load_bundle`.

### Tests (`tests/test_planning.py`)

Add `VariantCallingIntentTests`:

- `test_germline_discovery_prompt_maps_to_end_to_end_workflow` — prompt
  "Run GATK germline variant calling on paired-end reads" returns a
  plan whose `matched_entry_names` includes
  `germline_short_variant_discovery`.
- `test_bqsr_prompt_maps_to_base_recalibrator` — prompt
  "Generate a BQSR recalibration table for a BAM with dbSNP and Mills
  known sites" maps to `base_recalibrator`.
- `test_vqsr_prompt_maps_to_genotype_refinement` — prompt
  "Recalibrate variants with VQSR on a joint-called cohort VCF" maps to
  `genotype_refinement`.
- `test_ambiguous_prompt_declines_with_bundle_hint` — prompt
  "variant calling please" declines and suggests
  `variant_calling_germline_minimal`.

### Bundle typed-binding fix (`src/flytetest/bundles.py`)

In `variant_calling_germline_minimal` (lines ~126-174), the `KnownSites`
typed binding declares only dbSNP while the scalar `known_sites` list
declares dbSNP + Mills. Pick option (a) for minimal churn:

**Option (a): Drop the typed `KnownSites` binding from this bundle.**

Rationale: the scalar `known_sites` channel is the authoritative input
for every downstream task (`base_recalibrator`, `variant_recalibrator`,
`prepare_reference`), and typed `KnownSites` bindings remain available
to callers via `explicit_bindings` when needed for a single-resource
workflow.

Change:

```python
bindings={
    "ReferenceGenome": {"fasta_path": "data/references/hg38/chr20.fa"},
    "ReadPair": {
        "sample_id": "NA12878_chr20",
        "r1_path": "data/reads/NA12878_chr20_R1.fastq.gz",
        "r2_path": "data/reads/NA12878_chr20_R2.fastq.gz",
    },
    # KnownSites dropped — use scalar `known_sites` list below.
},
```

Add a short `# M:H` note in the `description` field:

```
"Minimal germline variant calling demo: chr20 slice of NA12878 "
"with reference, known-sites VCFs, and paired reads. "
"Known-sites VCFs are supplied via the scalar `known_sites` input "
"(tuple typed-binding is Milestone I work). "
"Documentation-only — no fixture data is stored in the repo."
```

Update bundle availability check in
`src/flytetest/bundles.py:_check_bundle_availability` if it currently
walks `KnownSites.vcf_path` — it should still walk the scalar
`known_sites` paths through `applies_to` registry checks.

### Tests (`tests/test_bundles.py`)

- `test_variant_calling_germline_minimal_has_consistent_bindings` —
  assert that every declared typed binding in
  `variant_calling_germline_minimal.bindings` is accepted by every
  entry in `applies_to`, and that no typed binding refers to a
  resource-family (dbSNP/Mills) that the scalar inputs also enumerate
  separately.

### Stale assumption (`src/flytetest/tasks/variant_calling.py`)

In `haplotype_caller`'s manifest `assumptions` list (line ~260), remove:

```python
"Whole-genome pass; intervals-scoped calling is out of scope for Milestone A.",
```

Replace with one line describing current behavior:

```python
"Intervals scoping is supported via the `intervals` parameter (Milestone F); whole-genome when omitted.",
```

Also grep the whole module for other `out of scope for Milestone A`
strings and either delete or rewrite them:

```bash
rg "out of scope for Milestone A" src/flytetest/
```

## CHANGELOG

```
### GATK Milestone H Step 03 — Planning intent + bundle integrity (YYYY-MM-DD)
- [x] YYYY-MM-DD added variant_calling intent branch to planning.py covering all 14 MCP targets.
- [x] YYYY-MM-DD fixed variant_calling_germline_minimal: dropped stale KnownSites typed binding; scalar known_sites is authoritative.
- [x] YYYY-MM-DD swept haplotype_caller manifest assumption (Milestone F intervals now documented inline).
- [x] YYYY-MM-DD added 4 VariantCallingIntentTests + 1 bundle-consistency test.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_planning.py tests/test_bundles.py tests/test_variant_calling.py -xvs
rg "out of scope for Milestone A" src/flytetest/
# expected: zero hits
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -c \
  "from flytetest.bundles import BUNDLES; b = BUNDLES['variant_calling_germline_minimal']; \
   print('typed_bindings:', sorted(b.bindings)); \
   print('scalar_known_sites:', b.inputs.get('known_sites'))"
# expected: typed_bindings: ['ReadPair', 'ReferenceGenome']
```

## Commit message

```
variant_calling: planning intent, bundle integrity, haplotype_caller assumption refresh
```

## Checklist

- [ ] Planning intent branch covers all 14 exposed variant_calling targets.
- [ ] `variant_calling_germline_minimal` bundle has no `KnownSites` typed binding.
- [ ] Bundle description notes that scalar `known_sites` is the authoritative channel.
- [ ] `haplotype_caller` manifest assumption no longer mentions "out of scope for Milestone A".
- [ ] Module-wide grep for that phrase returns zero hits.
- [ ] 4 new intent tests + 1 bundle test passing.
- [ ] Step 03 marked Complete in checklist.
