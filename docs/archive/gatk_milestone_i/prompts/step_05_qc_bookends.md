# Step 05 — QC Bookends: Picard + bcftools + MultiQC

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Three tasks + two workflows are
small individually but the MultiQC aggregation requires careful
file-layout choices so the report picks up all inputs automatically.

## Goal

1. Add pre-call `collect_wgs_metrics` task (Picard) and wrap it in a
   `pre_call_coverage_qc` workflow.
2. Add post-call `bcftools_stats` and `multiqc_summarize` tasks and
   compose them in a `post_call_qc_summary` workflow.
3. Registry entries, tool refs, tests.

## Context

- Milestone I plan §4 Step 05.
- Tool manuals:
  - Picard `CollectWgsMetrics` + `CollectInsertSizeMetrics`.
  - bcftools `stats` subcommand.
  - MultiQC — auto-detects Picard, bcftools, FastQC, and GATK
    MarkDuplicates outputs when given a scan root.
- Branch: `gatkport-i`.

## What to build

### `src/flytetest/tasks/variant_calling.py`

Three new tasks:

```python
@variant_calling_env.task
def collect_wgs_metrics(
    reference_fasta: File,
    aligned_bam: File,
    sample_id: str,
    picard_sif: str = "",
) -> tuple[File, File]:
    """Picard CollectWgsMetrics + CollectInsertSizeMetrics on one BAM.

    Returns (wgs_metrics_txt, insert_size_metrics_txt).
    """
    ref = require_path(Path(reference_fasta.download_sync()), "Reference FASTA")
    bam = require_path(Path(aligned_bam.download_sync()), "Aligned BAM")

    out_dir = project_mkdtemp("picard_wgs_")
    wgs_out = out_dir / f"{sample_id}_wgs_metrics.txt"
    insert_out = out_dir / f"{sample_id}_insert_size_metrics.txt"
    insert_hist = out_dir / f"{sample_id}_insert_size_histogram.pdf"

    run_tool(
        ["gatk", "CollectWgsMetrics",
         "-R", str(ref), "-I", str(bam), "-O", str(wgs_out)],
        picard_sif or "data/images/gatk4.sif",
        [ref.parent, bam.parent, out_dir],
    )
    run_tool(
        ["gatk", "CollectInsertSizeMetrics",
         "-I", str(bam), "-O", str(insert_out), "-H", str(insert_hist)],
        picard_sif or "data/images/gatk4.sif",
        [bam.parent, out_dir],
    )

    require_path(wgs_out, "WGS metrics output")
    require_path(insert_out, "Insert size metrics output")

    manifest = build_manifest_envelope(
        stage="collect_wgs_metrics",
        assumptions=[
            "Input BAM must be coordinate-sorted and indexed.",
            "Reference has .fai and .dict present.",
            "Both Picard tools are bundled in the GATK4 SIF.",
        ],
        inputs={"reference_fasta": str(ref), "aligned_bam": str(bam), "sample_id": sample_id},
        outputs={"wgs_metrics": str(wgs_out), "insert_size_metrics": str(insert_out)},
    )
    _write_json(out_dir / "run_manifest_collect_wgs_metrics.json", manifest)
    return File(path=str(wgs_out)), File(path=str(insert_out))
```

```python
@variant_calling_env.task
def bcftools_stats(
    input_vcf: File,
    cohort_id: str,
    bcftools_sif: str = "",
) -> File:
    """Run bcftools stats on a VCF/GVCF; return the stats text file."""
    vcf = require_path(Path(input_vcf.download_sync()), "Input VCF")
    out_dir = project_mkdtemp("bcftools_stats_")
    out_txt = out_dir / f"{cohort_id}_bcftools_stats.txt"

    cmd_str = f"bcftools stats {shlex.quote(str(vcf))} > {shlex.quote(str(out_txt))}"
    # bcftools stats writes to stdout; shell redirect is the only clean way.
    # Route through run_tool's shell path or plain subprocess with quoted paths.
    ...

    manifest = build_manifest_envelope(
        stage="bcftools_stats",
        assumptions=[
            "Input VCF must be valid; malformed records cause non-zero exit.",
            "Output is plain text; MultiQC parses the standard format.",
        ],
        inputs={"input_vcf": str(vcf), "cohort_id": cohort_id},
        outputs={"bcftools_stats_txt": str(out_txt)},
    )
    _write_json(out_dir / "run_manifest_bcftools_stats.json", manifest)
    return File(path=str(out_txt))
```

```python
@variant_calling_env.task
def multiqc_summarize(
    qc_inputs: list[File],
    cohort_id: str,
    multiqc_sif: str = "",
) -> File:
    """Aggregate one or more QC tool outputs into a single MultiQC HTML report.

    Copies each input into a fresh scan directory before running MultiQC so
    the report is self-contained and deterministic regardless of original
    file locations.
    """
    if not qc_inputs:
        raise ValueError("qc_inputs must not be empty")

    out_dir = project_mkdtemp("multiqc_")
    scan_root = out_dir / "scan"
    scan_root.mkdir()
    for qc_file in qc_inputs:
        src = require_path(Path(qc_file.download_sync()), "MultiQC input")
        shutil.copy2(src, scan_root / src.name)

    report_html = out_dir / f"{cohort_id}_multiqc.html"
    run_tool(
        ["multiqc", str(scan_root), "-n", report_html.name, "-o", str(out_dir)],
        multiqc_sif,
        [scan_root, out_dir],
    )
    require_path(report_html, "MultiQC HTML report")

    manifest = build_manifest_envelope(
        stage="multiqc_summarize",
        assumptions=[
            "MultiQC auto-detects Picard, bcftools, FastQC, and GATK MarkDuplicates outputs by filename patterns.",
            "Scan root is populated deterministically by copying inputs; no reliance on caller directory layouts.",
        ],
        inputs={"qc_input_count": len(qc_inputs), "cohort_id": cohort_id},
        outputs={"multiqc_report_html": str(report_html)},
    )
    _write_json(out_dir / "run_manifest_multiqc_summarize.json", manifest)
    return File(path=str(report_html))
```

Extend `MANIFEST_OUTPUT_KEYS` with `"wgs_metrics"`,
`"insert_size_metrics"`, `"bcftools_stats_txt"`,
`"multiqc_report_html"`.

### `src/flytetest/workflows/variant_calling.py`

```python
@variant_calling_env.task
def pre_call_coverage_qc(
    reference_fasta: File,
    aligned_bams: list[File],
    sample_ids: list[str],
    cohort_id: str,
    picard_sif: str = "",
    multiqc_sif: str = "",
) -> File:
    """Per-sample WGS + insert-size metrics aggregated into one MultiQC report."""
    if len(aligned_bams) != len(sample_ids):
        raise ValueError("aligned_bams and sample_ids must be the same length")

    qc_files: list[File] = []
    for bam, sid in zip(aligned_bams, sample_ids):
        wgs, insert = collect_wgs_metrics(
            reference_fasta=reference_fasta, aligned_bam=bam,
            sample_id=sid, picard_sif=picard_sif,
        )
        qc_files.extend([wgs, insert])

    return multiqc_summarize(qc_inputs=qc_files, cohort_id=cohort_id, multiqc_sif=multiqc_sif)
```

```python
@variant_calling_env.task
def post_call_qc_summary(
    input_vcf: File,
    cohort_id: str,
    extra_qc_files: list[File] | None = None,
    bcftools_sif: str = "",
    multiqc_sif: str = "",
) -> File:
    """bcftools stats + MultiQC; optional extra_qc_files merges additional tool logs."""
    stats = bcftools_stats(input_vcf=input_vcf, cohort_id=cohort_id, bcftools_sif=bcftools_sif)
    qc_files = [stats, *(extra_qc_files or [])]
    return multiqc_summarize(qc_inputs=qc_files, cohort_id=cohort_id, multiqc_sif=multiqc_sif)
```

Extend workflow-module `MANIFEST_OUTPUT_KEYS` with
`"pre_call_qc_bundle"`, `"post_call_qc_bundle"`.

### Registry entries

Five new entries (three tasks + two workflows), each with
`showcase_module`, `biological_stage`, accepted/produced planner types,
`slurm_resource_hints` sized for QC (CPU-light; memory scales with
cohort size for MultiQC).

- `collect_wgs_metrics`: stage 18, produces no planner type (metrics
  are artifacts, not pipeline state).
- `bcftools_stats`: stage 19, produces no planner type.
- `multiqc_summarize`: stage 20, produces no planner type.
- `pre_call_coverage_qc`: workflow stage 9.
- `post_call_qc_summary`: workflow stage 10.

### Bundles

Add an optional `multiqc_sif` key to the existing `variant_calling_*`
bundles' `runtime_images` so callers have a one-liner path.

### Tests

`tests/test_variant_calling.py`:

- `CollectWgsMetricsTests` — 3 tests (both outputs returned; missing
  output raises; manifest records both paths).
- `BcftoolsStatsTests` — 2 tests (stats file produced; shell-quoted
  paths don't break).
- `MultiqcSummarizeTests` — 3 tests (empty `qc_inputs` raises; copy
  semantics produce deterministic scan root; report path recorded in
  manifest).

`tests/test_variant_calling_workflows.py`:

- `PreCallCoverageQcWorkflowTests` — 2 tests.
- `PostCallQcSummaryWorkflowTests` — 2 tests (including
  `extra_qc_files` propagation to MultiQC).

Update `tests/test_registry_manifest_contract.py` with the five new
entries.

### Docs

- `docs/tool_refs/` — create `picard_wgs_metrics.md`, `bcftools.md`,
  `multiqc.md` if not already present, each following the `README.md`
  preferred structure (Purpose, Input/Output Data, Official
  Documentation, Native Command Context, Apptainer Command Context,
  Prompt Template, Notes And Caveats).
- `docs/gatk_pipeline_overview.md` — update DAG diagram and task /
  workflow tables.

## CHANGELOG

```
### GATK Milestone I Step 05 — QC bookends (YYYY-MM-DD)
- [x] YYYY-MM-DD added collect_wgs_metrics (Picard, stage 18), bcftools_stats (stage 19), multiqc_summarize (stage 20).
- [x] YYYY-MM-DD added pre_call_coverage_qc (workflow stage 9) and post_call_qc_summary (workflow stage 10).
- [x] YYYY-MM-DD MultiQC aggregates deterministically via scan-root copy semantics.
- [x] YYYY-MM-DD registry entries wired with showcase_module.
- [x] YYYY-MM-DD added 12 tests (8 task + 4 workflow).
- [x] YYYY-MM-DD tool refs: picard_wgs_metrics.md, bcftools.md, multiqc.md.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_variant_calling.py tests/test_variant_calling_workflows.py tests/test_registry.py tests/test_registry_manifest_contract.py -xvs
rg "collect_wgs_metrics|bcftools_stats|multiqc_summarize" src/flytetest/registry/_variant_calling.py | wc -l
# expected: ≥ 3
test -f docs/tool_refs/multiqc.md && echo "multiqc tool ref present"
```

## Commit message

```
variant_calling: add QC bookends (Picard WGS metrics + bcftools stats + MultiQC summary)
```

## Checklist

- [ ] Three new tasks landed with typed File I/O and run_tool.
- [ ] Two new workflows compose tasks into pre-/post-call QC bundles.
- [ ] `MANIFEST_OUTPUT_KEYS` extended on both modules.
- [ ] Registry entries include `showcase_module`.
- [ ] MultiQC scan root is deterministic (copy-in, not reference).
- [ ] 12 new tests passing.
- [ ] Three new `docs/tool_refs/` files authored.
- [ ] Pipeline overview DAG and tables refreshed.
- [ ] Step 05 marked Complete in checklist.
