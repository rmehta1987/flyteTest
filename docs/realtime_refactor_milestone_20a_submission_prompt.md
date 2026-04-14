Use this prompt when handing the Milestone 20a HPC Failure Recovery slice off
to another Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/ml20_plan.md
- /home/rmeht/Projects/flyteTest/ml20_assessment_plan.md
- /home/rmeht/Projects/flyteTest/plan-m20aHpcFailureRecovery.prompt.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/tasks.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md

Context:

- Milestone 19 is complete. The Slurm submit/monitor/retry/cancel lifecycle,
  approval gating, local-to-Slurm resume, and run-history listing are all
  working. Tests pass (340 offline + 1 live-cluster smoke skipped).
- M20a adds HPC failure recovery: resource-escalation retries, configurable
  Slurm module loads, and bounded scheduler log tails surfaced via
  `monitor_slurm_job`.
- M20b (Storage-Native Durable Asset Return) is a separate milestone numbered
  after this one. Do not start M20b work here.
- The consolidated plan in `plan-m20aHpcFailureRecovery.prompt.md` supersedes
  `ml20_plan.md` wherever the two differ. Follow the consolidated plan.

Key decisions already made (do not re-litigate):

- `SlurmRunRecord.resource_overrides` field type is `ResourceSpec | None`, not
  `dict[str, str]`.
- `ResourceSpec.module_loads` must flow through `_coerce_resource_spec()` and
  `_merge_resource_specs()` in `planning.py` — that file was missing from the
  original plan's touched-file list.
- Log tails live in the MCP response dict only; do not add them to executor
  dataclasses.
- All module names must be shell-quoted via `shlex.quote()` in
  `render_slurm_script()`.
- `_read_text_tail()` must use a `collections.deque`-based read (never
  `path.read_text()` then slice) and must reject paths outside `allowed_root`.
- `DEADLINE` is explicitly excluded from the escalation-retry path; document
  this alongside TIMEOUT.

Task:

Phase 0 — Pre-implementation doc renaming (no code changes):
1. Confirm `docs/realtime_refactor_checklist.md` has a `## Milestone 20a`
   section before `## Milestone 20b` (rename the existing `## Milestone 20`
   heading to `## Milestone 20b` if not already done).
2. Confirm the M20 plan doc has been renamed from
   `docs/realtime_refactor_plans/2026-04-08-milestone-20-storage-native-durable-asset-return.md`
   to `...milestone-20b-...`; rename it if not done.
3. Rename or add a redirect in
   `docs/realtime_refactor_milestone_20_submission_prompt.md` to point to the
   `_20b_` prompt (or rename the file itself if the old name is still in place).

Phase 1 — Data model (no inter-phase deps):
4. Add `module_loads: tuple[str, ...] = field(default_factory=tuple)` to
   `ResourceSpec` in `src/flytetest/specs.py`. Verify `from_dict()` still
   deserializes legacy payloads that lack this field (field has a default, so
   this should be automatic — confirm and add a comment noting the
   cache-identity implication).
5. Add `resource_overrides: ResourceSpec | None = None` to `SlurmRunRecord` in
   `src/flytetest/spec_executor.py`. Verify `save_slurm_run_record()` /
   `load_slurm_run_record()` round-trips work for both old and new records.
6. Update `_coerce_resource_spec()` in `src/flytetest/planning.py` to handle a
   `module_loads` key: accept a list or tuple and coerce to `tuple[str, ...]`.
7. Update `_merge_resource_specs()` in `src/flytetest/planning.py` so the
   override's `module_loads` wins when non-empty, otherwise the base value is
   preserved (same pattern as other fields).

Phase 2 — Execution helpers (depends on Phase 1):
8. Add `DEFAULT_SLURM_MODULE_LOADS = ("python/3.11.9", "apptainer/1.4.1")` near
   the top of the relevant section in `src/flytetest/spec_executor.py`.
9. Add `_RETRY_RESOURCE_OVERRIDE_FIELDS = {"cpu", "memory", "walltime", "queue",
   "account", "gpu"}` constant.
10. Add `_coerce_retry_resource_overrides(value)` — normalizes a plain mapping
    or `ResourceSpec` at the API edge; returns `(ResourceSpec | None,
    tuple[str, ...])` where a non-empty second element means decline without
    submitting.
11. Add `_effective_resource_spec(frozen, overrides)` — overlays retry
    escalation values onto the frozen recipe's resource spec using
    `dataclasses.replace()`; never mutates the frozen artifact.
12. Add `_slurm_module_load_lines(resource_spec)` — returns
    `["  module load <quoted_name>", ...]` lines, falling back to
    `DEFAULT_SLURM_MODULE_LOADS` when `resource_spec.module_loads` is empty.
13. Replace the hardcoded `module load python/3.11.9` / `module load
    apptainer/1.4.1` lines in `render_slurm_script()` with a call to
    `_slurm_module_load_lines(resource_spec)`.
14. Add `resource_overrides: ResourceSpec | None = None` parameter to
    `_submit_saved_artifact()`. Before calling `render_slurm_script()`, compute
    `effective = _effective_resource_spec(binding_plan.resource_spec,
    resource_overrides)` and use `effective` for rendering. Write both
    `resource_spec=effective` and `resource_overrides=resource_overrides` into
    the `SlurmRunRecord`.
15. Update `SlurmWorkflowSpecExecutor.retry()` to accept `resource_overrides:
    Mapping[str, Any] | ResourceSpec | None = None`. Gate: call
    `_coerce_retry_resource_overrides()` first; if limitations are non-empty,
    return `SlurmRetryResult(supported=False, ...)`. Allow an escalation retry
    when `failure_class == "resource_exhaustion"` and `override_spec is not
    None`, even though `retryable` is False. Pass `resource_overrides=
    override_spec` to `_submit_saved_artifact()`. Document `DEADLINE` as
    excluded from this path (same treatment as TIMEOUT).

Phase 3 — Server layer (depends on Phase 2):
16. Add `MAX_MONITOR_TAIL_LINES = 500` constant and `_read_text_tail(path, *,
    tail_lines, allowed_root)` to `src/flytetest/server.py`. The helper must:
    - raise `ValueError` for negative `tail_lines`
    - clamp to `MAX_MONITOR_TAIL_LINES`
    - resolve both `path` and `allowed_root` with `.resolve()` and reject the
      read if `path` is not relative to `allowed_root`
    - use `collections.deque(handle, maxlen=line_count)` to avoid loading the
      whole file
    - return `None` on `OSError` or out-of-root path
17. Add `tail_lines: int = 50` parameter to `_monitor_slurm_job_impl()`. After
    lifecycle reconciliation, if `final_scheduler_state` is non-null (terminal),
    read `stdout_tail` and `stderr_tail` via `_read_text_tail()` with
    `allowed_root=record.run_record_path.parent`. Add both to the returned dict;
    always include the keys (value is `None` when non-terminal or file absent).
18. Add `resource_overrides: dict[str, Any] | None = None` to
    `_retry_slurm_job_impl()` and `retry_slurm_job()`. Thread through to
    `executor.retry()`.
19. Update tool descriptions in `src/flytetest/mcp_contract.py` for
    `retry_slurm_job` (document `resource_overrides` and valid keys) and
    `monitor_slurm_job` (document `tail_lines`).

Phase 4 — Tests (parallel with Phase 3):
20. Confirm whether `tests/test_spec_executor.py` exists; create it if missing.
    Add or extend tests to cover all 18 cases listed in the consolidated plan:
    1. `prepare_run_recipe` with `module_loads` list → frozen artifact tuple
    2. `_merge_resource_specs()` preserves base `module_loads` when override empty
    3. OOM + `resource_overrides={"memory": "64Gi"}` → child `resource_spec.memory`,
       child `resource_overrides.memory`, sbatch `--mem=64G`
    4. TIMEOUT + `resource_overrides={"walltime": "04:00:00"}` → same pattern
    5. OOM with no `resource_overrides` → `supported=False`
    6. Child `resource_overrides` round-trips through save/load
    7. Custom `module_loads` → script has those modules, not defaults
    8. Empty `module_loads` → script has `python/3.11.9` and `apptainer/1.4.1`
    9. Custom module names are shell-quoted in the rendered script
    10. Legacy record without `module_loads` deserializes via `ResourceSpec.from_dict()`
    11. Unknown override key → `supported=False` before sbatch
    12. Negative `tail_lines` → `ValueError`; oversized → clamped
    13. Path outside `allowed_root` → `_read_text_tail()` returns `None`
    14. Terminal state + stdout content → `stdout_tail` has last N lines
    15. Non-terminal (RUNNING) → `stdout_tail` and `stderr_tail` are `None`
    16. Terminal + missing stdout file → `stdout_tail` is `None`, no crash
    17. `DEADLINE` → `supported=False` without escalation
    18. Extend `test_mcp_failed_job_is_retried_to_completed` in
        `test_mcp_prompt_flows.py` to use `resource_overrides`

Phase 5 — Docs (parallel with Phases 3–4):
21. Update `docs/mcp_showcase.md`: add `resource_overrides` and `tail_lines`
    param descriptions; update the Phase 5 (On Failure) decision tree so
    TIMEOUT/OOM can now use `retry_slurm_job` with `resource_overrides` for
    escalation (no longer always requires a new `prepare_run_recipe`).
22. Update `docs/mcp_cluster_prompt_tests.md`: add Scenario 6 covering an
    escalation retry from an OOM failure using `resource_overrides`.
23. Update `docs/capability_maturity.md`: revise the resource recovery row to
    reflect the new escalation path.
24. Update `README.md` if any walkthrough examples reference the old
    "re-prepare required for resource failures" guidance.
25. Update `docs/realtime_refactor_checklist.md`: add M20a checklist items and
    mark them complete when the test suite passes.
26. Update `CHANGELOG.md`: add M20a entries under `## Unreleased`.

Verification (run before declaring M20a complete):
1. `python -m unittest tests.test_server tests.test_mcp_prompt_flows tests.test_spec_executor -v`
   — all new tests pass; existing suite still passes
2. Inspect the sbatch script written to `.runtime/runs/<run_id>/` for a recipe
   with custom `module_loads`: module names are shell-quoted, custom modules
   appear instead of defaults.
3. Inspect a child `SlurmRunRecord` JSON after an escalation retry: `resource_spec`
   has the effective values, `resource_overrides` has only the overridden fields.
4. Exercise `_read_text_tail()` with a path outside `allowed_root`: confirm it
   returns `None` without raising.
5. `git diff --check` — no trailing whitespace.

Important constraints:

- Do not modify the frozen saved artifact at retry time; apply overrides only
  in `_submit_saved_artifact()`.
- Do not add `stdout_tail`/`stderr_tail` fields to any executor dataclass;
  they belong in the MCP response dict only.
- Do not change `classify_slurm_failure()` — TIMEOUT and OOM stay
  `retryable=False`; the new path is an explicit user escalation, not automatic
  retryability.
- Keep README, DESIGN, checklist docs, registry metadata, planner behavior,
  MCP contract, and tests aligned.

Report back with:

- checklist items completed
- files changed
- validation run output summary
- current checklist status
- remaining blockers or assumptions
```
