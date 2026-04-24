Use this prompt when starting Step 03 or when handing it off to another session.

Model: Sonnet sufficient — straightforward port, establishes the task pattern.

```text
You are continuing Milestone A of the FLyteTest Phase 3 GATK4 port under:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.3)
- Stargazer reference (read-only):
  /home/rmeht/Projects/stargazer/src/stargazer/tasks/gatk/create_sequence_dictionary.py

Context:

- This is Step 03 (Tasks). Depends on Steps 01, 02.
- Establishes the port pattern every subsequent task step follows:
  task function + matching registry entry + unit test + CHANGELOG line.

Key decisions already made (do not re-litigate):

- Input: `ReferenceGenome` (reuse existing planner type).
- Output: `Path` to the `.dict` file emitted next to the reference FASTA,
  wrapped in a `flyte.io.File`.
- GATK command is `gatk CreateSequenceDictionary -R <ref.fa> -O <ref.dict>`
  — same flags as Stargazer.
- Apptainer invocation via `run_tool(cmd, gatk_sif, bind_paths)` from
  `flytetest.config`, matching the pattern in
  `src/flytetest/tasks/annotation.py` (see the BRAKER3 task body for the
  `bind_paths` convention).
- Manifest emission via `build_manifest_envelope` (stage name:
  `"create_sequence_dictionary"`) + `_write_json` write of
  `run_manifest.json` into the output dir.
- Delete the Step 02 scaffolding test.

Task:

1. Add module header + imports to new file
   `src/flytetest/tasks/variant_calling.py`:

   ```python
   """GATK4 variant calling task implementations for Milestone A."""

   from __future__ import annotations

   from pathlib import Path

   from flyte.io import File

   from flytetest.config import (
       variant_calling_env,
       project_mkdtemp,
       require_path,
       run_tool,
   )
   from flytetest.manifest_envelope import build_manifest_envelope
   from flytetest.manifest_io import write_json as _write_json
   ```

2. Declare `MANIFEST_OUTPUT_KEYS: tuple[str, ...] = ("sequence_dict",)`
   at module level; this tuple grows as each task lands.

3. Implement `create_sequence_dictionary`:

   ```python
   @variant_calling_env.task
   def create_sequence_dictionary(
       reference_fasta: File,
       gatk_sif: str = "",
   ) -> File:
       """Emit a GATK sequence dictionary (.dict) next to the reference FASTA."""
       ref_path = require_path(Path(reference_fasta.download_sync()),
                               "Reference genome FASTA")
       out_dir = project_mkdtemp("gatk_seqdict_")
       dict_path = out_dir / f"{ref_path.stem}.dict"

       cmd = ["gatk", "CreateSequenceDictionary",
              "-R", str(ref_path), "-O", str(dict_path)]
       bind_paths = [ref_path.parent, out_dir]
       run_tool(cmd, gatk_sif or "data/images/gatk4.sif", bind_paths)

       require_path(dict_path, "GATK CreateSequenceDictionary output")

       manifest = build_manifest_envelope(
           stage="create_sequence_dictionary",
           assumptions=[
               "Reference FASTA is readable and has no pre-existing "
               ".dict that would conflict; GATK overwrites -O when run.",
           ],
           inputs={"reference_fasta": str(ref_path)},
           outputs={"sequence_dict": str(dict_path)},
       )
       _write_json(out_dir / "run_manifest.json", manifest)
       return File(path=str(dict_path))
   ```

   Notes:
   - Matches Stargazer arg order (`-R`, `-O`) per
     `stargazer/tasks/gatk/create_sequence_dictionary.py:35–42`.
   - No `.fai` or `.dict` companion fetching — FLyteTest gets paths
     directly; caller is responsible for readable paths.

4. Add a `RegistryEntry` to `VARIANT_CALLING_ENTRIES` in
   `src/flytetest/registry/_variant_calling.py`:

   ```python
   RegistryEntry(
       name="create_sequence_dictionary",
       category="task",
       description="Emit a GATK4 sequence dictionary (.dict) next to a reference FASTA via CreateSequenceDictionary.",
       inputs=(
           InterfaceField("reference_fasta", "File", "Reference genome FASTA."),
           InterfaceField("gatk_sif", "str", "Optional Apptainer/Singularity image path for GATK4."),
       ),
       outputs=(
           InterfaceField("sequence_dict", "File", "GATK4 sequence dictionary (.dict) file emitted next to the reference FASTA."),
       ),
       tags=("variant_calling", "gatk4", "reference_prep"),
       compatibility=RegistryCompatibilityMetadata(
           biological_stage="GATK4 reference sequence dictionary",
           accepted_planner_types=("ReferenceGenome",),
           produced_planner_types=(),
           reusable_as_reference=True,
           execution_defaults={
               "profile": "local",
               "result_manifest": "run_manifest.json",
               "resources": {"cpu": "1", "memory": "4Gi", "execution_class": "local"},
               "slurm_resource_hints": {"cpu": "1", "memory": "4Gi", "walltime": "00:30:00"},
               "runtime_images": {"gatk_sif": "data/images/gatk4.sif"},
               "module_loads": ("python/3.11.9", "apptainer/1.4.1"),
           },
           supported_execution_profiles=("local", "slurm"),
           synthesis_eligible=True,
           composition_constraints=(
               "Requires a reference genome FASTA; emits the sequence dictionary downstream tools depend on.",
           ),
           pipeline_family="variant_calling",
           pipeline_stage_order=1,
       ),
   ),
   ```

5. Delete the scaffolding test added in Step 02; add real tests.

Tests to add (`tests/test_variant_calling.py`):

- `test_create_sequence_dictionary_registry_entry_shape` — entry exists,
  pipeline_family is `"variant_calling"`, interface names match
  `MANIFEST_OUTPUT_KEYS`.
- `test_create_sequence_dictionary_invokes_run_tool` — patch `run_tool`,
  assert cmd is `["gatk", "CreateSequenceDictionary", "-R", <ref>, "-O", <dict>]`
  and the `.dict` path is wired into the returned `File`.
- `test_create_sequence_dictionary_emits_manifest` — patch `run_tool`
  and create a fake `.dict` in the output dir; assert
  `run_manifest.json` exists, has `stage == "create_sequence_dictionary"`,
  and `outputs["sequence_dict"]` matches the `.dict` path.

Verification:

- `python -m compileall src/flytetest/tasks/variant_calling.py src/flytetest/registry/_variant_calling.py`
- `pytest tests/test_variant_calling.py -xvs`
- `python -c "import flytetest.server"` clean.

Commit message: "variant_calling: add create_sequence_dictionary task + registry entry".

Then mark Step 03 Complete in docs/gatk_milestone_a/checklist.md.

Add a CHANGELOG.md entry dated today under `## Unreleased`.
```
