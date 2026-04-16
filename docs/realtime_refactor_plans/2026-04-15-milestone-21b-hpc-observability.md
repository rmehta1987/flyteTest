# Milestone 21b: HPC Observability

Date: 2026-04-15
Status: Ready to implement

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 21b

Bundled items:
- TODO 19 — MCP resources: `run-recipes/<id>` and `result-manifests/<id>`
- TODO 8  — Job log fetching (read content, not just return path)
- TODO 11 — Job polling / wait-for-completion

---

## Current State

- `monitor_slurm_job` reconciles state and returns `stdout_tail`/`stderr_tail`
  (capped at 500 lines) when a job reaches a terminal state. Paths are also
  returned but the full content is not accessible as an MCP resource.
- The four MCP server resources registered today are scope, supported-targets,
  example-prompts, and prompt-and-run-contract. None exposes saved recipe
  artifacts or result manifests.
- No wait-for-completion tool exists. Clients must poll `monitor_slurm_job`
  manually until a terminal state appears.

---

## TODO 19 — MCP Resources for Recipes and Manifests

### Goal

Add two read-only MCP resource templates that let clients fetch the raw
content of:
1. A frozen recipe artifact by its artifact path (ID = file path).
2. A `run_manifest.json` from a known result directory (ID = dir path).

### Constraints

- Resources are read-only. No side effects.
- Paths must be validated against `REPO_ROOT` the same way `_read_text_tail`
  validates against `allowed_root` — no path traversal outside the repo.
- Return `supported=False` with a limitation message if the file is absent or
  outside `REPO_ROOT`.
- Resource URI scheme: `flytetest://run-recipes/{path}` and
  `flytetest://result-manifests/{path}` where `{path}` is the URL-encoded
  absolute file path.

### Implementation

**`mcp_contract.py`:**
- Add `RUN_RECIPE_RESOURCE_URI_PREFIX = "flytetest://run-recipes/"` and
  `RESULT_MANIFEST_RESOURCE_URI_PREFIX = "flytetest://result-manifests/"`.
- Add both prefixes to `SERVER_RESOURCE_URIS`.

**`server.py`:**
- Add `resource_run_recipe(path: str) -> str` — validates path is inside
  `REPO_ROOT`, loads the JSON artifact file, returns raw JSON string.
- Add `resource_result_manifest(path: str) -> str` — validates `path` is a
  directory inside `REPO_ROOT`, loads `path/run_manifest.json`, returns raw
  JSON string.
- Register both with `mcp.resource()` in `create_mcp_server()`.

### Tests (2 tests)

- `test_resource_run_recipe_returns_artifact_json` — write a minimal artifact
  JSON to a temp file inside a temp dir treated as REPO_ROOT; confirm the
  resource returns valid JSON.
- `test_resource_result_manifest_returns_manifest_json` — write a minimal
  `run_manifest.json` to a temp dir; confirm the resource returns its contents.

---

## TODO 8 — Job Log Fetching (Content, Not Just Path)

### Goal

`monitor_slurm_job` already reads `stdout_tail`/`stderr_tail` for terminal
jobs (M21 already uses `_read_text_tail`). The gap is:
- For **in-progress** jobs, the tails are `None`.
- There is no standalone MCP tool to fetch the current content of a Slurm
  log file given its path.

Add `fetch_job_log(log_path, tail_lines=100)` as a new MCP tool that reads
bounded log content at any lifecycle state (running or terminal), with the
same path-validation safety as `_read_text_tail`.

### Constraints

- The path must resolve inside `DEFAULT_RUN_DIR` (the standard Slurm run dir).
- `tail_lines` is capped at `MAX_MONITOR_TAIL_LINES` (500).
- Returns `supported=False` if the file does not exist yet (job may not have
  started writing) — this is not an error.
- No scheduler calls. Reads only the file on disk.

### Implementation

**`mcp_contract.py`:**
- Add `FETCH_JOB_LOG_TOOL_NAME = "fetch_job_log"` and add to `MCP_TOOL_NAMES`.

**`server.py`:**
- Add `_fetch_job_log_impl(log_path, tail_lines, *, run_dir)`.
- Add `fetch_job_log(log_path: str, tail_lines: int = 100) -> dict[str, object]`.
- Register in `create_mcp_server()`.

### Tests (3 tests)

- `test_fetch_job_log_returns_tail_when_file_exists` — write a log file to a
  temp run dir; confirm the tool returns the correct tail.
- `test_fetch_job_log_returns_unsupported_when_file_absent` — call with a
  path that does not exist; confirm `supported=False`.
- `test_fetch_job_log_rejects_path_outside_run_dir` — call with a path
  traversing outside the allowed root; confirm `supported=False`.

---

## TODO 11 — Job Polling / Wait-for-Completion

### Goal

Add `wait_for_slurm_job(run_record_path, timeout_s=300, poll_interval_s=15)`
as a synchronous MCP tool that polls `_monitor_slurm_job_impl` until the job
reaches a terminal state (any `final_scheduler_state`) or the timeout expires.

**Not** a background async loop — the async poll loop in `slurm_monitor.py`
already handles background reconciliation. This is a client-invoked
request-response timeout-bounded wait, suitable for short-running jobs or
test fixtures.

### Constraints

- Terminal states: any non-None `final_scheduler_state` in the run record.
- `timeout_s` max: 3600 (1 hour). Default: 300 (5 minutes).
- `poll_interval_s` min: 5 seconds (no busy-polling).  Default: 15 seconds.
- Returns the same shape as `monitor_slurm_job` for the final observed state,
  plus a `timed_out: bool` field.
- If the job is already in a terminal state on the first poll, return
  immediately without sleeping.
- The tool is synchronous (blocking), acceptable because MCP clients invoke it
  interactively. Do not use `asyncio.sleep` — use `time.sleep`.

### Implementation

**`mcp_contract.py`:**
- Add `WAIT_FOR_SLURM_JOB_TOOL_NAME = "wait_for_slurm_job"` and add to
  `MCP_TOOL_NAMES`.

**`server.py`:**
- Add `_wait_for_slurm_job_impl(run_record_path, timeout_s, poll_interval_s,
  *, run_dir, scheduler_runner, command_available)`.
- Add `wait_for_slurm_job(run_record_path: str, timeout_s: int = 300,
  poll_interval_s: int = 15) -> dict[str, object]`.
- Register in `create_mcp_server()`.

### Tests (3 tests)

- `test_wait_for_slurm_job_returns_immediately_for_terminal_job` — job is
  already COMPLETED on first poll; confirm `timed_out=False` and exactly 1
  scheduler call.
- `test_wait_for_slurm_job_polls_until_terminal` — first poll returns RUNNING,
  second returns COMPLETED; confirm `timed_out=False` and 2 scheduler calls.
  Inject a fake `time.sleep` to avoid actual sleeping.
- `test_wait_for_slurm_job_reports_timeout_when_job_does_not_complete` — all
  polls return RUNNING and timeout expires; confirm `timed_out=True`.

---

## Acceptance Criteria

- All new tests pass; full suite stays green.
- `fetch_job_log` is documented in `docs/mcp_showcase.md`.
- `wait_for_slurm_job` is documented in `docs/mcp_showcase.md`.
- TODO 19 resources appear in `SERVER_RESOURCE_URIS` and the checklist items
  are marked complete.
- `docs/capability_maturity.md` updated: "Job log fetching" and "Job
  polling/wait" rows updated to `Current (M21b)`.
- `README.md` updated: new tools added to the supported-tools list.
- Checklist items for M21b checked.
- `CHANGELOG.md` updated with M21b entries.

## Compatibility Risks

- `SERVER_RESOURCE_URIS` is used in `create_mcp_server()` to register
  resources; indices 0–3 are already used. New resource URIs must use indices
  4 and 5 — do not shift existing indices.
- `_read_text_tail` uses `allowed_root` to prevent path traversal; `fetch_job_log`
  must use the same pattern with `DEFAULT_RUN_DIR` as the root.
- `wait_for_slurm_job` calls `time.sleep` synchronously inside the MCP
  server event loop — this is acceptable for bounded interactive use but must
  not be used in async tests. Inject a fake sleep callable for testing.
