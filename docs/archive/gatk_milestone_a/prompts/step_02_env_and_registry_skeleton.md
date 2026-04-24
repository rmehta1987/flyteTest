Use this prompt when starting Step 02 or when handing it off to another session.

Model: Sonnet sufficient — scaffolding; no biology logic yet.

```text
You are continuing Milestone A of the FLyteTest Phase 3 GATK4 port under:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.2)

Context:

- This is Step 02 (Foundation). Depends on Step 01 (planner types exist).
- Blocks Steps 03–09: each task step appends a `RegistryEntry` to the
  tuple created here and decorates the task with `variant_calling_env.task`.

Key decisions already made (do not re-litigate):

- New task env mirrors `annotation_env` in `src/flytetest/config.py`:
  name `"variant_calling"`, GATK4 SIF placeholder path
  `"data/images/gatk4.sif"`, resources 4 CPU / 16 GiB (local),
  Slurm hints 8 CPU / 32 GiB / 12h, module_loads
  `("python/3.11.9", "apptainer/1.4.1")`.
- Empty registry tuple at scaffolding time is intentional — each task
  step appends to it.
- No showcase_module is set in this step; showcase entries (if any)
  appear in Milestone B when workflows land.

Task:

1. In `src/flytetest/config.py`, add `variant_calling_env` next to the
   existing task envs. Mirror the `annotation_env` declaration shape
   exactly (same helper functions, same TASK_ENVIRONMENTS_BY_NAME
   registration if present). Constants used (e.g., `VARIANT_CALLING_SIF_DEFAULT`)
   live in the same file.

2. Create `src/flytetest/registry/_variant_calling.py`:

   ```python
   """Registry entries for the variant_calling pipeline family."""

   from __future__ import annotations

   from flytetest.registry._types import (
       InterfaceField,
       RegistryCompatibilityMetadata,
       RegistryEntry,
   )

   VARIANT_CALLING_ENTRIES: tuple[RegistryEntry, ...] = ()
   ```

3. Wire the new tuple into `src/flytetest/registry/__init__.py`:
   - Import `VARIANT_CALLING_ENTRIES` alongside the existing family imports.
   - Append to the `REGISTRY_ENTRIES` aggregation tuple.
   - Preserve alphabetical or existing order convention (verify before
     inserting).

4. Update `AGENTS.md` Project Structure section under `Registry package`:
   add `_variant_calling.py — GATK4 germline variant calling family`
   (insert in family listing).

5. Update `.codex/registry.md` if it enumerates families — add
   variant_calling to the list. If it does not enumerate families, no
   change needed.

6. Add one smoke test:

   ```python
   def test_variant_calling_family_registered():
       from flytetest.registry import REGISTRY_ENTRIES
       families = {e.compatibility.pipeline_family for e in REGISTRY_ENTRIES
                   if e.compatibility is not None}
       assert "variant_calling" not in families, (
           "Step 02 expects no entries yet — family appears only after Step 03"
       )
       # Import path smoke
       from flytetest.registry._variant_calling import VARIANT_CALLING_ENTRIES
       assert VARIANT_CALLING_ENTRIES == ()
   ```

   This test is scaffolding — it gets deleted or rewritten in Step 03
   once the first entry lands. Add a clear TODO comment pointing at Step
   03.

Tests to add:

- `test_variant_calling_family_registered` (scaffolding; deleted in
  Step 03).

Verification:

- `python -m compileall src/flytetest/config.py src/flytetest/registry/`
- `python -c "from flytetest.registry import REGISTRY_ENTRIES; print(len(REGISTRY_ENTRIES))"`
- `python -c "import flytetest.server"` — must succeed.
- `pytest tests/test_registry.py -xvs` (or whichever file covers
  registry import smoke) green.

Commit message: "variant_calling: wire variant_calling_env + registry skeleton".

Then mark Step 02 Complete in docs/gatk_milestone_a/checklist.md.

Add a CHANGELOG.md entry dated today under `## Unreleased`.
```
