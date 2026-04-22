Use this prompt when starting Step 06 or when handing it off to another session.

Model: Sonnet sufficient — mirrors Step 05 shape; consumes the BQSR report.

```text
You are continuing Milestone A of the FLyteTest Phase 3 GATK4 port under:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.3)
- Stargazer reference: /home/rmeht/Projects/stargazer/src/stargazer/tasks/gatk/apply_bqsr.py

Context:

- This is Step 06. Depends on Steps 01–05.
- Applies a BQSR recalibration table to an aligned BAM and emits a
  recalibrated BAM. First task whose output binds as a new
  `AlignmentSet`.

Key decisions already made (do not re-litigate):

- Command: `gatk ApplyBQSR -R <ref> -I <bam> --bqsr-recal-file <table>
  -O <out.bam>`. Matches Stargazer `apply_bqsr.py:54–65`.
- Output BAM is named `<sample_id>_recalibrated.bam` inside the task's
  scratch dir. Companion `.bai` is written by GATK; we surface it
  explicitly via manifest + return value.
- Duplicate flag of the input is assumed already set by the caller; we
  do not re-run MarkDuplicates here.

Task:

1. Implement `apply_bqsr`:

   ```python
   @variant_calling_env.task
   def apply_bqsr(
       reference_fasta: File,
       aligned_bam: File,
       bqsr_report: File,
       sample_id: str,
       gatk_sif: str = "",
   ) -> File:
       """Apply a BQSR recalibration table to an aligned BAM via GATK4 ApplyBQSR."""
       ref_path = require_path(Path(reference_fasta.download_sync()),
                               "Reference genome FASTA")
       bam_path = require_path(Path(aligned_bam.download_sync()),
                               "Aligned BAM for ApplyBQSR")
       recal_path = require_path(Path(bqsr_report.download_sync()),
                                 "BQSR recalibration table")

       out_dir = project_mkdtemp("gatk_apply_bqsr_")
       out_bam = out_dir / f"{sample_id}_recalibrated.bam"

       cmd = ["gatk", "ApplyBQSR",
              "-R", str(ref_path),
              "-I", str(bam_path),
              "--bqsr-recal-file", str(recal_path),
              "-O", str(out_bam)]
       bind_paths = [ref_path.parent, bam_path.parent, recal_path.parent, out_dir]
       run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

       require_path(out_bam, "GATK ApplyBQSR output BAM")
       out_bai = out_bam.with_suffix(".bai")  # GATK writes this; may also be .bam.bai
       if not out_bai.exists():
           alt_bai = Path(str(out_bam) + ".bai")
           if alt_bai.exists():
               out_bai = alt_bai

       manifest = build_manifest_envelope(
           stage="apply_bqsr",
           assumptions=[
               "Input BAM is coordinate-sorted and dedup'd (caller responsibility).",
               "BQSR table was generated from this BAM + the same reference + known sites.",
           ],
           inputs={
               "reference_fasta": str(ref_path),
               "aligned_bam": str(bam_path),
               "bqsr_report": str(recal_path),
               "sample_id": sample_id,
           },
           outputs={
               "recalibrated_bam": str(out_bam),
               "recalibrated_bam_index": str(out_bai) if out_bai.exists() else "",
           },
       )
       _write_json(out_dir / "run_manifest.json", manifest)
       return File(path=str(out_bam))
   ```

2. `RegistryEntry` to append:
   - `name="apply_bqsr"`, `category="task"`.
   - Inputs: reference_fasta, aligned_bam, bqsr_report, sample_id, gatk_sif.
   - Outputs: recalibrated_bam (`File`).
   - `accepted_planner_types=("ReferenceGenome", "AlignmentSet")` — BQSR
     report binds via explicit prior-run `from_run` reference, not as a
     separate planner type in Milestone A.
   - `produced_planner_types=("AlignmentSet",)`.
   - `pipeline_stage_order=4`.
   - Resources: 4 CPU / 16 GiB; Slurm hints 8 CPU / 32 GiB / 06:00:00.

3. Tests in `tests/test_variant_calling.py`:
   - `test_apply_bqsr_cmd_shape` — patch `run_tool`; assert cmd has
     `--bqsr-recal-file` before `-O` and output BAM path is derived
     from `sample_id`.
   - `test_apply_bqsr_registry_entry_shape`.
   - `test_apply_bqsr_emits_manifest` — outputs include
     `recalibrated_bam`; index key is present (possibly empty).

Verification:

- `python -m compileall src/flytetest/tasks/variant_calling.py`
- `pytest tests/test_variant_calling.py -xvs`

Commit message: "variant_calling: add apply_bqsr task + registry entry".

Mark Step 06 Complete; append CHANGELOG.
```
