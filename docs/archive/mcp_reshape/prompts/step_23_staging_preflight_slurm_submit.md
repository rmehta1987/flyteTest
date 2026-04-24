Use this prompt when starting Step 23 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md  (hard constraints: never submit a Slurm job without a frozen run record; do not change classify_slurm_failure semantics)
- /home/rmeht/Projects/flyteTest/DESIGN.md  (§7.5 offline-compute invariant)
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§8 — preflight offline-compute staging)

Context:

- This is Step 23. Depends on Steps 05 (`staging.py`),
  06 (`WorkflowSpec.tool_databases`), 21 (`run_task` reshape), 22 (`run_workflow`
  reshape). Wires `check_offline_staging` into the Slurm submit path so the
  server refuses to `sbatch` a recipe that cannot stage on the compute nodes.

Key decisions already made (do not re-litigate):

- Staging failure is pre-submission and reuses `RunReply` with a specific
  field pattern (§8 "Reply semantics"): `supported=True`,
  `execution_status="failed"`, `exit_status=None`, `run_record_path=""`,
  `recipe_id` + `artifact_path` populated, findings formatted into
  `limitations`. No new reply shape.
- Dry-run case is different — `dry_run=True` surfaces findings via
  `DryRunReply.staging_findings`, not `RunReply.limitations`. Dry-run never
  yields `execution_status="failed"` from staging. Step 21/22 already handle
  the dry-run branch; Step 23 wires only the real-submit branch.
- `shared_fs_roots` comes from the run tool's `resources` argument (or the
  entry's `execution_defaults.slurm_resource_hints`), NOT auto-detected.
  Symlinks resolve via `Path.resolve(strict=True)`; Apptainer bind-mount
  destinations must be declared by the caller. Broken symlinks become
  `StagingFinding(reason="not_readable")`.
- `classify_slurm_failure()` semantics are UNTOUCHED (AGENTS.md hard
  constraint). The staging check is a separate pre-submit gate; it short-
  circuits before `sbatch` is ever invoked.
- The frozen artifact stays on disk on staging failure so the scientist can
  fix the missing path and replay via `run_slurm_recipe(artifact_path=...)`.

Task:

1. In `src/flytetest/spec_executor.py`, extend
   `SlurmWorkflowSpecExecutor.submit(artifact_path)`:
   - Load the artifact.
   - Resolve `shared_fs_roots` from the artifact's resource spec
     (queue/account hints already live there per M19) using
     `Path.resolve(strict=True)`.
   - Call `check_offline_staging(artifact, shared_fs_roots)`.
   - If findings is empty, proceed to the existing `sbatch` path unchanged.
   - If findings is non-empty, DO NOT call `sbatch`. Return a sentinel that
     the run-tool wrapper translates into the §8 `RunReply(execution_status=
     "failed", run_record_path="", limitations=[<formatted finding>, ...])`
     shape. The executor itself does not produce a run record.

2. Update the run-tool call sites (Step 21 + Step 22 bodies) so the slurm
   branch converts the sentinel into the documented `RunReply` shape. Keep
   the happy-path return contract unchanged when findings is empty.

3. Format each `StagingFinding` as
   `"<kind> '<key>' at <path>: <reason>"` so the scientist can read the
   cause in `limitations` without parsing a nested dict.

4. `execution_profile="local"` continues to call `check_offline_staging` but
   skips the on-shared-fs check (§8 "Local-profile behavior"). Missing local
   paths still surface via `BindingPathMissingError` during
   `_materialize_bindings`, before staging runs.

Tests to add (tests/test_spec_executor.py + tests/test_server.py):

- Unreachable container → `sbatch` is NEVER called; `RunReply.limitations`
  contains the formatted finding; `recipe_id` + `artifact_path` populated;
  `run_record_path == ""`.
- Unreachable `tool_databases` path → same shape, different `kind` in the
  finding.
- Happy-path (all paths resolve on a `tmp_path`-rooted shared FS root) →
  `sbatch` IS called; the normal run record is emitted.
- Broken symlink inside a shared root → finding with `reason="not_readable"`
  and the original (unresolved) path preserved.
- Symlink inside shared root pointing at a target inside the same root →
  passes.
- Symlink inside shared root pointing outside any shared root → fails.
- `execution_profile="local"` with a missing shared-FS path → still passes
  staging (only existence/readability enforced); missing local paths
  surface through `BindingPathMissingError` instead.
- Replay: after staging failure, `run_slurm_recipe(artifact_path=...)` run
  against the still-on-disk artifact succeeds once the path is fixed.

Verification:

- `python -m compileall src/flytetest/spec_executor.py`
- `pytest tests/test_spec_executor.py tests/test_server.py`

Commit message: "spec_executor: gate slurm submit on check_offline_staging (pre-submit)".

Then mark Step 23 Complete in docs/mcp_reshape/checklist.md.
```
