Use this prompt when handing the Milestone 21b HPC Observability slice off to
another Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-15-milestone-21b-hpc-observability.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md

Context:

- This is Milestone 21b. Milestone 21 must be complete before starting this
  work. Confirm the `## Milestone 21` section in
  `docs/realtime_refactor_checklist.md` is marked complete before proceeding.
- M21b owns `fetch_job_log`, `wait_for_slurm_job`, and the two new MCP
  resources (`run-recipes/<path>`, `result-manifests/<path>`).
- Do not modify `run_task`, `list_available_bindings`, `get_run_summary`, or
  `inspect_run_result` — those belong to M21.

Key decisions already made (do not re-litigate):

- `fetch_job_log` validates the path under `DEFAULT_RUN_DIR` using the same
  `_read_text_tail`-style path resolution as the existing `monitor_slurm_job`
  log safety. Cap at `MAX_MONITOR_TAIL_LINES` (500).
- `wait_for_slurm_job` is synchronous (blocking, `time.sleep`) — not async.
  Default timeout 300 s, default poll interval 15 s. Poll interval floor: 5 s.
  Returns the same shape as `monitor_slurm_job` plus `timed_out: bool`.
- MCP resources `flytetest://run-recipes/{path}` and
  `flytetest://result-manifests/{path}` are read-only. Paths validated inside
  `REPO_ROOT`. New URIs append at indices 4 and 5 of `SERVER_RESOURCE_URIS` —
  do not shift the existing 4 indices.

Baseline:

- Run `.venv/bin/python -m unittest 2>&1 | tail -5` before any changes.
  Current baseline: 381 tests, all pass (1 skipped). Do not regress.

Task (implement in order):

Part 1 — TODO 19: MCP resources for recipes and manifests

1. In `src/flytetest/mcp_contract.py`:
   - Add `RUN_RECIPE_RESOURCE_URI_PREFIX` and `RESULT_MANIFEST_RESOURCE_URI_PREFIX`
     string constants.
   - Append both URI prefixes to `SERVER_RESOURCE_URIS`.

2. In `src/flytetest/server.py`:
   - Add `resource_run_recipe(path: str) -> str` — validate path inside
     REPO_ROOT, load and return raw JSON artifact content.
   - Add `resource_result_manifest(path: str) -> str` — validate path is a dir
     inside REPO_ROOT, load and return `run_manifest.json` content.
   - Register both in `create_mcp_server()` with `mcp.resource()`.

3. Add 2 tests to `tests/test_server.py`:
   - `test_resource_run_recipe_returns_artifact_json`
   - `test_resource_result_manifest_returns_manifest_json`

Part 2 — TODO 8: fetch_job_log

4. In `src/flytetest/mcp_contract.py`:
   - Add `FETCH_JOB_LOG_TOOL_NAME = "fetch_job_log"` and add to `MCP_TOOL_NAMES`.

5. In `src/flytetest/server.py`:
   - Add `_fetch_job_log_impl(log_path, tail_lines, *, run_dir)` using
     `_read_text_tail` with `run_dir` as `allowed_root`.
   - Add `fetch_job_log(log_path: str, tail_lines: int = 100) -> dict`.
   - Register in `create_mcp_server()`.

6. Add 3 tests to `tests/test_server.py`:
   - `test_fetch_job_log_returns_tail_when_file_exists`
   - `test_fetch_job_log_returns_unsupported_when_file_absent`
   - `test_fetch_job_log_rejects_path_outside_run_dir`

Part 3 — TODO 11: wait_for_slurm_job

7. In `src/flytetest/mcp_contract.py`:
   - Add `WAIT_FOR_SLURM_JOB_TOOL_NAME = "wait_for_slurm_job"` and add to
     `MCP_TOOL_NAMES`.

8. In `src/flytetest/server.py`:
   - Add `_wait_for_slurm_job_impl(run_record_path, timeout_s, poll_interval_s,
     *, run_dir, scheduler_runner, command_available, sleep_fn=time.sleep)`.
   - Add `wait_for_slurm_job(run_record_path: str, timeout_s: int = 300,
     poll_interval_s: int = 15) -> dict`.
   - Register in `create_mcp_server()`.

9. Add 3 tests to `tests/test_server.py`:
   - `test_wait_for_slurm_job_returns_immediately_for_terminal_job`
   - `test_wait_for_slurm_job_polls_until_terminal`
   - `test_wait_for_slurm_job_reports_timeout_when_job_does_not_complete`
   Use an injected `sleep_fn` (a lambda that records calls) to avoid actual
   sleeping in tests.

Part 4 — Docs

10. Update `docs/mcp_showcase.md`: add a new section documenting `fetch_job_log`
    and `wait_for_slurm_job` with example calls and response field descriptions.

11. Update `docs/capability_maturity.md`: add "Job log fetching" and
    "Job polling / wait-for-completion" rows as `Current (M21b)`.

12. Update `README.md`: add `fetch_job_log`, `wait_for_slurm_job` to the
    supported tools list; add the two new resource URI prefixes if the README
    documents resources.

13. Update `docs/realtime_refactor_checklist.md`: mark all M21b checkboxes `[x]`,
    update status to `Complete (2026-04-15)` (or the actual date).

14. Update `CHANGELOG.md`: add dated entries for each part.

Validation:

- `.venv/bin/python -m unittest tests.test_server -v 2>&1 | tail -30`
- `.venv/bin/python -m unittest 2>&1 | tail -5`  — must show 389+ tests, all pass
- `git diff --check`  — no trailing whitespace
```
