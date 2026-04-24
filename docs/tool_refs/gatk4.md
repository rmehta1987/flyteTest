# GATK4

## Purpose

Germline variant discovery from aligned, duplicate-marked BAMs: BQSR
recalibration, per-sample GVCF calling, cohort GVCF merging, and joint
genotyping via GenomicsDB.

## Input Data

- coordinate-sorted, duplicate-marked BAM (caller-supplied; alignment and dedup
  are out of Milestone A scope)
- reference genome FASTA with `.fai` and `.dict` index files
- indexed known-sites VCFs for BQSR (e.g., dbSNP, Mills)

## Output Data

- BQSR recalibration table (`.table`)
- recalibrated BAM
- per-sample GVCF (`.g.vcf` + `.idx`)
- cohort merged GVCF
- joint-called VCF

## Pipeline Fit

Germline variant calling family (`pipeline_family="variant_calling"`);
BAM-in, VCF-out. Alignment and dedup are Milestone B scope. VQSR is
deferred. See `docs/gatk_milestone_a/milestone_a_plan.md`.

## Official Documentation

- [GATK Best Practices — Germline SNPs and Indels](https://gatk.broadinstitute.org/hc/en-us/articles/360035535932)
- [BaseRecalibrator](https://gatk.broadinstitute.org/hc/en-us/articles/360036898312)
- [ApplyBQSR](https://gatk.broadinstitute.org/hc/en-us/articles/360037055712)
- [HaplotypeCaller](https://gatk.broadinstitute.org/hc/en-us/articles/360037225632)
- [CombineGVCFs](https://gatk.broadinstitute.org/hc/en-us/articles/360037053272)
- [GenomicsDBImport](https://gatk.broadinstitute.org/hc/en-us/articles/360036883491)
- [GenotypeGVCFs](https://gatk.broadinstitute.org/hc/en-us/articles/360037057852)

---

## create_sequence_dictionary

**GATK tool:** `CreateSequenceDictionary`

**FLyteTest path:** `flytetest.tasks.variant_calling.create_sequence_dictionary`

**Command shape:**
```
gatk CreateSequenceDictionary -R <ref.fa> -O <ref.dict>
```

**Key argument rationale:**
- `-R` — reference FASTA input; GATK reads the sequence names and lengths.
- `-O` — explicit output path; GATK would otherwise write next to `-R`, which may be read-only.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/create_sequence_dictionary.py`

**Milestone A scope notes:**
- Produces the `.dict` file that `BaseRecalibrator`, `ApplyBQSR`, and
  `HaplotypeCaller` require alongside the `.fai` index.
- Must be run once per reference before any BQSR or calling step.

---

## index_feature_file

**GATK tool:** `IndexFeatureFile`

**FLyteTest path:** `flytetest.tasks.variant_calling.index_feature_file`

**Command shape:**
```
gatk IndexFeatureFile -I <sites.vcf[.gz]>
```

**Key argument rationale:**
- `-I` — input VCF or GVCF; GATK writes the index (`.idx` for plain VCF,
  `.tbi` for `.vcf.gz`) next to the input file.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/index_feature_file.py`

**Milestone A scope notes:**
- Must be run on each known-sites VCF before `BaseRecalibrator`.
- Index suffix is inferred from the input suffix: `.vcf` → `.vcf.idx`,
  `.vcf.gz` → `.vcf.gz.tbi`.

---

## base_recalibrator

**GATK tool:** `BaseRecalibrator`

**FLyteTest path:** `flytetest.tasks.variant_calling.base_recalibrator`

**Command shape:**
```
gatk BaseRecalibrator -R <ref.fa> -I <sample.bam> -O <sample_bqsr.table> \
  --known-sites <dbsnp.vcf> [--known-sites <mills.vcf> ...]
```

**Key argument rationale:**
- `--known-sites` repeated once per indexed VCF; at least one required.
- `-O` — recalibration table consumed by `ApplyBQSR`.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/base_recalibrator.py`

**Milestone A scope notes:**
- Requires a coordinate-sorted, duplicate-marked BAM (caller responsibility).
- All known-sites VCFs must be indexed (`.idx` or `.tbi`) before invocation.
- Reference must have a `.fai` and `.dict` already present.
- Resources: 4 CPU / 16 GiB local; Slurm hints 8 CPU / 32 GiB / 06:00:00.

---

## apply_bqsr

**GATK tool:** `ApplyBQSR`

**FLyteTest path:** `flytetest.tasks.variant_calling.apply_bqsr`

**Command shape:**
```
gatk ApplyBQSR -R <ref.fa> -I <sample.bam> \
  --bqsr-recal-file <sample_bqsr.table> -O <sample_recalibrated.bam>
```

**Key argument rationale:**
- `--bqsr-recal-file` — recalibration table from `base_recalibrator`; must
  have been generated with the same reference and known sites.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/apply_bqsr.py`

**Milestone A scope notes:**
- GATK writes a `.bai` index alongside the output BAM; the task checks both
  `.bai` and `.bam.bai` naming conventions.
- Resources: 4 CPU / 16 GiB local; Slurm hints 8 CPU / 32 GiB / 06:00:00.

---

## haplotype_caller

**GATK tool:** `HaplotypeCaller`

**FLyteTest path:** `flytetest.tasks.variant_calling.haplotype_caller`

**Command shape:**
```
gatk HaplotypeCaller -R <ref.fa> -I <sample.bam> \
  -O <sample.g.vcf> --emit-ref-confidence GVCF
```

**Key argument rationale:**
- `--emit-ref-confidence GVCF` — required for per-sample GVCF mode; enables
  joint genotyping downstream via `CombineGVCFs` + `GenotypeGVCFs`.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/haplotype_caller.py`

**Milestone A scope notes:**
- Whole-genome pass only; interval-scoped calling is out of scope.
- BQSR-recalibrated BAM strongly recommended.
- Output is `<sample_id>.g.vcf`; GATK writes `.g.vcf.idx` alongside.
- Resources: 8 CPU / 32 GiB local; Slurm hints 16 CPU / 64 GiB / 24:00:00.

---

## combine_gvcfs

**GATK tool:** `CombineGVCFs`

**FLyteTest path:** `flytetest.tasks.variant_calling.combine_gvcfs`

**Command shape:**
```
gatk CombineGVCFs -R <ref.fa> -O <cohort_combined.g.vcf> \
  -V <s1.g.vcf> -V <s2.g.vcf> [...]
```

**Key argument rationale:**
- `-V` repeated once per per-sample GVCF, in order; input order is preserved
  in the output.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/combine_gvcfs.py:66–76`

**Milestone A scope notes:**
- All inputs must have been emitted with `--emit-ref-confidence GVCF`.
- All inputs must call against the same reference build.
- Empty list raises `ValueError` before GATK is invoked.
- Resources: 4 CPU / 16 GiB local; Slurm hints 8 CPU / 32 GiB / 06:00:00.

---

## joint_call_gvcfs

**GATK tools:** `GenomicsDBImport` → `GenotypeGVCFs`

**FLyteTest path:** `flytetest.tasks.variant_calling.joint_call_gvcfs`

**Command shapes:**
```
# Step 1 — import
gatk GenomicsDBImport \
  --genomicsdb-workspace-path <cohort_genomicsdb/> \
  --sample-name-map <sample_map.txt> \
  -L <interval> [-L <interval> ...]

# Step 2 — genotype
gatk GenotypeGVCFs -R <ref.fa> \
  -V gendb://<cohort_genomicsdb/> \
  -O <cohort_genotyped.vcf>
```

**Key argument rationale:**
- `--sample-name-map` — TSV of `<sample_id>\t<gvcf_path>` written per
  invocation and discarded with the `TemporaryDirectory` workspace.
- `-L` — at least one genomic interval required by GenomicsDBImport; caller
  supplies (e.g., `["chr20"]`).
- `gendb://` URI — how GenotypeGVCFs reads the GenomicsDB workspace created by
  GenomicsDBImport in the same invocation.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/joint_call_gvcfs.py:63–108`

**Milestone A scope notes:**
- GenomicsDB workspace is ephemeral: created inside a `TemporaryDirectory`
  scoped to the task; never written to the results directory.
- `sample_ids` must be 1:1 with `gvcfs`; mismatch raises `ValueError`.
- Empty `gvcfs` or empty `intervals` each raise `ValueError` before GATK runs.
- Output is `<cohort_id>_genotyped.vcf`; GATK writes `.vcf.idx` alongside.
- Resources: 8 CPU / 32 GiB local; Slurm hints 16 CPU / 64 GiB / 24:00:00.

---

## bwa_mem2_index

**Tool:** BWA-MEM2

**FLyteTest path:** `flytetest.tasks.variant_calling.bwa_mem2_index`

**Command shape:**
```
bwa-mem2 index -p <results_dir>/<ref_stem> <ref.fa>
```

**Key argument rationale:**
- `-p <prefix>` — writes all five index files (`.0123`, `.amb`, `.ann`, `.bwt.2bit.64`, `.pac`) under `results_dir` using the reference stem as prefix.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/general/bwa_mem2.py` — `bwa_mem2_index`

**Milestone B scope notes:**
- All five index file extensions are verified post-run; `FileNotFoundError` if any is absent.
- Plain function returning a `dict` manifest (not a Flyte task decorator).
- Resources: 4 CPU / 16 GiB local; Slurm hints 8 CPU / 32 GiB / 02:00:00.

---

## bwa_mem2_mem

**Tool:** BWA-MEM2 + samtools

**FLyteTest path:** `flytetest.tasks.variant_calling.bwa_mem2_mem`

**Command shape:**
```
bwa-mem2 mem -R '@RG\tID:<sample_id>\tSM:<sample_id>\tLB:lib\tPL:ILLUMINA' \
  -t <threads> <ref.fa> <r1.fq.gz> [r2.fq.gz] \
  | samtools view -bS -o <sample_id>_aligned.bam -
```

**Implementation note:** Shell pipeline via `subprocess.run(shell=True)`; wrapped in `apptainer exec` when `sif_path` is set. `run_tool` cannot be used for piped commands.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/general/bwa_mem2.py` — `bwa_mem2_mem`

**Milestone B scope notes:**
- `r2_path=""` → single-end mode.
- `RuntimeError` raised when subprocess exits non-zero.
- Resources: 8 CPU / 32 GiB local; Slurm hints 16 CPU / 64 GiB / 08:00:00.

---

## sort_sam

**Tool:** GATK4 SortSam

**FLyteTest path:** `flytetest.tasks.variant_calling.sort_sam`

**Command shape:**
```
gatk SortSam -I <aligned.bam> -O <sample_id>_sorted.bam \
  --SORT_ORDER coordinate --CREATE_INDEX true
```

**Key argument rationale:**
- `--CREATE_INDEX true` — GATK writes the BAI alongside the sorted BAM. FLyteTest checks both `.bai` and `.bam.bai` naming conventions.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/sort_sam.py`

**Milestone B scope notes:**
- Consumes the unsorted BAM from `bwa_mem2_mem`.
- Resources: 4 CPU / 16 GiB local; Slurm hints 8 CPU / 32 GiB / 04:00:00.

---

## mark_duplicates

**Tool:** GATK4 MarkDuplicates

**FLyteTest path:** `flytetest.tasks.variant_calling.mark_duplicates`

**Command shape:**
```
gatk MarkDuplicates -I <sorted.bam> -O <sample_id>_marked_duplicates.bam \
  -M <sample_id>_duplicate_metrics.txt --CREATE_INDEX true
```

**Key outputs:**
- `dedup_bam` — duplicate-marked BAM; required input for `base_recalibrator`.
- `duplicate_metrics` — per-sample duplicate rate; both appear in the manifest.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/mark_duplicates.py`

**Milestone B scope notes:**
- Consumes the coordinate-sorted BAM from `sort_sam`.
- Both output files are verified post-run; `FileNotFoundError` if either is absent.
- Resources: 4 CPU / 16 GiB local; Slurm hints 8 CPU / 32 GiB / 04:00:00.

---

## variant_recalibrator

**Tool:** GATK4 VariantRecalibrator

**FLyteTest path:** `flytetest.tasks.variant_calling.variant_recalibrator`

**Command shape:**
```
gatk VariantRecalibrator \
  -R <ref.fa> -V <joint.vcf.gz> \
  -mode SNP|INDEL \
  -O <cohort_id>_<mode>.recal \
  --tranches-file <cohort_id>_<mode>.tranches \
  --resource:<name>,known=<bool>,training=<bool>,truth=<bool>,prior=<float> <vcf> \
  -an QD -an MQ -an MQRankSum -an ReadPosRankSum -an FS -an SOR   # SNP
  -an QD -an FS -an SOR                                            # INDEL
```

**Key argument rationale:**
- `-mode SNP` uses MQ and MQRankSum; `-mode INDEL` omits them — MQ-based annotations are unreliable for indels.
- `prior` encodes confidence in the resource: HapMap/Omni 15/12, 1000G 10, dbSNP 2 (known-only, not training).
- `known`/`training`/`truth` are lowercase strings (`"true"`/`"false"`); GATK rejects Python booleans.
- `known_sites` and `known_sites_flags` are parallel lists; each dict carries `resource_name`, `known`, `training`, `truth`, `prior`.

**Outputs:**
- `recal_file` — `<cohort_id>_<mode>.recal`; input to `apply_vqsr`.
- `tranches_file` — `<cohort_id>_<mode>.tranches`; input to `apply_vqsr`.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/variant_recalibrator.py:1-117`

**Milestone D scope notes:**
- Requires ≥30k SNPs (SNP mode) or ≥2k indels (INDEL mode). The chr20 slice in `variant_calling_germline_minimal` is too small; use `variant_calling_vqsr_chr20` bundle.
- All known-sites VCFs must be indexed (`.tbi` or `.idx`).
- Resources: 4 CPU / 16 GiB local; Slurm hints 4 CPU / 16 GiB / 04:00:00.

---

## apply_vqsr

**Tool:** GATK4 ApplyVQSR

**FLyteTest path:** `flytetest.tasks.variant_calling.apply_vqsr`

**Command shape:**
```
gatk ApplyVQSR \
  -R <ref.fa> -V <in.vcf.gz> \
  --recal-file <recal_file> \
  --tranches-file <tranches_file> \
  --truth-sensitivity-filter-level <level> \
  --create-output-variant-index true \
  -mode SNP|INDEL \
  -O <cohort_id>_vqsr_<mode>.vcf.gz
```

**Key argument rationale:**
- `--truth-sensitivity-filter-level` defaults to 99.5 (SNP) and 99.0 (INDEL) when `truth_sensitivity_filter_level=0.0` is passed.
- `--create-output-variant-index true` writes `.vcf.gz.tbi` automatically.
- The INDEL pass must consume the SNP-filtered VCF from the prior `apply_vqsr` call, not the original joint VCF — enforced by `genotype_refinement`.

**Outputs:**
- `vqsr_vcf` — `<cohort_id>_vqsr_<mode>.vcf.gz`.
- `vqsr_vcf_index` — companion `.vcf.gz.tbi`; empty string in manifest if absent.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/apply_vqsr.py:1-114`

**Milestone D scope notes:**
- `recal_file` and `tranches_file` must come from `variant_recalibrator` for the same mode.
- Resources: 4 CPU / 16 GiB local; Slurm hints 4 CPU / 16 GiB / 02:00:00.

---

## merge_bam_alignment

Merges an aligned (but unsorted) BAM from `bwa_mem2_mem` with its original
unmapped BAM (uBAM) to restore read group metadata, original base qualities,
and tags from the sequencer, producing a coordinate-sorted merged BAM.

**FLyteTest path:** `flytetest.tasks.variant_calling.merge_bam_alignment`

**Command shape:**
```
gatk MergeBamAlignment \
  -R <ref.fa> \
  -ALIGNED <aligned.bam> \
  -UNMAPPED <sample.ubam> \
  -O <sample_id>_merged.bam \
  --SORT_ORDER coordinate \
  --ADD_MATE_CIGAR true \
  --CLIP_ADAPTERS false \
  --CLIP_OVERLAPPING_READS true \
  --INCLUDE_SECONDARY_ALIGNMENTS true \
  --MAX_INSERTIONS_OR_DELETIONS -1 \
  --PRIMARY_ALIGNMENT_STRATEGY MostDistant \
  --ATTRIBUTES_TO_RETAIN X0 \
  --CREATE_INDEX true
```

**Key argument rationale:**
- `--SORT_ORDER coordinate` — output is coordinate-sorted, so no separate `sort_sam` step is required. This is the key structural difference from the `preprocess_sample` path.
- `--PRIMARY_ALIGNMENT_STRATEGY MostDistant` — GATK best-practice for WGS short reads; selects the primary alignment at the map position most distant from the mate's position, reducing mapping ambiguity near repeat boundaries.
- `--MAX_INSERTIONS_OR_DELETIONS -1` — disables the clipping of alignments with many indels; required for accurate indel calling at low-complexity regions.
- `--CLIP_ADAPTERS false` — adapter clipping is expected to have been performed upstream (during FASTQ preparation); hard-clipping here is destructive.
- `--ADD_MATE_CIGAR true` — adds the MC tag required by downstream GATK tools.
- `--CREATE_INDEX true` — writes a `.bai` companion file alongside the merged BAM.
- `ubam_path` must be **queryname-sorted** — GATK MergeBamAlignment requirement; providing a coordinate-sorted uBAM causes a fatal error.

**Outputs:**
- `merged_bam` — `<sample_id>_merged.bam`, coordinate-sorted.
- `merged_bam_index` — companion `.bai`; empty string in manifest if absent.

**Stargazer citation:**
`stargazer/src/stargazer/tasks/gatk/merge_bam_alignment.py`

**Milestone E scope notes:**
- `merge_bam_alignment` is stage 14 in the pipeline registry (a task-level stage slot distinct from the `preprocess_sample_from_ubam` workflow at stage 5).
- uBAM path is an alternative to the `preprocess_sample` FASTQ-only path; both paths produce a BQSR-recalibrated BAM accepted by `haplotype_caller`.
- Resources: 4 CPU / 16 GiB local; Slurm hints 4 CPU / 16 GiB / 02:00:00.

---

## gather_vcfs

Merges a set of per-interval GVCFs produced by `haplotype_caller` into a single
coordinate-sorted GVCF using GATK4 GatherVcfs (a Picard tool bundled in the
GATK4 distribution). This is the gather step in an interval-scatter/gather pattern.

**FLyteTest path:** `flytetest.tasks.variant_calling.gather_vcfs`

**Command shape:**
```
gatk GatherVcfs \
  -I <gvcf1> -I <gvcf2> ... \
  -O <sample_id>_gathered.g.vcf.gz \
  --CREATE_INDEX true
```

**Key argument rationale:**
- `-I` flags are emitted in `gvcf_paths` order — GatherVcfs requires inputs to be in genomic order and non-overlapping. Ordering is the caller's responsibility (enforced by `scattered_haplotype_caller`).
- `--CREATE_INDEX true` — writes a `.tbi` index alongside the output GVCF automatically; downstream tools require it.
- No `-R` reference flag — GatherVcfs is a pure merge operation and does not require a reference FASTA.

**Outputs:**
- `gathered_gvcf` — `<sample_id>_gathered.g.vcf.gz`, single merged GVCF.

**No Stargazer reference:** GatherVcfs is a standard Picard tool; the
implementation was designed directly from GATK4 documentation.

**Milestone F scope notes:**
- `gather_vcfs` is task stage 15 in the pipeline registry.
- The scatter step is a synchronous Python `for` loop inside `scattered_haplotype_caller` (workflow stage 6); there are no job arrays or async patterns.
- `SplitIntervals` is out of scope — users supply interval lists directly.
- Resources: 2 CPU / 8 GiB local; Slurm hints 2 CPU / 8 GiB / 01:00:00.

---

## calculate_genotype_posteriors

Refines per-sample genotype posteriors using population frequency priors
via GATK4 CalculateGenotypePosteriors (CGP). Downstream of joint calling;
optionally consumes population VCFs to improve posterior estimates.

**FLyteTest path:** `flytetest.tasks.variant_calling.calculate_genotype_posteriors`

**Command shape:**
```
gatk CalculateGenotypePosteriors \
  -V <vcf_path> \
  -O <cohort_id>_cgp.vcf.gz \
  --create-output-variant-index true \
  [--supporting-callsets <vcf>]   # one flag per supporting callset
```

**Key argument rationale:**
- No `-R` flag — CGP is a VCF-level operation and does not require a reference FASTA; including it would cause an error with some GATK4 builds.
- `--supporting-callsets` — provide one flag per population VCF (e.g. `1000G_omni2.5.hg38.vcf.gz`). CGP uses allele frequencies from these VCFs to sharpen genotype posteriors beyond pedigree-only priors. Omit entirely when no supporting data is available; CGP will apply pedigree-derived priors only.
- `--create-output-variant-index true` — writes a `.tbi` index automatically; required by downstream tools.

**Outputs:**
- `cgp_vcf` — `<cohort_id>_cgp.vcf.gz`, CGP-refined VCF.
- `cgp_vcf_index` — companion `.tbi`; empty string in manifest if absent.

**No Stargazer reference:** CGP was not implemented in the Stargazer reference
project; this implementation was derived directly from GATK4 documentation.

**Milestone G scope notes:**
- `calculate_genotype_posteriors` is task stage 16 in the pipeline registry.
- Composable after `genotype_refinement` (VQSR) or directly after `joint_call_gvcfs`; wired via the `post_genotyping_refinement` workflow (stage 7).
- VQSR on the CGP output is user-composable but out of scope for this milestone.
- Resources: 4 CPU / 16 GiB local; Slurm hints 4 CPU / 16 GiB / 02:00:00.
