# Step 01 — Port Preprocessing Helpers to Flyte Task Pattern

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Four task signatures change and
one workflow body is rewired; Haiku risks missing the subtle
`.outputs["..."]` → `.path` translations that show up in mocked tests.

## Goal

1. Port `bwa_mem2_index`, `bwa_mem2_mem`, `sort_sam`, and
   `mark_duplicates` from plain-Python helpers with `str` paths and
   `dict` returns to `@variant_calling_env.task` functions with
   `File`/`Dir` I/O and `run_tool()` wrapping.
2. Parameterize read-group fields in `bwa_mem2_mem` (`library_id`,
   `platform`).
3. Update `preprocess_sample` workflow to consume `File`/`Dir` returns.
4. Update existing tests for the four tasks plus `preprocess_sample`.

## Context

- Milestone I plan §3 (signature table) and §4 Step 01.
- `.codex/tasks.md` — `File`/`Dir` I/O + `run_tool()` + `project_mkdtemp()`
  patterns.
- Pattern reference: Milestone A tasks (`create_sequence_dictionary`,
  `base_recalibrator`) already use the target pattern.
- Branch: `gatkport-i` (created after Milestone H merges).

## What to build

### `src/flytetest/tasks/variant_calling.py`

**`bwa_mem2_index`** (currently line ~414). New signature:

```python
@variant_calling_env.task
def bwa_mem2_index(
    reference_fasta: File,
    gatk_sif: str = "",
) -> Dir:
    """Index a reference FASTA for BWA-MEM2 alignment."""
    ref = require_path(Path(reference_fasta.download_sync()), "Reference FASTA")
    out_dir = project_mkdtemp("bwa_mem2_index_")
    index_prefix = out_dir / ref.stem

    cmd = ["bwa-mem2", "index", "-p", str(index_prefix), str(ref)]
    run_tool(cmd, gatk_sif or "data/images/gatk4.sif", [ref.parent, out_dir])

    # Assert all expected index files exist.
    for suffix in (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"):
        if not Path(f"{index_prefix}{suffix}").exists():
            raise FileNotFoundError(f"bwa-mem2 index missing: {index_prefix}{suffix}")

    # Manifest (per-stage filename from Milestone H)
    manifest = build_manifest_envelope(
        stage="bwa_mem2_index",
        assumptions=["Reference FASTA readable; no pre-existing conflicting index files."],
        inputs={"reference_fasta": str(ref)},
        outputs={"bwa_index_prefix": str(index_prefix)},
    )
    _write_json(out_dir / f"run_manifest_bwa_mem2_index.json", manifest)
    return Dir(path=str(out_dir))
```

**`bwa_mem2_mem`** (currently line ~450). New signature with RG params:

```python
@variant_calling_env.task
def bwa_mem2_mem(
    reference_fasta: File,
    r1: File,
    sample_id: str,
    r2: File | None = None,
    threads: int = 4,
    library_id: str | None = None,
    platform: str = "ILLUMINA",
    gatk_sif: str = "",
) -> File:
    """Align paired-end FASTQ reads to a reference using BWA-MEM2."""
    ref = require_path(Path(reference_fasta.download_sync()), "Reference FASTA")
    r1_path = require_path(Path(r1.download_sync()), "R1 FASTQ")
    r2_path = require_path(Path(r2.download_sync()), "R2 FASTQ") if r2 is not None else None
    lib = library_id or f"{sample_id}_lib"

    out_dir = project_mkdtemp("bwa_mem2_mem_")
    out_bam = out_dir / f"{sample_id}_aligned.bam"

    # Continue to quote every user-supplied path via shlex.quote (Milestone H Step 01).
    rg = f"@RG\\tID:{sample_id}\\tSM:{sample_id}\\tLB:{lib}\\tPL:{platform}"
    # Rest of pipeline per Milestone H shape; wrap via run_tool when sif_path set.
    ...
```

Use `run_tool` with a list command when no shell piping is required; for
the `bwa-mem2 mem | samtools view` pipeline keep the quoted-bash pattern
from Milestone H Step 01, but invoke it through the container when
`gatk_sif` is set so bind-paths are consistent with the rest of the module.

**`sort_sam`** (currently line ~509). New signature:

```python
@variant_calling_env.task
def sort_sam(
    aligned_bam: File,
    sample_id: str,
    gatk_sif: str = "",
) -> File:
    """Coordinate-sort a BAM file using GATK SortSam."""
```

Return the sorted BAM `File`; drop `results_dir` in favor of
`project_mkdtemp`.

**`mark_duplicates`** (currently line ~554). New signature with tuple
return because both outputs matter downstream:

```python
@variant_calling_env.task
def mark_duplicates(
    sorted_bam: File,
    sample_id: str,
    gatk_sif: str = "",
) -> tuple[File, File]:
    """Mark PCR/optical duplicates; returns (dedup_bam, metrics_file)."""
```

### `src/flytetest/workflows/variant_calling.py`

Update `preprocess_sample` body to consume `File` returns:

```python
@variant_calling_env.task
def preprocess_sample(
    reference_fasta: File,
    r1: File,
    sample_id: str,
    known_sites: list[File],
    r2: File | None = None,
    threads: int = 4,
    library_id: str | None = None,
    platform: str = "ILLUMINA",
    gatk_sif: str = "",
) -> File:
    aligned = bwa_mem2_mem(
        reference_fasta=reference_fasta, r1=r1, r2=r2,
        sample_id=sample_id, threads=threads,
        library_id=library_id, platform=platform, gatk_sif=gatk_sif,
    )
    sorted_bam = sort_sam(aligned_bam=aligned, sample_id=sample_id, gatk_sif=gatk_sif)
    dedup_bam, _metrics = mark_duplicates(sorted_bam=sorted_bam, sample_id=sample_id, gatk_sif=gatk_sif)
    bqsr_table = base_recalibrator(
        reference_fasta=reference_fasta, aligned_bam=dedup_bam,
        known_sites=known_sites, sample_id=sample_id, gatk_sif=gatk_sif,
    )
    recal_bam = apply_bqsr(
        reference_fasta=reference_fasta, aligned_bam=dedup_bam,
        bqsr_report=bqsr_table, sample_id=sample_id, gatk_sif=gatk_sif,
    )
    # Workflow-level manifest stays at run_manifest.json (per H Step 01).
    ...
    return recal_bam
```

Note the signature change: `preprocess_sample` now returns a `File`
(the recalibrated BAM) instead of a `dict`. The sole downstream
consumer, `germline_short_variant_discovery`, is updated in Step 02.

### Registry entries (`src/flytetest/registry/_variant_calling.py`)

Update the four task entries and `preprocess_sample` entry:

- `inputs` tuples now reflect `File`/`Dir` types.
- Drop `results_dir` from each `inputs` tuple.
- Add `library_id` (str, optional) and `platform` (str, optional) to
  `bwa_mem2_mem`.
- Update `preprocess_sample` `inputs` to use typed planner-binding
  semantics (`ReferenceGenome`, `ReadPair`, `KnownSites`) consistently.
- Set `produced_planner_types=("AlignmentSet",)` on `mark_duplicates`
  and `sort_sam` since the output BAM moves the planner state forward.

### Tests

Update existing `test_variant_calling.py` classes for the four ported
tasks. Changes:

- Mock inputs become `File(path=...)` / `Dir(path=...)` instances.
- Assertions on returns become `.path` accesses instead of
  `result["outputs"]["..."]` accesses.
- `bwa_mem2_mem` gets three new tests:
  - `test_bwa_mem2_mem_default_library_id` — asserts RG has
    `LB:{sample_id}_lib` when `library_id` omitted.
  - `test_bwa_mem2_mem_explicit_library_id` — asserts RG reflects the
    explicit `library_id`.
  - `test_bwa_mem2_mem_platform_override` — asserts `PL:PACBIO` when
    `platform="PACBIO"`.

Update `test_variant_calling_workflows.py`:

- `preprocess_sample` tests mock `File`/`Dir` inputs and unpack `File`
  returns.

Update `tests/test_registry_manifest_contract.py` to remove any
`results_dir` references for the ported tasks.

## CHANGELOG

```
### GATK Milestone I Step 01 — Port preprocessing helpers (YYYY-MM-DD)
- [x] YYYY-MM-DD ported bwa_mem2_index, bwa_mem2_mem, sort_sam, mark_duplicates to @variant_calling_env.task with File/Dir I/O.
- [x] YYYY-MM-DD bwa_mem2_mem gained library_id (default f"{sample_id}_lib") and platform (default "ILLUMINA").
- [x] YYYY-MM-DD preprocess_sample workflow updated to consume File returns; signature now returns File instead of dict.
- [x] YYYY-MM-DD registry entries updated; results_dir removed.
- [x] YYYY-MM-DD tests updated; 3 new RG tests added.
- [!] Breaking: bwa_mem2_index, bwa_mem2_mem, sort_sam, mark_duplicates signatures changed from (str, ..., results_dir) → (File, ...). External callers must migrate.
- [!] Breaking: preprocess_sample returns File not dict.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src \
  pytest tests/test_variant_calling.py tests/test_variant_calling_workflows.py tests/test_registry.py -xvs
rg "def (bwa_mem2_index|bwa_mem2_mem|sort_sam|mark_duplicates)" src/flytetest/tasks/variant_calling.py -B1
# every match must be preceded by @variant_calling_env.task
rg "results_dir" src/flytetest/tasks/variant_calling.py | rg "(bwa_mem2|sort_sam|mark_duplicates)"
# expected: zero hits
```

## Commit message

```
variant_calling: port preprocessing helpers to Flyte task pattern + RG params
```

## Checklist

- [ ] All four tasks decorated with `@variant_calling_env.task`.
- [ ] Signatures take `File`/`Dir` (no `str` paths, no `results_dir`).
- [ ] `bwa_mem2_mem` accepts `library_id` (default
      `f"{sample_id}_lib"`) and `platform` (default `"ILLUMINA"`).
- [ ] `preprocess_sample` returns `File`, not `dict`.
- [ ] Registry entries updated.
- [ ] 3 new RG tests passing; existing tests migrated and passing.
- [ ] CHANGELOG breaking-change notes present.
- [ ] Step 01 marked Complete in checklist.
