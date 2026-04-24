# Step 06 — Variant Annotation via SnpEff

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). SnpEff's CLI is fussy about
database names and data-directory layout; careful transcription from
the manual is required.

## Goal

1. Add `snpeff_annotate` task wrapping `snpEff ann`.
2. Add `annotate_variants_snpeff` workflow as a thin single-task
   wrapper.
3. Registry entries, tool ref, tests.

## Context

- Milestone I plan §4 Step 06 — SnpEff chosen over VEP for Milestone I
  (simpler local-SIF workflow; no ENSEMBL cache dependency).
- SnpEff manual: `http://pcingola.github.io/SnpEff/`
- Database names: `GRCh38.105`, `hg38`, `GRCh38.mane.1.2.ensembl`,
  etc. Callers supply the exact name and the data directory containing
  the pre-downloaded database.
- Branch: `gatkport-i`.

## What to build

### `src/flytetest/tasks/variant_calling.py`

```python
@variant_calling_env.task
def snpeff_annotate(
    input_vcf: File,
    cohort_id: str,
    snpeff_database: str,
    snpeff_data_dir: str,
    snpeff_sif: str = "",
) -> tuple[File, File]:
    """Annotate a VCF with SnpEff; return (annotated_vcf, genes_summary_txt).

    snpeff_database: database identifier (e.g. "GRCh38.105", "hg38").
    snpeff_data_dir: directory containing the pre-downloaded database
        cache. Must be staged on shared FS for Slurm runs (see
        check_offline_staging).
    """
    vcf = require_path(Path(input_vcf.download_sync()), "Input VCF")
    data_dir = require_path(Path(snpeff_data_dir), "SnpEff data directory")

    out_dir = project_mkdtemp("snpeff_")
    annotated_vcf = out_dir / f"{cohort_id}_snpeff.vcf"
    stats_html = out_dir / f"{cohort_id}_snpeff_summary.html"
    genes_txt = out_dir / f"{cohort_id}_snpeff_summary.genes.txt"

    # snpEff writes to stdout; shell redirect is standard.
    # Use bash -c so run_tool's container path still applies.
    cmd_str = (
        f"snpEff ann "
        f"-dataDir {shlex.quote(str(data_dir))} "
        f"-stats {shlex.quote(str(stats_html))} "
        f"{shlex.quote(snpeff_database)} "
        f"{shlex.quote(str(vcf))} "
        f"> {shlex.quote(str(annotated_vcf))}"
    )
    run_tool(
        ["bash", "-c", cmd_str],
        snpeff_sif,
        [vcf.parent, data_dir, out_dir],
    )

    require_path(annotated_vcf, "SnpEff annotated VCF")
    # genes_txt is emitted alongside stats_html; guard against missing.
    genes_path_str = str(genes_txt) if genes_txt.exists() else ""

    manifest = build_manifest_envelope(
        stage="snpeff_annotate",
        assumptions=[
            "snpeff_data_dir contains the pre-downloaded database for snpeff_database.",
            "SnpEff writes annotation fields into INFO; original VCF records are preserved.",
            "Database cache is NOT downloaded at runtime; compute nodes typically have no internet.",
        ],
        inputs={
            "input_vcf": str(vcf),
            "cohort_id": cohort_id,
            "snpeff_database": snpeff_database,
            "snpeff_data_dir": str(data_dir),
        },
        outputs={
            "snpeff_vcf": str(annotated_vcf),
            "snpeff_genes_txt": genes_path_str,
            "snpeff_summary_html": str(stats_html) if stats_html.exists() else "",
        },
    )
    _write_json(out_dir / "run_manifest_snpeff_annotate.json", manifest)
    return File(path=str(annotated_vcf)), File(path=str(genes_txt))
```

Extend `MANIFEST_OUTPUT_KEYS` with `"snpeff_vcf"` and
`"snpeff_genes_txt"`.

### `src/flytetest/workflows/variant_calling.py`

```python
@variant_calling_env.task
def annotate_variants_snpeff(
    input_vcf: File,
    cohort_id: str,
    snpeff_database: str,
    snpeff_data_dir: str,
    snpeff_sif: str = "",
) -> File:
    """Thin wrapper: annotate a VCF with SnpEff; return the annotated VCF."""
    annotated_vcf, _genes = snpeff_annotate(
        input_vcf=input_vcf,
        cohort_id=cohort_id,
        snpeff_database=snpeff_database,
        snpeff_data_dir=snpeff_data_dir,
        snpeff_sif=snpeff_sif,
    )
    # Workflow manifest tracks annotated_vcf.
    ...
    return annotated_vcf
```

Extend workflow-module `MANIFEST_OUTPUT_KEYS` with `"annotated_vcf"`.

### Registry entries

- `snpeff_annotate`: task, `pipeline_stage_order=21`,
  `accepted_planner_types=("VariantCallSet",)`,
  `produced_planner_types=("VariantCallSet",)`,
  `showcase_module="flytetest.tasks.variant_calling"`.
  Declare `snpeff_data_dir` as a `tool_database`-shaped input in the
  registry so `check_offline_staging` can verify it for Slurm runs.
- `annotate_variants_snpeff`: workflow, `pipeline_stage_order=11`,
  `showcase_module="flytetest.workflows.variant_calling"`.

Tool-database metadata on the registry entry:

```python
composition_constraints=(
    "snpeff_data_dir must be staged on shared FS for Slurm submission.",
    "Database name must match an installed snpeff cache (e.g. GRCh38.105, hg38).",
),
```

### Bundles

Optional new bundle `variant_calling_snpeff_chr20` pointing at a
GRCh38.105 staged cache directory. Follow the pattern of
`variant_calling_vqsr_chr20`:

- `tool_databases={"snpeff_data_dir": "data/snpeff/data"}`.
- `fetch_hints` including the SnpEff download command:
  `scripts/rcc/download_snpeff_db.sh GRCh38.105`.

Also add `scripts/rcc/download_snpeff_db.sh` (parallel to
`download_vqsr_training_vcfs.sh`).

### `docs/tool_refs/snpeff.md`

New tool ref following the preferred structure:

- Purpose, Input/Output Data, Key Inputs/Outputs, Pipeline Fit.
- Official docs: `http://pcingola.github.io/SnpEff/`.
- Native command context.
- Apptainer command context.
- Prompt Template.
- Notes & Caveats: database cache must be pre-downloaded; no
  runtime fetching on compute nodes.

### Tests

`tests/test_variant_calling.py` — `SnpeffAnnotateTests`:

- `test_annotated_vcf_emitted` — cmd produces the output VCF; tuple
  return carries both File instances.
- `test_data_dir_quoted_and_bound` — `snpeff_data_dir` passes
  through `shlex.quote` and appears in `bind_paths`.
- `test_missing_output_raises` — output absent after run →
  `FileNotFoundError`.
- `test_genes_txt_optional_in_manifest` — when the companion genes
  file isn't emitted (empty VCF), manifest output reads `""`
  instead of raising.

`tests/test_variant_calling_workflows.py` — `AnnotateVariantsSnpeffWorkflowTests`:

- `test_workflow_returns_annotated_vcf` — workflow return is the
  annotated VCF, not the genes file.
- `test_workflow_threads_database_and_data_dir` — both are passed
  through unchanged to `snpeff_annotate`.

`tests/test_registry_manifest_contract.py` — add both new entries.

### Documentation updates

- `docs/gatk_pipeline_overview.md` — DAG gains an "annotate" terminal
  node after filter / refinement paths; task table adds stage 21;
  workflow table adds stage 11.
- `docs/tool_refs/stage_index.md` — new "variant annotation" stage
  entrypoint citing `snpeff_annotate` and `annotate_variants_snpeff`.

## CHANGELOG

```
### GATK Milestone I Step 06 — Variant annotation via SnpEff (YYYY-MM-DD)
- [x] YYYY-MM-DD added snpeff_annotate task (stage 21) and annotate_variants_snpeff workflow (stage 11).
- [x] YYYY-MM-DD tool database snpeff_data_dir wired; offline-staging preflight applies.
- [x] YYYY-MM-DD added scripts/rcc/download_snpeff_db.sh fetch helper.
- [x] YYYY-MM-DD optional variant_calling_snpeff_chr20 bundle added.
- [x] YYYY-MM-DD added 6 tests; docs/tool_refs/snpeff.md authored.
- Chose SnpEff over VEP for Milestone I simplicity; VEP remains a Milestone K candidate.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_variant_calling.py tests/test_variant_calling_workflows.py tests/test_registry.py tests/test_registry_manifest_contract.py -xvs
test -f docs/tool_refs/snpeff.md && echo "tool ref present"
rg "snpeff_annotate|annotate_variants_snpeff" src/flytetest/registry/_variant_calling.py | wc -l
# expected: ≥ 2
```

## Commit message

```
variant_calling: add SnpEff annotation (snpeff_annotate task + annotate_variants_snpeff workflow)
```

## Checklist

- [ ] `snpeff_annotate` task handles `shlex.quote`-ed paths and
      bash-redirect output.
- [ ] `annotate_variants_snpeff` workflow returns the annotated VCF only.
- [ ] Registry declares `snpeff_data_dir` as offline-staging-checkable.
- [ ] `MANIFEST_OUTPUT_KEYS` extended on both modules.
- [ ] 6 new tests passing.
- [ ] `docs/tool_refs/snpeff.md` authored.
- [ ] `scripts/rcc/download_snpeff_db.sh` added.
- [ ] Optional `variant_calling_snpeff_chr20` bundle added (if fixture path is feasible).
- [ ] Step 06 marked Complete in checklist.
