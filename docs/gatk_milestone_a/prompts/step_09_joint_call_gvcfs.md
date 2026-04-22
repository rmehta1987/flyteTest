Use this prompt when starting Step 09 or when handing it off to another session.

Model: Opus recommended — two-step GATK invocation (GenomicsDBImport +
GenotypeGVCFs) with an ephemeral workspace; more moving parts than prior tasks.

```text
You are continuing Milestone A of the FLyteTest Phase 3 GATK4 port under:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.3)
- Stargazer reference: /home/rmeht/Projects/stargazer/src/stargazer/tasks/gatk/joint_call_gvcfs.py

Context:

- This is Step 09. Depends on Steps 01–08. The final task step.
- Runs GenomicsDBImport followed by GenotypeGVCFs in a single task so
  the GenomicsDB workspace never leaves the task's scratch space.
- Produces the joint-called VCF `VariantCallSet` that closes out the
  germline discovery surface for Milestone A.

Key decisions already made (do not re-litigate):

- Workspace is created under a `tempfile.TemporaryDirectory()` inside
  the task (matches Stargazer `joint_call_gvcfs.py:63–89`).
- `--sample-name-map` file is written per-invocation and discarded with
  the tempdir.
- Output VCF is `<cohort_id>_genotyped.vcf`, index `<out>.idx`.
- `intervals` is required (GenomicsDBImport requires at least one `-L`).
  Empty list → `ValueError("intervals list cannot be empty for GenomicsDBImport")`.
- Milestone A does not auto-derive intervals from the reference; caller
  supplies (e.g., `["chr20"]` for the NA12878 chr20 slice planned for
  Milestone B fixtures).

Task:

1. Add `import tempfile` to the task module (if not already present).

2. Implement `joint_call_gvcfs`:

   ```python
   @variant_calling_env.task
   def joint_call_gvcfs(
       reference_fasta: File,
       gvcfs: list[File],
       sample_ids: list[str],
       intervals: list[str],
       cohort_id: str = "cohort",
       gatk_sif: str = "",
   ) -> File:
       """GenomicsDBImport + GenotypeGVCFs → joint-called VCF for a cohort."""
       if not gvcfs:
           raise ValueError("gvcfs list cannot be empty")
       if not intervals:
           raise ValueError("intervals list cannot be empty for GenomicsDBImport")
       if len(sample_ids) != len(gvcfs):
           raise ValueError(
               f"sample_ids length ({len(sample_ids)}) must match gvcfs "
               f"length ({len(gvcfs)}); sample_name_map requires a 1:1 mapping."
           )

       ref_path = require_path(Path(reference_fasta.download_sync()),
                               "Reference genome FASTA")
       gvcf_paths = [
           require_path(Path(g.download_sync()), f"Input GVCF #{i}")
           for i, g in enumerate(gvcfs)
       ]

       out_dir = project_mkdtemp("gatk_joint_")
       out_vcf = out_dir / f"{cohort_id}_genotyped.vcf"

       with tempfile.TemporaryDirectory(
           prefix="gatk_genomicsdb_", dir=str(out_dir)
       ) as tmpdir:
           tmp = Path(tmpdir)
           workspace = tmp / f"{cohort_id}_genomicsdb"
           sample_map = tmp / "sample_map.txt"
           sample_map.write_text(
               "\n".join(
                   f"{sid}\t{gp}" for sid, gp in zip(sample_ids, gvcf_paths)
               ) + "\n"
           )

           import_cmd = ["gatk", "GenomicsDBImport",
                         "--genomicsdb-workspace-path", str(workspace),
                         "--sample-name-map", str(sample_map)]
           for interval in intervals:
               import_cmd.extend(["-L", interval])

           bind_paths = [ref_path.parent, out_dir, tmp,
                         *[g.parent for g in gvcf_paths]]
           run_tool(import_cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)
           require_path(workspace, "GenomicsDBImport workspace")

           genotype_cmd = ["gatk", "GenotypeGVCFs",
                           "-R", str(ref_path),
                           "-V", f"gendb://{workspace}",
                           "-O", str(out_vcf)]
           run_tool(genotype_cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

       require_path(out_vcf, "GATK GenotypeGVCFs output VCF")
       out_idx = out_dir / f"{out_vcf.name}.idx"

       manifest = build_manifest_envelope(
           stage="joint_call_gvcfs",
           assumptions=[
               "All inputs are per-sample GVCFs from HaplotypeCaller against the same reference.",
               "Intervals cover the genomic region of interest; GenomicsDBImport requires ≥1 interval.",
               "GenomicsDB workspace is ephemeral (tempdir); the workspace does not leave this task.",
           ],
           inputs={
               "reference_fasta": str(ref_path),
               "gvcfs": [str(g) for g in gvcf_paths],
               "sample_ids": list(sample_ids),
               "intervals": list(intervals),
               "cohort_id": cohort_id,
           },
           outputs={
               "joint_vcf": str(out_vcf),
               "joint_vcf_index": str(out_idx) if out_idx.exists() else "",
           },
       )
       _write_json(out_dir / "run_manifest.json", manifest)
       return File(path=str(out_vcf))
   ```

3. `RegistryEntry` to append:
   - `name="joint_call_gvcfs"`, `category="task"`.
   - Inputs: reference_fasta, gvcfs, sample_ids, intervals, cohort_id,
     gatk_sif.
   - Outputs: joint_vcf (`File`).
   - `accepted_planner_types=("ReferenceGenome", "VariantCallSet")`.
   - `produced_planner_types=("VariantCallSet",)` (variant_type="vcf"
     downstream).
   - `pipeline_stage_order=7`.
   - Resources: 8 CPU / 32 GiB; Slurm hints 16 CPU / 64 GiB / 24:00:00.
   - `composition_constraints=("Requires a list of GVCFs with matching sample_ids 1:1.", "Requires at least one genomic interval.")`.

4. Tests:
   - `test_joint_call_gvcfs_rejects_empty_gvcfs`.
   - `test_joint_call_gvcfs_rejects_empty_intervals`.
   - `test_joint_call_gvcfs_rejects_mismatched_sample_ids_length`.
   - `test_joint_call_gvcfs_cmd_sequence` — patch `run_tool`; assert
     two invocations in order (`GenomicsDBImport` first,
     `GenotypeGVCFs` second) and that the second uses `gendb://`.
   - `test_joint_call_gvcfs_sample_map_format` — patch `run_tool`;
     inspect the `sample_map.txt` written during the call and assert
     one line per sample with `<sid>\t<path>`.
   - `test_joint_call_gvcfs_registry_entry_shape`.
   - `test_joint_call_gvcfs_emits_manifest`.

Verification:

- `python -m compileall src/flytetest/tasks/variant_calling.py`
- `pytest tests/test_variant_calling.py -xvs`

Commit message: "variant_calling: add joint_call_gvcfs task + registry entry".

Mark Step 09 Complete; append CHANGELOG.
```
