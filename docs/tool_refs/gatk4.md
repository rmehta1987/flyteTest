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
