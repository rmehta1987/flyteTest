# GATK4 Germline Variant Calling — Milestone B

Four alignment/preprocessing tasks, three workflow compositions, a germline
fixture bundle, and a container-pull script extension.

Source-of-truth references:

- `AGENTS.md` — hard constraints, efficiency notes, core rules.
- `DESIGN.md` — biological pipeline boundaries, planner types.
- `.codex/tasks.md`, `.codex/registry.md`, `.codex/workflows.md` — patterns.
- Milestone A plan: `docs/gatk_milestone_a/milestone_a_plan.md`.
- Stargazer alignment tasks (read-only reference):
  - `stargazer/src/stargazer/tasks/general/bwa_mem2.py`
  - `stargazer/src/stargazer/tasks/gatk/sort_sam.py`
  - `stargazer/src/stargazer/tasks/gatk/mark_duplicates.py`
  - `stargazer/src/stargazer/workflows/gatk_data_preprocessing.py`
  - `stargazer/src/stargazer/workflows/germline_short_variant_discovery.py`

## §1 Context

Milestone A delivered the seven GATK4 task vocabulary (BQSR → HaplotypeCaller
→ CombineGVCFs → joint calling) and the `variant_calling` registry family.
It accepted a pre-aligned, coordinate-sorted, duplicate-marked BAM as input.

Milestone B adds the upstream preprocessing that produces that BAM from raw
reads, plus three workflow compositions that wire the full pipeline end-to-end.

- **Milestone A** (complete) — typed planner foundations + seven GATK4 tasks.
- **Milestone B** (this plan) — four preprocessing tasks, three workflows,
  germline fixture bundle, container-pull script extension.
- **Milestone C** (deferred) — cluster validation prompt set and refresh of
  `docs/mcp_full_pipeline_prompt_tests.md`.

Stargazer is async/IPFS; FLyteTest is synchronous/filesystem. Stargazer source
determines command argument ordering and output naming only; everything above
the tool invocation is re-implemented against FLyteTest patterns. No
`async def`, `await`, `asyncio.gather`, `.cid`, IPFS, Pinata, or TinyDB.

## §2 Pillars / Invariants (carried from Milestone A)

1. **Freeze before execute.** Tasks emit `run_manifest.json` via
   `build_manifest_envelope`; registry-manifest contract test enforces
   alignment.
2. **Typed surfaces everywhere.** New planner types inherit
   `PlannerSerializable`; registry interface fields stay typed.
3. **Manifest envelope per task.** Every task and workflow emits
   `run_manifest.json`.
4. **No Stargazer-pattern bleed-in.** Grep gate in §8 must pass.

## §3 Data Model

### New planner type: `ReadPair`

```python
@dataclass(frozen=True)
class ReadPair(PlannerSerializable):
    """Paired-end FASTQ inputs for one sample."""
    sample_id: str
    r1_path: str          # absolute path to R1 FASTQ (may be .gz)
    r2_path: str | None = None   # None for single-end
```

`AlignmentSet` (Milestone A) already covers pre-aligned BAMs.
`ReadPair` covers raw reads that need alignment.

### New `MANIFEST_OUTPUT_KEYS` additions

```
"bwa_index_prefix"    # bwa_mem2_index
"aligned_bam"         # bwa_mem2_mem
"sorted_bam"          # sort_sam
"dedup_bam"           # mark_duplicates
"duplicate_metrics"   # mark_duplicates
```

Added incrementally per step; full tuple after Step 05:

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    # Milestone A keys
    "sequence_dict", "feature_index", "bqsr_report",
    "recalibrated_bam", "gvcf", "combined_gvcf", "joint_vcf",
    # Milestone B keys
    "bwa_index_prefix", "aligned_bam", "sorted_bam",
    "dedup_bam", "duplicate_metrics",
)
```

Workflow manifest keys are defined in the workflow module (separate
`MANIFEST_OUTPUT_KEYS` in `src/flytetest/workflows/variant_calling.py`):

```python
MANIFEST_OUTPUT_KEYS: tuple[str, ...] = (
    "prepared_ref",          # prepare_reference
    "preprocessed_bam",      # preprocess_sample
    "genotyped_vcf",         # germline_short_variant_discovery
)
```

### Registry stage orders

Tasks continue the Milestone A sequence:

| stage_order | task |
|---|---|
| 1–7 | Milestone A tasks (unchanged) |
| 8 | `bwa_mem2_index` |
| 9 | `bwa_mem2_mem` |
| 10 | `sort_sam` |
| 11 | `mark_duplicates` |

Workflows use `pipeline_stage_order` 1–3 within category `"workflow"`.

## §4 Implementation Notes

### BWA-MEM2 pipeline command

`bwa_mem2_mem` must pipe through `samtools view -bS` to produce a BAM.
Use a shell pipeline via `subprocess.run(shell=True, ...)` — do NOT use
`run_tool` directly since it does not support pipes. Pattern:

```python
import subprocess
pipeline = (
    f"bwa-mem2 mem -R '{rg}' -t {threads} {ref} {r1} {r2} "
    f"| samtools view -bS -o {output_bam} -"
)
result = subprocess.run(pipeline, shell=True, capture_output=True, text=True)
if result.returncode != 0:
    raise RuntimeError(f"bwa_mem2_mem failed:\n{result.stderr}")
```

Container invocation: when `sif_path` is set, wrap the pipeline inside
`apptainer exec {sif_path} bash -c '{pipeline}'` using `run_tool` with
`cmd=["bash", "-c", pipeline]`.

### SortSam

```
gatk SortSam -I <in.bam> -O <out.bam> --SORT_ORDER coordinate --CREATE_INDEX true
```

`--CREATE_INDEX true` writes `<out.bam>.bai` alongside; the task must check
for both `.bai` and `.bam.bai` naming (consistent with `apply_bqsr`).

### MarkDuplicates

```
gatk MarkDuplicates -I <in.bam> -O <out.bam> -M <metrics.txt> --CREATE_INDEX true
```

Both `<out.bam>` and `<metrics.txt>` go in `results_dir`; both appear in
manifest and registry outputs.

### Workflow compositions

Workflows live in `src/flytetest/workflows/variant_calling.py` as
`@variant_calling_env.task` decorated functions (consistent with the
existing `transcript_evidence_generation` pattern). They compose Milestone A
+ B tasks in biological order using normal sequential Python calls.

Per-sample loops in `germline_short_variant_discovery` are synchronous Python
`for` loops — no `asyncio.gather`.

#### `prepare_reference`

```
create_sequence_dictionary(ref_path, results_dir)
for vcf in known_sites:
    index_feature_file(vcf, results_dir)
bwa_mem2_index(ref_path, results_dir)
→ emit manifest: prepared_ref = ref_path
```

#### `preprocess_sample`

```
aligned   = bwa_mem2_mem(ref_path, r1, r2, sample_id, results_dir)
sorted    = sort_sam(aligned, sample_id, results_dir)
deduped   = mark_duplicates(sorted, sample_id, results_dir)
bqsr_tbl  = base_recalibrator(ref_path, deduped, known_sites, sample_id, results_dir)
recal_bam = apply_bqsr(ref_path, deduped, bqsr_tbl, sample_id, results_dir)
→ emit manifest: preprocessed_bam = recal_bam
```

#### `germline_short_variant_discovery`

```
for sample_id, r1, r2 in zip(sample_ids, r1_paths, r2_paths):
    recal_bam = preprocess_sample(...)
    gvcf      = haplotype_caller(ref_path, recal_bam, sample_id, results_dir)
combined = combine_gvcfs(ref_path, gvcfs, cohort_id, results_dir)
joint_vcf = joint_call_gvcfs(ref_path, sample_ids, gvcfs, intervals, cohort_id, results_dir)
→ emit manifest: genotyped_vcf = joint_vcf
```

### Fixture bundle

Add a `ResourceBundle` named `"variant_calling_germline_minimal"` to
`src/flytetest/bundles.py`. This is a documentation bundle only (no actual
fixture data in the repo) describing the expected paths for:

- Reference FASTA (e.g., `data/references/hg38/chr20.fa`)
- Known-sites VCFs (dbSNP, Mills)
- Test sample R1/R2 FASTQs (e.g., NA12878 chr20 slice)
- Results directory prefix

### Container-pull script

Add `scripts/rcc/pull_gatk_image.sh` — a short script that pulls the GATK4
SIF image to `data/images/gatk4.sif` using `apptainer pull`.

## §5 Backward Compatibility

Milestone B is purely additive:

- New `ReadPair` planner type (new dataclass; no existing type changed).
- Four new tasks appended to `variant_calling.py`.
- New workflow file `src/flytetest/workflows/variant_calling.py` (no existing
  workflow changed).
- New registry entries appended to `VARIANT_CALLING_ENTRIES`.
- `MANIFEST_OUTPUT_KEYS` in task module extended (new keys only; existing keys
  unchanged).
- `bundles.py` gains one new entry (additive).
- `scripts/rcc/pull_gatk_image.sh` is new (no existing script changed).

## §6 Steps

### Foundation

| # | Step | Prompt |
|---|------|--------|
| 01 | Add `ReadPair` planner type | `prompts/step_01_read_pair_type.md` |

### Preprocessing Tasks

| # | Step | Prompt |
|---|------|--------|
| 02 | `bwa_mem2_index` — index reference for BWA-MEM2 | `prompts/step_02_bwa_mem2_index.md` |
| 03 | `bwa_mem2_mem` — align paired reads → unsorted BAM | `prompts/step_03_bwa_mem2_mem.md` |
| 04 | `sort_sam` — coordinate-sort BAM | `prompts/step_04_sort_sam.md` |
| 05 | `mark_duplicates` — mark PCR/optical duplicates | `prompts/step_05_mark_duplicates.md` |

### Workflow Compositions

| # | Step | Prompt |
|---|------|--------|
| 06 | `prepare_reference` workflow | `prompts/step_06_prepare_reference.md` |
| 07 | `preprocess_sample` workflow | `prompts/step_07_preprocess_sample.md` |
| 08 | `germline_short_variant_discovery` workflow | `prompts/step_08_germline_short_variant_discovery.md` |

### Closure

| # | Step | Prompt |
|---|------|--------|
| 09 | Fixture bundle + container script + agent-context sweep | `prompts/step_09_closure.md` |

## §7 Out of Scope (this milestone)

- `merge_bam_alignment` (uBAM workflow path) — deferred; direct FASTQ path
  is sufficient for Milestone B.
- VQSR (`variant_recalibrator`, `apply_vqsr`) — still deferred.
- Actual fixture data in the repo — bundle is documentation-only; real data
  lives on the cluster.
- `docs/mcp_full_pipeline_prompt_tests.md` refresh — Milestone C.
- Interval-scoped HaplotypeCaller — still out of scope.

## §8 Verification Gates

All must pass before marking Milestone B complete:

- `python -m compileall src/flytetest/` clean.
- `pytest tests/test_variant_calling.py -xvs` green.
- `pytest tests/test_variant_calling_workflows.py -xvs` green.
- `pytest tests/test_registry_manifest_contract.py -xvs` green.
- `pytest tests/test_planner_types.py -xvs` green (ReadPair round-trips).
- Full `pytest` suite green.
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits.
- `rg "bwa_mem2_index|sort_sam|mark_duplicates|prepare_reference|preprocess_sample|germline_short_variant_discovery" src/flytetest/registry/_variant_calling.py` → matches.

## §9 Hard Constraints

- No frozen-artifact mutation at retry/replay time.
- No Slurm submit without a frozen run record.
- No change to `classify_slurm_failure()` semantics.
- No async/IPFS/TinyDB patterns in ported code.
- `merge_bam_alignment` is out of scope; do not implement it unless the step
  prompt explicitly opens that scope.
