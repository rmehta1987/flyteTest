Use this prompt when starting Step 07 or when handing it off to another session.

Model: Sonnet sufficient — one-input-to-one-output variant caller.

```text
You are continuing Milestone A of the FLyteTest Phase 3 GATK4 port under:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.3)
- Stargazer reference: /home/rmeht/Projects/stargazer/src/stargazer/tasks/gatk/haplotype_caller.py

Context:

- This is Step 07. Depends on Steps 01–06.
- Calls germline variants per-sample in GVCF mode. Output is a GVCF
  `VariantCallSet`.

Key decisions already made (do not re-litigate):

- Command: `gatk HaplotypeCaller -R <ref> -I <bam> -O <out.g.vcf>
  --emit-ref-confidence GVCF`. Matches Stargazer
  `haplotype_caller.py:46–57`.
- GVCF is `<sample_id>.g.vcf`; companion index is
  `<sample_id>.g.vcf.idx` (GATK writes it implicitly).
- Milestone A does not emit intervals-scoped calls; whole-genome pass
  only. Intervals are a Milestone B/C enhancement.

Task:

1. Implement `haplotype_caller`:

   ```python
   @variant_calling_env.task
   def haplotype_caller(
       reference_fasta: File,
       aligned_bam: File,
       sample_id: str,
       gatk_sif: str = "",
   ) -> File:
       """Call per-sample germline GVCF via GATK4 HaplotypeCaller in GVCF mode."""
       ref_path = require_path(Path(reference_fasta.download_sync()),
                               "Reference genome FASTA")
       bam_path = require_path(Path(aligned_bam.download_sync()),
                               "Aligned BAM for HaplotypeCaller")

       out_dir = project_mkdtemp("gatk_hc_")
       out_gvcf = out_dir / f"{sample_id}.g.vcf"

       cmd = ["gatk", "HaplotypeCaller",
              "-R", str(ref_path),
              "-I", str(bam_path),
              "-O", str(out_gvcf),
              "--emit-ref-confidence", "GVCF"]
       bind_paths = [ref_path.parent, bam_path.parent, out_dir]
       run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

       require_path(out_gvcf, "GATK HaplotypeCaller output GVCF")
       out_idx = out_dir / f"{out_gvcf.name}.idx"

       manifest = build_manifest_envelope(
           stage="haplotype_caller",
           assumptions=[
               "Aligned BAM is coordinate-sorted, dedup'd, and (recommended) BQSR-recalibrated.",
               "Reference has a .fai and .dict next to the FASTA.",
               "Whole-genome pass; intervals-scoped calling is out of scope for Milestone A.",
           ],
           inputs={
               "reference_fasta": str(ref_path),
               "aligned_bam": str(bam_path),
               "sample_id": sample_id,
           },
           outputs={
               "gvcf": str(out_gvcf),
               "gvcf_index": str(out_idx) if out_idx.exists() else "",
           },
       )
       _write_json(out_dir / "run_manifest.json", manifest)
       return File(path=str(out_gvcf))
   ```

2. `RegistryEntry` to append:
   - `name="haplotype_caller"`, `category="task"`.
   - Inputs: reference_fasta, aligned_bam, sample_id, gatk_sif.
   - Outputs: gvcf (`File`).
   - `accepted_planner_types=("ReferenceGenome", "AlignmentSet")`.
   - `produced_planner_types=("VariantCallSet",)` — discriminated by
     `variant_type="gvcf"` when bound downstream.
   - `pipeline_stage_order=5`.
   - Resources: 8 CPU / 32 GiB; Slurm hints 16 CPU / 64 GiB / 24:00:00.

3. Tests:
   - `test_haplotype_caller_cmd_shape` — `--emit-ref-confidence GVCF`
     present; `-O` points at `<sample>.g.vcf`.
   - `test_haplotype_caller_registry_entry_shape`.
   - `test_haplotype_caller_emits_manifest` — stage,
     `outputs["gvcf"]` matches.

Verification:

- `python -m compileall src/flytetest/tasks/variant_calling.py`
- `pytest tests/test_variant_calling.py -xvs`

Commit message: "variant_calling: add haplotype_caller task + registry entry".

Mark Step 07 Complete; append CHANGELOG.
```
