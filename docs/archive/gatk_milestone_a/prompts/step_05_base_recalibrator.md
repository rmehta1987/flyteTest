Use this prompt when starting Step 05 or when handing it off to another session.

Model: Sonnet sufficient — patterns are established by steps 03–04; this is
the first task consuming multiple planner types.

```text
You are continuing Milestone A of the FLyteTest Phase 3 GATK4 port under:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.3)
- Stargazer reference: /home/rmeht/Projects/stargazer/src/stargazer/tasks/gatk/base_recalibrator.py

Context:

- This is Step 05. Depends on Steps 01–04 (planner types, env, registry
  skeleton, `index_feature_file` available for known-sites indexing).
- First task consuming an `AlignmentSet` + `ReferenceGenome` + list of
  `KnownSites`; the registry entry demonstrates the
  `accepted_planner_types` shape for multi-type bindings.

Key decisions already made (do not re-litigate):

- Input BAM must be coordinate-sorted and dedup'd — Milestone A does not
  perform alignment or MarkDuplicates. Task asserts the BAM path exists
  but does not verify sort order or duplicate flag (trust the binding).
- At least one `KnownSites` entry is required; empty list → raise
  `ValueError("known_sites list cannot be empty for BQSR")`, matching
  Stargazer `base_recalibrator.py:42`.
- Command: `gatk BaseRecalibrator -R <ref> -I <bam> -O <recal.table>
  --known-sites <site>` (repeated per site). Matches Stargazer
  `base_recalibrator.py:55–67`.
- Output: `File` pointing at the BQSR recalibration table. The task does
  not produce a new `AlignmentSet` — that is Step 06 (ApplyBQSR).
- Known-sites VCFs are expected to be already indexed (caller ran Step
  04 first). This task does not silently reindex.

Task:

1. Implement `base_recalibrator`:

   ```python
   @variant_calling_env.task
   def base_recalibrator(
       reference_fasta: File,
       aligned_bam: File,
       known_sites: list[File],
       sample_id: str,
       gatk_sif: str = "",
   ) -> File:
       """Generate a BQSR recalibration table via GATK4 BaseRecalibrator."""
       if not known_sites:
           raise ValueError("known_sites list cannot be empty for BQSR")

       ref_path = require_path(Path(reference_fasta.download_sync()),
                               "Reference genome FASTA")
       bam_path = require_path(Path(aligned_bam.download_sync()),
                               "Aligned BAM")
       site_paths = [
           require_path(Path(s.download_sync()), f"KnownSites VCF #{i}")
           for i, s in enumerate(known_sites)
       ]

       out_dir = project_mkdtemp("gatk_bqsr_report_")
       recal_path = out_dir / f"{sample_id}_bqsr.table"

       cmd = ["gatk", "BaseRecalibrator",
              "-R", str(ref_path),
              "-I", str(bam_path),
              "-O", str(recal_path)]
       for site in site_paths:
           cmd.extend(["--known-sites", str(site)])

       bind_paths = [ref_path.parent, bam_path.parent, out_dir,
                     *[s.parent for s in site_paths]]
       run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

       require_path(recal_path, "GATK BaseRecalibrator output table")

       manifest = build_manifest_envelope(
           stage="base_recalibrator",
           assumptions=[
               "Aligned BAM is coordinate-sorted and has duplicates marked (caller responsibility).",
               "All known-sites VCFs are indexed (.idx or .tbi present next to each VCF).",
               "Reference has a .fai and .dict next to the FASTA.",
           ],
           inputs={
               "reference_fasta": str(ref_path),
               "aligned_bam": str(bam_path),
               "known_sites": [str(s) for s in site_paths],
               "sample_id": sample_id,
           },
           outputs={"bqsr_report": str(recal_path)},
       )
       _write_json(out_dir / "run_manifest.json", manifest)
       return File(path=str(recal_path))
   ```

2. `RegistryEntry` to append:
   - `name="base_recalibrator"`, `category="task"`.
   - Inputs: reference_fasta, aligned_bam, known_sites (`list[File]`),
     sample_id, gatk_sif.
   - Outputs: bqsr_report (`File`).
   - `accepted_planner_types=("ReferenceGenome", "AlignmentSet", "KnownSites")`.
   - `produced_planner_types=()`.
   - `pipeline_stage_order=3`.
   - Resources: 4 CPU / 16 GiB; Slurm hints 8 CPU / 32 GiB / 06:00:00.
   - `composition_constraints=("Requires coordinate-sorted dedup'd BAM + reference + ≥1 indexed known-sites VCF.",)`.

3. Tests in `tests/test_variant_calling.py`:
   - `test_base_recalibrator_rejects_empty_known_sites` — empty list →
     `ValueError`.
   - `test_base_recalibrator_cmd_shape` — patch `run_tool`; assert
     cmd contains the fixed prefix and `--known-sites` is emitted once
     per input entry in order.
   - `test_base_recalibrator_registry_entry_shape`.
   - `test_base_recalibrator_emits_manifest` — stage and outputs keys.

Verification:

- `python -m compileall src/flytetest/tasks/variant_calling.py`
- `pytest tests/test_variant_calling.py -xvs`

Commit message: "variant_calling: add base_recalibrator task + registry entry".

Mark Step 05 Complete; append CHANGELOG.
```
