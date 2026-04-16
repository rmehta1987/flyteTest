# Milestone 20 Restructure: M20a + M20b

## Context

Milestone 19 is complete. The existing numbered Milestone 20 is
"Storage-Native Durable Asset Return" (proposed 2026-04-08, not started).
A second body of work — HPC Failure Recovery — is needed before the cluster
validation tests (`docs/mcp_cluster_prompt_tests.md`) become truly useful,
and is the first item in the roadmap's P2a track.

Both bodies of work are independent enough to run on separate branches
simultaneously, but they share `spec_executor.py` in different sections.
The project already uses the lettered sub-milestone pattern (M18, M18a, M18b,
M18c), so the cleanest approach is:

- **M20a** — HPC Failure Recovery (new; cluster-facing, immediate value)
- **M20b** — Storage-Native Durable Asset Return (rename of existing M20)

Existing M21–M25 keep their numbers. No renumbering of later milestones.

---

## Can They Run in Parallel?

Yes — they touch different sections of `spec_executor.py`:

| Area | M20a | M20b |
|---|---|---|
| `SlurmWorkflowSpecExecutor.retry()` | ✓ | — |
| `render_slurm_script()` | ✓ | — |
| `SlurmRunRecord` fields | ✓ | — |
| `LocalWorkflowSpecExecutor.execute()` | — | ✓ |
| Manifest writing / `run_manifest.json` | — | ✓ |
| `resolver.py` | — | ✓ |
| `spec_artifacts.py` | — | ✓ |
| `types/assets.py` | — | ✓ |
| `server.py` (monitor/retry tools) | ✓ | — |
| `specs.py` (ResourceSpec) | ✓ | — |

A parallel approach uses two branches: `m20a-hpc-recovery` and
`m20b-durable-assets`. Merge M20a first (smaller, needed for cluster),
then M20b.

For a sequential approach, do M20a before M20b — same reason.

---

## What Changes in the Project Docs

1. **Rename existing M20 entry** in `docs/realtime_refactor_checklist.md`
   from `## Milestone 20` to `## Milestone 20b` (one heading change, no
   content change).

2. **Rename plan doc** from
   `docs/realtime_refactor_plans/2026-04-08-milestone-20-storage-native-durable-asset-return.md`
   to
   `docs/realtime_refactor_plans/2026-04-08-milestone-20b-storage-native-durable-asset-return.md`.

3. **Add `## Milestone 20a`** section to the checklist before M20b.

4. **Create submission prompt** at
   `docs/realtime_refactor_milestone_20a_submission_prompt.md`.

5. **Update** `docs/realtime_refactor_milestone_20_submission_prompt.md`
   to rename/redirect to M20b (or just rename the file to
   `..._20b_submission_prompt.md`).

---

## Milestone 20a: HPC Failure Recovery

### Files Changed

| File | Change |
|---|---|
| `src/flytetest/specs.py` | `ResourceSpec.module_loads` field |
| `src/flytetest/spec_executor.py` | `render_slurm_script()`, `SlurmWorkflowSpecExecutor.retry()`, `SlurmWorkflowSpecExecutor._submit_saved_artifact()` |
| `src/flytetest/spec_executor.py` | `SlurmRunRecord.resource_overrides` field |
| `src/flytetest/server.py` | `_retry_slurm_job_impl()`, `retry_slurm_job()`, `_monitor_slurm_job_impl()`, `monitor_slurm_job()`, `_result_from_slurm_lifecycle()` |
| `src/flytetest/mcp_contract.py` | Update tool descriptions |
| `tests/test_server.py` | 10 new tests (see below) |
| `tests/test_mcp_prompt_flows.py` | Extend retry flow test |
| `docs/mcp_showcase.md` | Document `resource_overrides` and `tail_lines` |
| `docs/mcp_cluster_prompt_tests.md` | Add Scenario 6 (escalation retry) |

### Part 1 — Resource-Escalation Retry (TODO 9)

**Problem:** OOM and TIMEOUT are classified `resource_exhaustion` /
`retryable=False`. `retry_slurm_job` resubmits the identical frozen recipe.
Users cannot recover from resource failures from the MCP client.

**New parameter:**
```python
retry_slurm_job(run_record_path: str, resource_overrides: dict[str, str] | None = None)
```
Valid keys: `cpu`, `memory`, `walltime`, `queue`, `account`, `gpu`.

**Gate change in `SlurmWorkflowSpecExecutor.retry()`:**
```
if not failure_classification.retryable:
    if failure_class == "resource_exhaustion" and resource_overrides:
        allow escalation retry        ← new path
    else:
        decline (existing behavior)
```
`classify_slurm_failure()` is unchanged — TIMEOUT/OOM stay `retryable=False`.

**`_submit_saved_artifact()` change:** when `resource_overrides` is non-empty,
apply to a `dataclasses.replace()` copy of `resource_spec` before
`render_slurm_script()`. Frozen artifact is never modified.

**`SlurmRunRecord` new field:**
```python
resource_overrides: dict[str, str] = field(default_factory=dict)
```
Persisted in the child record for audit.

**Tests:**
1. OOM + `resource_overrides={"memory": "64Gi"}` → `supported=True`, sbatch
   script has `--mem=64G`, child record `resource_overrides` matches
2. TIMEOUT + `resource_overrides={"walltime": "04:00:00"}` → same pattern
3. OOM with no `resource_overrides` → `supported=False` (unchanged behavior)
4. Child record `resource_overrides` round-trips through save/load

### Part 2 — Configurable Module Loading (TODO 7)

**Problem:** `render_slurm_script()` (~line 1367 in `spec_executor.py`)
hardcodes `python/3.11.9` and `apptainer/1.4.1`.

**`ResourceSpec` new field:**
```python
module_loads: tuple[str, ...] = field(default_factory=tuple)
```
Accepted via `resource_request` dict:
`{"module_loads": ["python/3.11.9", "apptainer/1.4.1", "cuda/12.0"]}`.

**`render_slurm_script()` change:**
```python
modules = list(resource_spec.module_loads) or ["python/3.11.9", "apptainer/1.4.1"]
```
Default behavior (empty `module_loads`) is identical — no existing recipes break.

**Constraint:** `ResourceSpec` uses `slots=True`; verify `dataclasses.asdict()`
works after adding the new field before shipping.

**Tests:**
5. `prepare_run_recipe` with `module_loads` → artifact `resource_spec.module_loads`
   persisted correctly
6. Submit with custom `module_loads` → sbatch script contains those modules, not
   the hardcoded defaults
7. Submit with empty `module_loads` → script still contains `python/3.11.9`
   and `apptainer/1.4.1` (regression guard)

### Part 3 — Job Log Tail (TODO 8)

**Problem:** `monitor_slurm_job` returns `stdout_path`/`stderr_path` but never
reads them.

**New parameter:**
```python
monitor_slurm_job(run_record_path: str, tail_lines: int = 50)
```
`tail_lines=0` disables reading.

**In `_monitor_slurm_job_impl()`:** after assembling the lifecycle result, if
`final_scheduler_state` is non-null (terminal):
```python
def _read_tail(path, n):
    if n == 0 or path is None or not path.is_file():
        return None
    try:
        lines = path.read_text(errors="replace").splitlines()
        return "\n".join(lines[-n:]) if lines else ""
    except OSError:
        return None
```
`_result_from_slurm_lifecycle()` gains `stdout_tail` and `stderr_tail` fields.
Reading lives in the server layer, not the executor — executor stays pure.

**Tests:**
8. Terminal state + stdout file with known content → `stdout_tail` contains
   last N lines
9. Non-terminal state (RUNNING) → `stdout_tail` and `stderr_tail` are `None`
10. Terminal state + missing stdout file → `stdout_tail` is `None`, no crash

---

## Milestone 20b: Storage-Native Durable Asset Return

Unchanged from the existing plan. After renaming:

- Checklist entry: `## Milestone 20b` (was `## Milestone 20`)
- Plan doc: `2026-04-08-milestone-20b-storage-native-durable-asset-return.md`
- Submission prompt: `docs/realtime_refactor_milestone_20b_submission_prompt.md`

Start point: `docs/realtime_refactor_milestone_20b_submission_prompt.md`
(task: read the plan, audit resolver/spec_executor/spec_artifacts/types/assets.py,
define durable reference model, update manifests additively, add tests).

Gate: M20a complete (or on a merged branch) before starting M20b on `realtime`.

---

## Verification (M20a)

1. `.venv/bin/python -m unittest tests.test_server tests.test_mcp_prompt_flows tests.test_spec_executor -v`
   — all 10 new tests pass; existing 340 tests unchanged
2. Cluster prompt Scenario 5b with `resource_overrides`: inspect the rendered
   sbatch script under `.runtime/runs/<run_id>/` before job submission to
   confirm the override appears in the `#SBATCH` directives
3. Cluster prompt Scenario 2c: verify `stdout_tail` and `stderr_tail` appear
   in the `monitor_slurm_job` response for a completed BUSCO job
4. `git diff --check` — no trailing whitespace
