# SnpEff

## Purpose

Annotate genetic variants with functional effects (gene impact, coding consequence,
amino acid changes). SnpEff is chosen for Milestone I over VEP because it requires
no external ENSEMBL cache and integrates cleanly with a local SIF-based workflow.

## Input/Output Data

**Inputs:**
- Input VCF (plain or bgzip)
- SnpEff database name (e.g. `GRCh38.105`, `hg38`, `GRCh38.mane.1.2.ensembl`)
- SnpEff data directory containing the pre-downloaded database cache

**Outputs:**
- Annotated VCF (INFO field enriched with `ANN=` entries)
- Genes summary text file

## FLyteTest Path

Task: `flytetest.tasks.variant_calling.snpeff_annotate`
Workflow: `flytetest.workflows.variant_calling.annotate_variants_snpeff`

## Official Documentation

- SnpEff manual: http://pcingola.github.io/SnpEff/
- Database download: `scripts/rcc/download_snpeff_db.sh`

## Native Command Context

```bash
snpEff ann \
  -dataDir /path/to/snpeff/data \
  -stats cohort_snpeff_summary.html \
  GRCh38.105 \
  input.vcf \
  > cohort_snpeff.vcf
```

## Apptainer Command Context

```bash
apptainer exec --cleanenv --bind /path/to/snpeff/data:/path/to/snpeff/data \
  data/images/snpeff.sif \
  bash -c "snpEff ann -dataDir /path/to/snpeff/data -stats stats.html GRCh38.105 input.vcf > out.vcf"
```

## Prompt Template

```
annotate variants with snpeff using database GRCh38.105 and data dir /data/snpeff/data
```

## Notes and Caveats

- The database cache must be **pre-downloaded** before any Slurm submission.
  Compute nodes typically have no internet access; `check_offline_staging` verifies
  `snpeff_data_dir` is reachable from compute nodes.
- Download a database: `scripts/rcc/download_snpeff_db.sh GRCh38.105`
- VEP remains a Milestone K candidate when ENSEMBL-native identifiers or plugins
  are required.
- SnpEff writes to stdout; FLyteTest routes via `bash -c ... > output.vcf`.
- The genes summary file may not be emitted for empty/malformed VCFs; the task
  returns an empty string in the manifest for `snpeff_genes_txt` in that case.
