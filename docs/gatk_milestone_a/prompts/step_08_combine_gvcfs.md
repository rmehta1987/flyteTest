Use this prompt when starting Step 08 or when handing it off to another session.

Model: Sonnet sufficient — list-input task; emphasize per-element binding.

```text
You are continuing Milestone A of the FLyteTest Phase 3 GATK4 port under:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.3)
- Stargazer reference: /home/rmeht/Projects/stargazer/src/stargazer/tasks/gatk/combine_gvcfs.py

Context:

- This is Step 08. Depends on Steps 01–07.
- Merges multiple per-sample GVCFs into a single cohort GVCF. First task
  consuming a `list[VariantCallSet]`-shaped binding.

Key decisions already made (do not re-litigate):

- Command: `gatk CombineGVCFs -R <ref> -O <out> -V <gvcf>` (repeated per
  input). Matches Stargazer `combine_gvcfs.py:66–76`.
- Output GVCF is `<cohort_id>_combined.g.vcf`.
- Empty list → `ValueError("gvcfs list cannot be empty")`.
- Caller is responsible for ensuring each input is a GVCF; Milestone A
  does not inspect VCF headers. A later Milestone can tighten this by
  binding via a typed `VariantCallSet` whose `variant_type` is
  verified at resolver time.

Task:

1. Implement `combine_gvcfs`:

   ```python
   @variant_calling_env.task
   def combine_gvcfs(
       reference_fasta: File,
       gvcfs: list[File],
       cohort_id: str = "cohort",
       gatk_sif: str = "",
   ) -> File:
       """Combine per-sample GVCFs into a cohort GVCF via GATK4 CombineGVCFs."""
       if not gvcfs:
           raise ValueError("gvcfs list cannot be empty")

       ref_path = require_path(Path(reference_fasta.download_sync()),
                               "Reference genome FASTA")
       gvcf_paths = [
           require_path(Path(g.download_sync()), f"Input GVCF #{i}")
           for i, g in enumerate(gvcfs)
       ]

       out_dir = project_mkdtemp("gatk_combine_")
       out_gvcf = out_dir / f"{cohort_id}_combined.g.vcf"

       cmd = ["gatk", "CombineGVCFs",
              "-R", str(ref_path),
              "-O", str(out_gvcf)]
       for gp in gvcf_paths:
           cmd.extend(["-V", str(gp)])

       bind_paths = [ref_path.parent, out_dir, *[g.parent for g in gvcf_paths]]
       run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

       require_path(out_gvcf, "GATK CombineGVCFs output GVCF")
       out_idx = out_dir / f"{out_gvcf.name}.idx"

       manifest = build_manifest_envelope(
           stage="combine_gvcfs",
           assumptions=[
               "Every input is a per-sample GVCF emitted with --emit-ref-confidence GVCF.",
               "All inputs call against the same reference build as the one supplied here.",
           ],
           inputs={
               "reference_fasta": str(ref_path),
               "gvcfs": [str(g) for g in gvcf_paths],
               "cohort_id": cohort_id,
           },
           outputs={
               "combined_gvcf": str(out_gvcf),
               "combined_gvcf_index": str(out_idx) if out_idx.exists() else "",
           },
       )
       _write_json(out_dir / "run_manifest.json", manifest)
       return File(path=str(out_gvcf))
   ```

2. `RegistryEntry` to append:
   - `name="combine_gvcfs"`, `category="task"`.
   - Inputs: reference_fasta, gvcfs (`list[File]`), cohort_id, gatk_sif.
   - Outputs: combined_gvcf (`File`).
   - `accepted_planner_types=("ReferenceGenome", "VariantCallSet")` —
     resolver expands `VariantCallSet` list binding per-element.
   - `produced_planner_types=("VariantCallSet",)`.
   - `pipeline_stage_order=6`.
   - Resources: 4 CPU / 16 GiB; Slurm hints 8 CPU / 32 GiB / 06:00:00.

3. Tests:
   - `test_combine_gvcfs_rejects_empty_list`.
   - `test_combine_gvcfs_cmd_emits_V_per_input` — patch `run_tool`;
     assert `-V` appears exactly once per input GVCF, in order.
   - `test_combine_gvcfs_registry_entry_shape`.
   - `test_combine_gvcfs_emits_manifest`.

Verification:

- `python -m compileall src/flytetest/tasks/variant_calling.py`
- `pytest tests/test_variant_calling.py -xvs`

Commit message: "variant_calling: add combine_gvcfs task + registry entry".

Mark Step 08 Complete; append CHANGELOG.
```
