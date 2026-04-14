## Plan: M20a HPC Failure Recovery — Consolidated

**TL;DR:** `ml20_plan.md` has the right structure but has several correctness gaps that `ml20_assessment_plan.md` caught. The plan below folds those corrections in so implementation doesn't hit surprises mid-way. The biggest deltas are: (1) typed `ResourceSpec | None` instead of `dict[str, str]` for durable overrides, (2) `planning.py` was omitted from the touched-file list, (3) the log-tail reading is unbounded and lacks a path traversal guard, and (4) module names need shell-quoting.

---

### Possible Blockers

1. **`planning.py` was not in `ml20_plan.md`'s file list** — `_coerce_resource_spec()` currently handles `cpu, memory, gpu, queue, account, walltime, execution_class, notes` but has no case for `module_loads`. If this function is not updated, MCP callers passing `{"module_loads": [...]}` via `prepare_run_recipe(resource_request=...)` will silently drop the field. This is a correctness blocker for Part 2 (Configurable Module Loading).

2. **`ResourceSpec` + `BindingPlan` JSON serialization / cache-identity drift** — `ResourceSpec` uses `slots=True` and `frozen=True`. Adding `module_loads` changes `dataclasses.asdict()` output, which affects `cache_identity_key` for any artifact that includes a `ResourceSpec`. Legacy artifacts lack the field but `from_dict()` should default it to `()` — verify before shipping.

3. **`SlurmRunRecord.resource_overrides` type** — `ml20_plan.md` proposes `dict[str, str]`, but the repo's typed spec model uses `ResourceSpec | None` everywhere else. Using a raw dict breaks the inspectability contract established by M19 and creates a `from_dict()` mismatch. The assessment strongly recommends `ResourceSpec | None`.

4. **Log tail security / memory** — `ml20_plan.md`'s `_read_tail()` calls `path.read_text()` and then `splitlines()[-n:]`, loading the whole file. A large scheduler log file would OOM the server process. Additionally, there is no path traversal guard — a tampered run-record could point `stdout_path` outside the run directory. Both must be fixed before landing.

5. **Shell injection via module names** — `render_slurm_script()` will embed module names directly in the script without quoting. A space or special character in a module name (e.g., `"python 3.11.9"`) would silently break the generated script or allow injection. Use `shlex.quote()`.

---

### Additions Over `ml20_plan.md`

| Addition | Source | Why |
|---|---|---|
| `planning.py` in touched-file list | Assessment | `module_loads` must flow through `_coerce_resource_spec()` + `_merge_resource_specs()` |
| `_coerce_retry_resource_overrides()` helper | Assessment | Separates API edge validation from submission logic; returns explicit limitations tuple |
| `_effective_resource_spec()` helper | Assessment | Clean `dataclasses.replace()`-based overlay; frozen artifact never touched |
| `_slurm_module_load_lines()` helper | Assessment | Extracted render helper; fallback to defaults when `module_loads` is empty |
| `DEFAULT_SLURM_MODULE_LOADS` constant | Assessment | Avoids magic strings repeated in two places |
| `MAX_MONITOR_TAIL_LINES = 500` cap | Assessment | Prevents runaway memory when `tail_lines` is huge |
| `allowed_root` path traversal guard | Assessment | Security — prevents reading files outside the run directory |
| `deque`-based file reading | Assessment | Bounded tail without loading whole file |
| Tests 11–18 (see below) | Assessment | Edge cases missing from the 10-test list in the plan |
| DEADLINE coverage | Assessment | Not mentioned in plan; needs explicit doc or test |

---

### Steps

**Phase 0 — Pre-implementation doc renaming** *(no code changes)*
1. Rename M20 → M20b heading in `docs/realtime_refactor_checklist.md`
2. Rename plan doc `2026-04-08-milestone-20-...md` → `2026-04-08-milestone-20b-...md`
3. Add `## Milestone 20a` section to checklist
4. Create `docs/realtime_refactor_milestone_20a_submission_prompt.md`
5. Redirect/rename `docs/realtime_refactor_milestone_20_submission_prompt.md` → `_20b_`

**Phase 1 — Data model** *(independent, no code deps)*
6. Add `module_loads: tuple[str, ...] = field(default_factory=tuple)` to `ResourceSpec` in `src/flytetest/specs.py`
7. Add `resource_overrides: ResourceSpec | None = None` to `SlurmRunRecord` in `src/flytetest/spec_executor.py`
8. Update `_coerce_resource_spec()` and `_merge_resource_specs()` in `src/flytetest/planning.py` to handle `module_loads`

**Phase 2 — Execution helpers** *(depends on Phase 1)*
9. Add `DEFAULT_SLURM_MODULE_LOADS`, `_RETRY_RESOURCE_OVERRIDE_FIELDS`, `_coerce_retry_resource_overrides()`, `_effective_resource_spec()`, `_slurm_module_load_lines()` to `src/flytetest/spec_executor.py`
10. Update `render_slurm_script()` to use `_slurm_module_load_lines()` with `shlex.quote()`
11. Update `_submit_saved_artifact()` to accept `resource_overrides` and call `_effective_resource_spec()` before rendering; write both `resource_spec` and `resource_overrides` into the `SlurmRunRecord`
12. Update `SlurmWorkflowSpecExecutor.retry()` to accept `resource_overrides`; call `_coerce_retry_resource_overrides()` as a gate; thread override to `_submit_saved_artifact()`

**Phase 3 — Server layer** *(depends on Phase 2, parallel with Phase 4)*
13. Add `MAX_MONITOR_TAIL_LINES`, `_read_text_tail()` with path-traversal guard to `src/flytetest/server.py`
14. Update `_monitor_slurm_job_impl()` with `tail_lines` param; add `stdout_tail`/`stderr_tail` to returned dict
15. Update `_retry_slurm_job_impl()` and `retry_slurm_job()` with `resource_overrides` param
16. Update `src/flytetest/mcp_contract.py` tool descriptions

**Phase 4 — Tests** *(parallel with Phase 3, depends on Phase 2)*
17. Add tests covering: `module_loads` flow, typed override round-trip, OOM/TIMEOUT escalation, empty/unknown override, tail bounds, path traversal, shell quoting, legacy deserialization, DEADLINE exclusion, and MCP prompt flow extension

Full test list:
1. `prepare_run_recipe` with `resource_request={"module_loads": [...]}` → persists tuple in frozen artifact
2. `_merge_resource_specs()` preserves registry-default `module_loads` if override is empty
3. OOM + `resource_overrides={"memory": "64Gi"}` → child `resource_spec.memory=="64Gi"`, child `resource_overrides.memory=="64Gi"`, sbatch script has `--mem=64G`
4. TIMEOUT + `resource_overrides={"walltime": "04:00:00"}` → same pattern
5. OOM with no `resource_overrides` → `supported=False` (unchanged behavior)
6. Child `resource_overrides` round-trips through save/load
7. Custom `module_loads` → sbatch script contains those modules, not defaults
8. Empty `module_loads` → script contains `python/3.11.9` and `apptainer/1.4.1`
9. Custom module names are shell-quoted in the rendered script
10. Legacy artifact/run-record without `module_loads` still deserializes through `ResourceSpec.from_dict()`
11. Unknown override key → declined before sbatch
12. Negative `tail_lines` → `ValueError`; oversized `tail_lines` → clamped to `MAX_MONITOR_TAIL_LINES`
13. Log-tail reading ignores a tampered (path traversal) path outside run-record directory → returns `None`
14. Terminal state + stdout content → `stdout_tail` contains last N lines
15. Non-terminal (RUNNING) → `stdout_tail` and `stderr_tail` are `None`
16. Terminal state + missing stdout file → `stdout_tail` is `None`, no crash
17. `DEADLINE` failure returns `supported=False` without escalation (document excluded path)
18. Extend `test_mcp_failed_job_is_retried_to_completed` in `test_mcp_prompt_flows.py` to cover escalation retry with `resource_overrides`

**Phase 5 — Docs** *(parallel with Phases 3–4)*
18. Update `docs/mcp_showcase.md` — add `resource_overrides` and `tail_lines` params; update "TIMEOUT/OOM require new prepare" text to reflect new escalation path
19. Update `docs/mcp_cluster_prompt_tests.md` — add Scenario 6 (escalation retry)
20. Update `src/flytetest/mcp_contract.py` — tool descriptions
21. Update `README.md` — if walkthrough references old "re-prepare" requirement for resource failures
22. Update `docs/capability_maturity.md` — resource recovery row
23. Update `docs/realtime_refactor_checklist.md` — M20a section with items
24. Update `CHANGELOG.md` — add M20a unreleased entries

---

### Verification

1. `python -m unittest tests.test_server tests.test_mcp_prompt_flows tests.test_spec_executor -v` — all new tests pass; full suite remains green
2. Inspect a rendered sbatch script: module names are shell-quoted, custom modules override defaults, empty `module_loads` falls back to defaults
3. Inspect a child `SlurmRunRecord` JSON: `resource_spec` reflects the effective (merged) spec, `resource_overrides` captures only what was changed
4. Call `_read_text_tail()` with a path pointing outside `allowed_root`: returns `None` with no exception
5. `git diff --check` — no trailing whitespace

---

### Decisions

- **`resource_overrides` type:** `ResourceSpec | None` — typed, inspectable, consistent with repo patterns
- **`module_loads` coercion:** flows through `planning.py` so MCP callers can pass it in `resource_request`
- **Log tails in executor:** kept out of executor dataclasses; only added to MCP response dict
- **`DEADLINE`:** explicitly excluded from escalation path (same treatment as TIMEOUT) — document this, don't leave it ambiguous
- **Shell quoting:** all module names via `shlex.quote()`

---

### Further Considerations

1. **`test_spec_executor.py` may not exist yet** — module-load and resource-override unit tests naturally belong in a spec-executor test file. Confirm whether that file exists or whether tests should go into `test_server.py`.
2. **M20b gate** — the plan says M20b should not start until M20a is merged. If branches diverge on `spec_executor.py`, the merge conflict surface is `_submit_saved_artifact()` return type and manifest writing. Worth noting in the M20b submission prompt.

---

### Files Changed (M20a)

| File | Change |
|---|---|
| `src/flytetest/specs.py` | `ResourceSpec.module_loads` field |
| `src/flytetest/planning.py` | `_coerce_resource_spec()`, `_merge_resource_specs()` — **missing from original plan** |
| `src/flytetest/spec_executor.py` | `SlurmRunRecord.resource_overrides`, `render_slurm_script()`, `_submit_saved_artifact()`, `retry()`, new helpers |
| `src/flytetest/server.py` | `_monitor_slurm_job_impl()`, `_retry_slurm_job_impl()`, `retry_slurm_job()`, `_read_text_tail()` |
| `src/flytetest/mcp_contract.py` | tool descriptions |
| `tests/test_server.py` | new tests |
| `tests/test_mcp_prompt_flows.py` | extend escalation retry flow |
| `tests/test_spec_executor.py` | module-load + resource-override unit tests (confirm file exists) |
| `docs/mcp_showcase.md` | document `resource_overrides`, `tail_lines`, updated failure guidance |
| `docs/mcp_cluster_prompt_tests.md` | Scenario 6 |
| `docs/realtime_refactor_checklist.md` | M20a section |
| `docs/capability_maturity.md` | resource recovery row |
| `README.md` | walkthrough update |
| `CHANGELOG.md` | M20a unreleased entries |
| `docs/realtime_refactor_milestone_20a_submission_prompt.md` | new file |
