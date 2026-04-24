Use this prompt when starting Step 05 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md  (§7.5 offline-compute invariant)
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§8 — staging preflight module)

Context:

- This is Step 05. Pure-additive — no existing code is touched. The executor
  only calls into staging in Step 23.
- Depends on Step 06 (WorkflowSpec.tool_databases) only if the module reads
  `artifact.tool_databases` in its body. If Step 06 has not landed yet,
  guard the read with `getattr(artifact, "tool_databases", {}) or {}`.

Key decisions already made (do not re-litigate):

- `local` profile skips the shared-fs-roots check but still verifies
  existence. `slurm` profile enforces both existence AND shared-fs membership.
- `classify_slurm_failure()` is untouched (hard constraint).
- The function returns a list of findings rather than raising; the caller
  (executor in Step 23, validate_run_recipe in Step 24) decides policy.

Task:

1. Create `src/flytetest/staging.py` matching §8 of the master plan:
   `StagingFinding` dataclass (kind/key/path/reason), `check_offline_staging(
   artifact, shared_fs_roots, *, execution_profile)` walking
   `artifact.runtime_images`, `artifact.tool_databases`,
   `artifact.resolved_input_paths`.

2. `_check_path(kind, key, path, shared_fs_roots, execution_profile)`
   returns zero or more findings per path. Reasons: `not_found`,
   `not_readable`, `not_on_shared_fs`. `shared_fs_roots` is a tuple of `Path`.

3. A path is "on shared fs" when one of the roots is a parent (use
   `Path.is_relative_to` from py3.9+). The slurm profile adds the
   `not_on_shared_fs` finding; local profile skips it.

Tests to add (tests/test_staging.py):

- Missing container → `kind="container"` finding with `reason="not_found"`.
- Missing tool DB → `kind="tool_database"` finding.
- Resolved input outside `shared_fs_roots` (slurm) → `not_on_shared_fs`.
- All-present + under shared fs → empty findings.
- Local profile ignores `not_on_shared_fs` but surfaces `not_found`.

Verification:

- `python -m compileall src/flytetest/staging.py`
- `pytest tests/test_staging.py`

Commit message: "staging: add check_offline_staging preflight module (DESIGN §7.5)".

Then mark Step 05 Complete in docs/mcp_reshape/checklist.md.
```
