# Step 03 — `bwa_mem2_mem` Task

## Goal

Add the `bwa_mem2_mem` task to `src/flytetest/tasks/variant_calling.py`
and register it in `src/flytetest/registry/_variant_calling.py`.

## Context

- Plan §4: `docs/gatk_milestone_b/milestone_b_plan.md`.
- Stargazer reference (command args and read-group pattern):
  `stargazer/src/stargazer/tasks/general/bwa_mem2.py` — `bwa_mem2_mem`.
- `ReadPair` planner type is available from Step 01.

## Command shape

```
bwa-mem2 mem -R '@RG\tID:<sample_id>\tSM:<sample_id>\tLB:lib\tPL:ILLUMINA' \
  -t <threads> <ref.fa> <r1.fq.gz> [r2.fq.gz] \
  | samtools view -bS -o <sample_id>_aligned.bam -
```

This is a shell pipeline — BWA-MEM2 writes SAM to stdout; samtools converts
to BAM inline.

## What to build

### Task signature

```python
def bwa_mem2_mem(
    ref_path: str,
    r1_path: str,
    sample_id: str,
    results_dir: str,
    r2_path: str = "",
    threads: int = 4,
    sif_path: str = "",
) -> dict:
```

### Pipeline execution

Do NOT use `run_tool` directly — it does not support shell pipes. Use:

```python
import subprocess
pipeline = (
    f"bwa-mem2 mem "
    f"-R '@RG\\tID:{sample_id}\\tSM:{sample_id}\\tLB:lib\\tPL:ILLUMINA' "
    f"-t {threads} {ref_path} {r1_path}"
    + (f" {r2_path}" if r2_path else "")
    + f" | samtools view -bS -o {output_bam} -"
)
result = subprocess.run(pipeline, shell=True, capture_output=True, text=True)
if result.returncode != 0:
    raise RuntimeError(f"bwa_mem2_mem failed:\n{result.stderr}")
```

When `sif_path` is set, wrap the pipeline:

```python
apptainer_cmd = f"apptainer exec {sif_path} bash -c {shlex.quote(pipeline)}"
result = subprocess.run(apptainer_cmd, shell=True, capture_output=True, text=True)
```

### Output

- `<results_dir>/<sample_id>_aligned.bam` — unsorted BAM.
- Raise `FileNotFoundError` if the BAM is absent after the run.
- Manifest key: `"aligned_bam"`.

### `MANIFEST_OUTPUT_KEYS` addition

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    ...,
    "bwa_index_prefix",
    "aligned_bam",  # ← new
)
```

### Registry entry

```python
RegistryEntry(
    name="bwa_mem2_mem",
    category="task",
    description="Align paired-end FASTQ reads to a reference using BWA-MEM2.",
    pipeline_family="variant_calling",
    pipeline_stage_order=9,
    showcase_module="",
    accepted_planner_types=("ReferenceGenome", "ReadPair"),
    produced_planner_types=("AlignmentSet",),
    inputs=[
        InterfaceField("ref_path", "str", "Absolute path to reference FASTA."),
        InterfaceField("r1_path", "str", "Absolute path to R1 FASTQ."),
        InterfaceField("sample_id", "str", "Sample identifier."),
        InterfaceField("results_dir", "str", "Output directory."),
        InterfaceField("r2_path", "str", "Optional R2 FASTQ path (empty string for single-end)."),
        InterfaceField("threads", "int", "BWA-MEM2 alignment threads."),
        InterfaceField("sif_path", "str", "Optional GATK4/BWA SIF image path."),
    ],
    outputs=[
        InterfaceField("aligned_bam", "str", "Path to unsorted aligned BAM."),
    ],
    compatibility=RegistryCompatibilityMetadata(
        local_resources={"cpu": "8", "memory": "32Gi"},
        slurm_hints={"cpus_per_task": 16, "mem": "64G", "time": "08:00:00"},
    ),
)
```

### Tests (`tests/test_variant_calling.py`)

Add `BwaMem2MemRegistryTests`, `BwaMem2MemInvocationTests`,
`BwaMem2MemManifestTests` covering:

- Registry entry shape (stage_order=9, accepted_planner_types include ReadPair).
- Pipeline string contains `"bwa-mem2"`, `"mem"`, `"-R"`, ref_path, r1_path.
- R2 is appended when provided; absent when r2_path is empty.
- Read-group string contains `ID:<sample_id>` and `SM:<sample_id>`.
- Manifest emits `"aligned_bam"`.
- `RuntimeError` when subprocess returns non-zero (mock `subprocess.run`).

### `CHANGELOG.md`

```
### GATK Milestone B Step 03 — bwa_mem2_mem task (YYYY-MM-DD)
- [x] YYYY-MM-DD added `bwa_mem2_mem` using shell pipeline (bwa-mem2 | samtools view).
- [x] YYYY-MM-DD added `bwa_mem2_mem` registry entry (stage_order 9).
- [x] YYYY-MM-DD extended MANIFEST_OUTPUT_KEYS with `"aligned_bam"`.
- [x] YYYY-MM-DD added N tests; all tests passing.
```

## Commit message

```
variant_calling: add bwa_mem2_mem task + registry entry
```

## Checklist

- [ ] `bwa_mem2_mem` uses `subprocess.run(shell=True)` pipeline.
- [ ] Apptainer wrapping when `sif_path` is set.
- [ ] Output BAM existence checked post-run.
- [ ] `MANIFEST_OUTPUT_KEYS` extended with `"aligned_bam"`.
- [ ] Registry entry at stage_order=9.
- [ ] Tests: registry shape, pipeline string, R2 conditional, read-group, manifest, error.
- [ ] `pytest tests/test_variant_calling.py -xvs` green.
- [ ] CHANGELOG updated.
- [ ] Step 03 marked Complete in checklist.
