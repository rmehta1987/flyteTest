Use this prompt when starting Step 04 or when handing it off to another session.

Model: Sonnet sufficient — small helper task, same pattern as Step 03.

```text
You are continuing Milestone A of the FLyteTest Phase 3 GATK4 port under:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.3)
- Stargazer reference: /home/rmeht/Projects/stargazer/src/stargazer/tasks/gatk/index_feature_file.py

Context:

- This is Step 04. Depends on Steps 01–03.
- Produces an index (`.idx` or `.tbi`) alongside a VCF/GVCF. Used by
  BQSR (known-sites) and by downstream steps that accept GVCF indices.

Key decisions already made (do not re-litigate):

- Input: `KnownSites` planner-type-shaped binding OR any `File` that is
  a VCF/GVCF. For Milestone A, scope to the BQSR-facing use case:
  input is a `File` pointing at a `.vcf` / `.vcf.gz` and the task
  returns the resulting index file next to it.
- Command: `gatk IndexFeatureFile -I <vcf>`. GATK writes the index
  alongside `<vcf>` with a suffixed name. We do NOT pass `-O` — the
  index path is derived by appending `.idx` (for `.vcf`) or `.tbi`
  (for `.vcf.gz`).
- No companion-fetch behavior; caller provides a reachable path.

Task:

1. Append `"index_feature_file"` variants to `MANIFEST_OUTPUT_KEYS` if
   you are tracking per-module keys; otherwise document in the registry
   entry. (Check Step 03's final shape and follow the pattern.)

2. Implement `index_feature_file`:

   ```python
   @variant_calling_env.task
   def index_feature_file(
       vcf: File,
       gatk_sif: str = "",
   ) -> File:
       """Emit a GATK4 feature-file index (.idx or .tbi) next to a VCF/GVCF."""
       vcf_path = require_path(Path(vcf.download_sync()),
                               "VCF/GVCF input for IndexFeatureFile")
       out_dir = project_mkdtemp("gatk_index_")

       if vcf_path.suffix == ".gz":
           expected_index = vcf_path.with_suffix(vcf_path.suffix + ".tbi")
       else:
           expected_index = vcf_path.with_suffix(vcf_path.suffix + ".idx")

       cmd = ["gatk", "IndexFeatureFile", "-I", str(vcf_path)]
       bind_paths = [vcf_path.parent, out_dir]
       run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

       require_path(expected_index, "GATK IndexFeatureFile output index")

       manifest = build_manifest_envelope(
           stage="index_feature_file",
           assumptions=[
               "VCF is readable; GATK writes the index next to the VCF.",
           ],
           inputs={"vcf": str(vcf_path)},
           outputs={"feature_index": str(expected_index)},
       )
       _write_json(out_dir / "run_manifest.json", manifest)
       return File(path=str(expected_index))
   ```

3. Add the `RegistryEntry` to `VARIANT_CALLING_ENTRIES`:
   - `name="index_feature_file"`, `category="task"`.
   - Inputs: `vcf: File`, `gatk_sif: str`.
   - Outputs: `feature_index: File`.
   - `biological_stage="GATK4 feature-file indexing"`,
     `accepted_planner_types=("KnownSites",)` (downstream step 05 can
     bind a `KnownSites` planner type to this task's `vcf` input),
     `produced_planner_types=()`, `pipeline_stage_order=2`.
   - Resources: 1 CPU / 4 GiB.

4. Tests in `tests/test_variant_calling.py`:
   - `test_index_feature_file_registry_entry_shape`.
   - `test_index_feature_file_uses_tbi_for_gz` — input
     `sites.vcf.gz` → expected output path ends in `.vcf.gz.tbi`.
   - `test_index_feature_file_uses_idx_for_plain_vcf` — input
     `sites.vcf` → expected output path ends in `.vcf.idx`.
   - Manifest assertion: `outputs["feature_index"]` matches.

Verification:

- `python -m compileall src/flytetest/tasks/variant_calling.py src/flytetest/registry/_variant_calling.py`
- `pytest tests/test_variant_calling.py -xvs`

Commit message: "variant_calling: add index_feature_file task + registry entry".

Then mark Step 04 Complete in docs/gatk_milestone_a/checklist.md and
append a CHANGELOG.md entry.
```
