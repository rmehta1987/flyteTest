# GATK4 Germline Variant Calling — Milestone F

Interval-scoped HaplotypeCaller: extend the existing `haplotype_caller` task
with optional intervals, add a `gather_vcfs` merge task, and add a
`scattered_haplotype_caller` workflow that scatter-calls across intervals and
gathers per-interval GVCFs.

Source-of-truth references:

- `AGENTS.md`, `DESIGN.md`, `.codex/` — project rules and patterns.
- Milestones A–E plans under `docs/gatk_milestone_*/`.
- No Stargazer reference for this milestone — design from GATK Best Practices
  (GATK docs: HaplotypeCaller `-L` flag, GatherVcfs tool).

## §1 Context

The existing `haplotype_caller` task runs whole-genome (no `-L` intervals).
For large genomes or large cohorts, scattered calling — splitting the genome
into interval chunks, calling each chunk independently, then merging — is the
standard production path. Scatter-gather reduces per-task memory footprint and
enables parallelism within a single workflow call.

Milestones A–E covered alignment, preprocessing, BQSR, joint calling, VQSR,
and the uBAM path. Milestone F adds interval scattering as the missing
production-scale feature for the per-sample GVCF generation step.

## §2 Pillars / Invariants

Same four pillars as Milestones A–E. No new exceptions.

## §3 Data Model

### No new planner type

Intervals are `list[str]` (e.g., `["chr1", "chr2:1-50000000"]`), already used
throughout the pipeline.

### New `MANIFEST_OUTPUT_KEYS` additions — tasks module

```python
"gathered_gvcf",    # gather_vcfs
```

### New `MANIFEST_OUTPUT_KEYS` additions — workflows module

```python
"scattered_gvcf",   # scattered_haplotype_caller
```

### Registry stage orders

| stage_order | item |
|---|---|
| 1–14 | Milestones A–E (unchanged) |
| — | `haplotype_caller` extended (no new stage; backward compatible) |
| 15 | `gather_vcfs` (new task) |

Workflow uses `pipeline_stage_order` 6.

## §4 Implementation Notes

### Extending `haplotype_caller` (backward compatible)

Add `intervals: list[str] = None` parameter (default `None` = whole-genome,
preserving existing behavior). When non-empty, append one `-L <interval>` flag
per entry:

```python
for interval in (intervals or []):
    cmd.extend(["-L", interval])
```

Output filename remains `<sample_id>.g.vcf` (unchanged). The manifest key
`"gvcf"` is unchanged.

### gather_vcfs

```
gatk GatherVcfs \
  -I <gvcf1> -I <gvcf2> ... \
  -O <sample_id>_gathered.g.vcf.gz \
  --CREATE_INDEX true
```

`GatherVcfs` (Picard) concatenates pre-sorted, non-overlapping VCFs in order.
Inputs must be in genomic order matching the interval order passed to
`scattered_haplotype_caller`. Output is always `.vcf.gz` with companion `.tbi`.

Signature:

```python
def gather_vcfs(
    gvcf_paths: list[str],
    sample_id: str,
    results_dir: str,
    sif_path: str = "",
) -> dict:
```

Raises `ValueError` if `gvcf_paths` is empty. Raises `FileNotFoundError` if
output is absent after run.

Manifest outputs: `{"gathered_gvcf": str(out_vcf)}`.

### scattered_haplotype_caller workflow

```python
interval_gvcfs = []
for i, interval in enumerate(intervals):
    result = haplotype_caller(
        ref_path, bam_path, sample_id,
        results_dir=f"{results_dir}/interval_{i:04d}/",
        intervals=[interval], sif_path=sif_path)
    interval_gvcfs.append(result["outputs"]["gvcf"])

gathered = gather_vcfs(interval_gvcfs, sample_id, results_dir, sif_path)
emit manifest: scattered_gvcf = gathered["outputs"]["gathered_gvcf"]
```

Each interval writes to its own subdirectory (`interval_0000/`,
`interval_0001/`, …) to avoid output filename collisions. Raises `ValueError`
if `intervals` is empty.

## §5 Backward Compatibility

- `haplotype_caller` signature change is backward compatible: `intervals=None`
  produces identical behavior to the pre-Milestone-F task.
- All existing tests for `haplotype_caller` continue to pass unchanged.
- New `gather_vcfs` task and `scattered_haplotype_caller` workflow are additive.

## §6 Steps

| # | Step | Prompt |
|---|------|--------|
| 01 | Extend `haplotype_caller` with optional intervals | `prompts/step_01_haplotype_caller_intervals.md` |
| 02 | `gather_vcfs` task + registry entry + tests | `prompts/step_02_gather_vcfs.md` |
| 03 | `scattered_haplotype_caller` workflow + registry entry + tests | `prompts/step_03_scattered_haplotype_caller.md` |
| 04 | Closure | `prompts/step_04_closure.md` |

## §7 Out of Scope (this milestone)

- Parallel interval dispatch (job arrays) — still deferred; this milestone
  uses a sequential Python for loop within one Slurm job.
- `SplitIntervals` (GATK interval splitting tool) — user supplies intervals.
- `MergeVcfs` as alternative to `GatherVcfs` — not needed for non-overlapping
  intervals; `GatherVcfs` is the canonical GATK Best Practices choice.
- `CalculateGenotypePosteriors` — Milestone G.

## §8 Verification Gates

- `python -m compileall src/flytetest/` clean.
- `pytest tests/test_variant_calling.py -xvs` green.
- `pytest tests/test_variant_calling_workflows.py -xvs` green.
- `pytest tests/test_registry_manifest_contract.py -xvs` green.
- `pytest` full suite green.
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits.
- `rg "gather_vcfs|scattered_haplotype_caller" src/flytetest/registry/_variant_calling.py` → matches.
- Existing `HaplotypeCallerInvocationTests` still pass (no regression from intervals addition).
