# GATK4 Germline Variant Calling — Milestone E

uBAM preprocessing path: `UnmappedBAM` planner type, `merge_bam_alignment`
task, and `preprocess_sample_from_ubam` workflow.

Source-of-truth references:

- `AGENTS.md` — hard constraints, efficiency notes, core rules.
- `DESIGN.md` — biological pipeline boundaries, planner types.
- `.codex/tasks.md`, `.codex/registry.md`, `.codex/workflows.md` — patterns.
- Milestones A–D plans under `docs/gatk_milestone_*/`.
- Stargazer reference (read-only):
  `stargazer/src/stargazer/tasks/gatk/merge_bam_alignment.py`

## §1 Context

Milestones A–D delivered the full germline pipeline from raw FASTQ reads to a
VQSR-refined VCF. The existing `preprocess_sample` workflow accepts paired
FASTQ as input. GATK Best Practices supports an alternative starting point:
an unmapped BAM (uBAM) that preserves original base qualities (OQ tag) and
per-read metadata. `MergeBamAlignment` merges the BWA-MEM2 aligned BAM with
the uBAM to produce a coordinate-sorted merged BAM that retains both alignment
and original read metadata.

- **Milestones A–D** (complete) — full FASTQ-in → VQSR-refined VCF pipeline.
- **Milestone E** (this plan) — uBAM-in alternative preprocessing path.
- **Milestone F** (next) — interval-scoped HaplotypeCaller.
- **Milestone G** (next) — CalculateGenotypePosteriors + GATK closure.

## §2 Pillars / Invariants (carried from Milestones A–D)

1. **Freeze before execute.** Tasks emit `run_manifest.json` via
   `build_manifest_envelope`.
2. **Typed surfaces everywhere.** New planner type inherits `PlannerSerializable`.
3. **Manifest envelope per task.** Every task and workflow emits
   `run_manifest.json`.
4. **No Stargazer-pattern bleed-in.** No `async def`, `await`, `asyncio.gather`,
   `.cid`, IPFS, Pinata, or TinyDB.

## §3 Data Model

### New planner type: `UnmappedBAM`

```python
@dataclass(frozen=True)
class UnmappedBAM(PlannerSerializable):
    """An unmapped BAM file with original read metadata preserved."""
    bam_path: str
    sample_id: str
```

Unmapped BAMs must be queryname-sorted (GATK requirement for `MergeBamAlignment`).

### New `MANIFEST_OUTPUT_KEYS` additions — tasks module

```python
"merged_bam",    # merge_bam_alignment
```

### New `MANIFEST_OUTPUT_KEYS` additions — workflows module

```python
"preprocessed_bam_from_ubam",   # preprocess_sample_from_ubam
```

### Registry stage orders

| stage_order | task |
|---|---|
| 1–13 | Milestones A–D (unchanged) |
| 14 | `merge_bam_alignment` |

Workflow uses `pipeline_stage_order` 5 within category `"workflow"`.

## §4 Implementation Notes

### merge_bam_alignment

```
gatk MergeBamAlignment \
  -R <ref.fa> \
  -ALIGNED <aligned.bam> \
  -UNMAPPED <ubam> \
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

Flags come from Stargazer reference. `--SORT_ORDER coordinate` means no
separate `sort_sam` step is needed. `--CREATE_INDEX true` writes a `.bai`.
Raises `FileNotFoundError` if `<sample_id>_merged.bam` is absent after run.

### preprocess_sample_from_ubam workflow

```
bwa_mem2_mem(ref_path, r1_path, r2_path, sample_id, results_dir, sif_path)
→ aligned_bam

merge_bam_alignment(ref_path, aligned_bam, ubam_path, sample_id,
                    results_dir, sif_path)
→ merged_bam

mark_duplicates(merged_bam, sample_id, results_dir, sif_path)
→ deduped

base_recalibrator(ref_path, deduped, known_sites, sample_id, sif_path)
→ bqsr_table

apply_bqsr(ref_path, deduped, bqsr_table, sample_id, sif_path)
→ recal_bam

emit manifest: preprocessed_bam_from_ubam = recal_bam
```

No `sort_sam` step — `MergeBamAlignment` coordinates-sorts the output.
Input: `ubam_path: str` (absolute path to queryname-sorted uBAM) alongside
the usual FASTQ R1/R2 pair.

## §5 Backward Compatibility

Milestone E is purely additive:

- New `UnmappedBAM` planner type; existing types unchanged.
- New `merge_bam_alignment` task appended to `variant_calling.py`.
- New `preprocess_sample_from_ubam` workflow appended to
  `workflows/variant_calling.py`.
- New registry entries appended to `VARIANT_CALLING_ENTRIES`.
- `MANIFEST_OUTPUT_KEYS` in tasks and workflows modules extended (new keys only).

## §6 Steps

| # | Step | Prompt |
|---|------|--------|
| 01 | `UnmappedBAM` planner type + round-trip tests | `prompts/step_01_unmapped_bam_type.md` |
| 02 | `merge_bam_alignment` task + registry entry + unit tests | `prompts/step_02_merge_bam_alignment.md` |
| 03 | `preprocess_sample_from_ubam` workflow + registry entry + unit tests | `prompts/step_03_preprocess_sample_from_ubam.md` |
| 04 | Closure — tool ref, CHANGELOG, submission prompt | `prompts/step_04_closure.md` |

## §7 Out of Scope (this milestone)

- `RevertSam` (converting FASTQ to uBAM) — users supply pre-existing uBAMs.
- `SamToFastq` (extracting FASTQs from uBAM) — out of scope.
- Interval-scoped HaplotypeCaller — Milestone F.
- `CalculateGenotypePosteriors` — Milestone G.

## §8 Verification Gates

- `python -m compileall src/flytetest/` clean.
- `pytest tests/test_variant_calling.py -xvs` green.
- `pytest tests/test_variant_calling_workflows.py -xvs` green.
- `pytest tests/test_registry_manifest_contract.py -xvs` green.
- `pytest tests/test_planner_types.py -xvs` green (UnmappedBAM round-trips).
- `pytest` full suite green.
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits.
- `rg "merge_bam_alignment|preprocess_sample_from_ubam" src/flytetest/registry/_variant_calling.py` → matches.

## §9 Hard Constraints

- No frozen-artifact mutation at retry/replay time.
- No Slurm submit without a frozen run record.
- No async/IPFS/TinyDB patterns.
- `RevertSam` and `SamToFastq` are out of scope.
