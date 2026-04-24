# GATK Milestone E — Submission Prompt

Branch: `gatkport-e`

Milestone E adds the uBAM preprocessing path to the germline variant calling
pipeline. It introduces the `UnmappedBAM` planner type, a `merge_bam_alignment`
task that merges an aligned BAM with its original unmapped BAM via GATK4
MergeBamAlignment, and a `preprocess_sample_from_ubam` workflow that composes
the full uBAM path (align → merge → dedup → BQSR) without any `sort_sam` step
because MergeBamAlignment sorts to coordinate order internally.

## What Was Built

| Item | Stage | Tests |
|---|---|---|
| `UnmappedBAM` planner type | — | 1 round-trip serialization test |
| `merge_bam_alignment` task | task stage 14 | 5 unit tests |
| `preprocess_sample_from_ubam` workflow | workflow stage 5 | 4 unit tests |

- `merge_bam_alignment` — GATK4 MergeBamAlignment with 9 flags (MostDistant
  alignment strategy, coordinate sort, CREATE_INDEX, ADD_MATE_CIGAR, etc.).
  Input uBAM must be queryname-sorted.
- `preprocess_sample_from_ubam` — `bwa_mem2_mem → merge_bam_alignment →
  mark_duplicates → base_recalibrator → apply_bqsr`. No `sort_sam` call;
  test asserts it is never invoked.
- `MANIFEST_OUTPUT_KEYS` extended with `preprocessed_bam_from_ubam`.
- `docs/tool_refs/gatk4.md` updated with full `merge_bam_alignment` section.

## Key Files

| File | Role |
|---|---|
| `src/flytetest/planner_types.py` | `UnmappedBAM` dataclass |
| `src/flytetest/tasks/variant_calling.py` | `merge_bam_alignment` task |
| `src/flytetest/workflows/variant_calling.py` | `preprocess_sample_from_ubam` + updated `MANIFEST_OUTPUT_KEYS` |
| `src/flytetest/registry/_variant_calling.py` | Registry entries (task stage 14, workflow stage 5) |
| `tests/test_variant_calling.py` | 5 new tests (MergeBamAlignment) |
| `tests/test_variant_calling_workflows.py` | 4 new tests (PreprocessSampleFromUbam) |
| `tests/test_planner_types.py` | 1 new round-trip test (UnmappedBAM) |
| `docs/tool_refs/gatk4.md` | `merge_bam_alignment` reference section |

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling_workflows.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_registry_manifest_contract.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_planner_types.py -xvs
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" \
  src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py
rg "merge_bam_alignment|preprocess_sample_from_ubam" src/flytetest/registry/_variant_calling.py
```

## Scope Boundaries

- Interval-scoped `HaplotypeCaller` — deferred to Milestone F.
- `GatherVcfs` — deferred to Milestone F.
- `CalculateGenotypePosteriors` — deferred to Milestone G.
- `VariantAnnotator` / `PostprocessVariants` — deferred to Milestone G.

## Not Implemented (by design)

- `RevertSam` / `SamToFastq` conversion steps — not part of the GATK best-practice uBAM path.
- `async def` / `await` / `asyncio.gather` patterns.
- IPFS / Pinata / TinyDB patterns.
