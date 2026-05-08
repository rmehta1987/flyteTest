# Slurm UX Rollout — Checklist

## Phase 0 — Polish (this week)

### Step 01 — Canonical run dir + recipe-id hash + SCIENTIST_GUIDE fix

- [x] `src/flytetest/spec_artifacts.py`: write spec to `.runtime/runs/<recipe_id>/spec.json`; ensure run dir exists at freeze time
- [x] `src/flytetest/spec_artifacts.py`: recipe-id truncation appends `-<hash4>` (blake2b digest_size=2) when `target_name` exceeds 25 chars; short names unchanged
- [x] `src/flytetest/spec_executor.py`: update spec reads to new location
- [x] `src/flytetest/planning.py`: spec-path resolution updates
- [x] `src/flytetest/server.py`: `validate_run_recipe`, `run_local_recipe`, `run_slurm_recipe` spec-path reads
- [x] `scripts/migrate_specs_to_runs.py`: one-shot move of existing `.runtime/specs/*.json` → `.runtime/runs/<recipe_id>/spec.json`; rmdir `.runtime/specs/`
- [x] Update tests asserting on `.runtime/specs/` paths
- [x] Fix `SCIENTIST_GUIDE.md:~168` Step 6 (`run_slurm_recipe(recipe_id=..., partition=..., account=...)` → `run_slurm_recipe(artifact_path=...)`); revise the surrounding paragraph
- [x] Update `CLAUDE.md` and `AGENTS.md` `.runtime/specs/` mentions
- [x] Update `CHANGELOG.md`
- [x] Compile + run focused tests

### Step 02 — runs/latest symlink + monitor_slurm_job paths-in-response

- [x] `src/flytetest/spec_executor.py` `_submit_saved_artifact`: create/update `.runtime/runs/latest` → `<recipe_id>` after successful submission (idempotent on retry)
- [x] `src/flytetest/spec_executor.py`: create `inputs/` and `outputs/` named symlinks within the run dir (one per declared shared FS root, or a multi-root variant)
- [x] `src/flytetest/server.py:3204`: `monitor_slurm_job` response includes `spec_path`, `run_record_path`, `stdout_path`, `stderr_path`, `outputs_dir`, `inputs_dir` as absolute paths
- [x] Test: after submission, `readlink .runtime/runs/latest` returns `<recipe_id>`
- [x] Test: `monitor_slurm_job(...)` response carries all 6 paths as absolute strings
- [x] Update `CHANGELOG.md`

### Step 03 — extend_module_loads with documented precedence

- [x] `src/flytetest/specs.py`: add `extend_module_loads: tuple[str, ...] = ()` to `ResourceSpec` (10 fields after this change)
- [x] `src/flytetest/spec_executor.py:1393`: precedence logic — only `module_loads` set → full replace; only `extend_module_loads` set → `DEFAULT + extend`; both set → `module_loads` wins, warning logged
- [x] Docstring on `ResourceSpec.extend_module_loads` highlights it as the recommended path
- [x] Test: warning emitted when both fields set; `module_loads` wins
- [x] Test: `extend_module_loads=["bcftools/1.20"]` ships 5 modules (defaults + bcftools)
- [x] Update `CHANGELOG.md`

### Step 04 — ResourceSpec format validators

- [x] `src/flytetest/specs.py`: add `__post_init__` to `ResourceSpec` with regex validators
- [x] `memory` matches `^\d+(\.\d+)?(K|M|G|T)i?$`
- [x] `walltime` matches `^(\d+-)?\d{1,2}:\d{2}(:\d{2})?$`
- [x] `cpu` parses as positive integer string
- [x] `partition` non-empty when `execution_class != "local"`
- [x] `account` non-empty when `execution_class != "local"`
- [x] Test: `memory="32 GB"` (with space) raises; `walltime="48h"` raises; valid values pass
- [x] Update `CHANGELOG.md`

### Step 05 — list_slurm_partitions MCP tool

- [x] Create `src/flytetest/slurm_introspection.py` (or extend `slurm_monitor.py`) with `list_slurm_partitions()` wrapping `sinfo --format=...`
- [x] Returns `list[dict]` with `name`, `max_walltime`, `max_nodes`, `available`, etc.
- [x] Register as MCP tool in `src/flytetest/server.py`
- [x] Add tool name constant + `TOOL_DESCRIPTIONS` entry in `mcp_contract.py`
- [x] Test: mocks `sinfo` output; verifies parsing
- [x] Update `CHANGELOG.md`

### Step 06 — sbatch --test-only integration

- [x] `src/flytetest/staging.py` (or `src/flytetest/server.py:3014` `validate_run_recipe`): after `check_offline_staging` passes, run `sbatch --test-only` against the generated script
- [x] Failure mode: structured findings (`kind: "slurm_test_only"`, `reason: "partition_invalid" | "account_unknown" | "resources_exceed_limits"`) consistent with `StagingFinding` shape
- [x] Returned alongside `staging_findings` in `validate_run_recipe` reply
- [x] Test: invalid partition produces a structured finding (mock `sbatch --test-only` failure path)
- [x] Update `CHANGELOG.md`

## Phase 1 — Small structural wins (gated on Phase 0; per-step prompts drafted later)

### Step 07 — First-submission resource_overrides + submitted_resources audit field

- [ ] `src/flytetest/server.py:2998`: `run_slurm_recipe` accepts `resource_overrides: dict | None`
- [ ] `SlurmRunRecord` adds `submitted_resources: ResourceSpec | None`
- [ ] When overrides applied, `submitted_resources` records the effective values that went to sbatch
- [ ] Recipe `resource_request` stays unchanged (frozen)
- [ ] Tests + CHANGELOG

### Step 08 — User-friendly failure presentation layer

- [ ] `src/flytetest/spec_executor.py:1043`: `SlurmFailureClassification` adds `category_label`, `summary`, `suggested_action`
- [ ] Mapping table per the plan covers all 6 internal classes × terminal states
- [ ] `monitor_slurm_job` and `retry_slurm_job` responses surface friendly fields first
- [ ] Internal `failure_class` and `retryable` stay frozen (preserves AGENTS.md hard constraint)
- [ ] Tests + CHANGELOG

### Step 09 — retry_with_default_escalation 1.5x policy

- [ ] `src/flytetest/server.py:3292`: `retry_slurm_job` accepts `retry_with_default_escalation: bool = False`
- [ ] When True + state was `OUT_OF_MEMORY` → memory becomes `ceil(1.5 × original GiB)`
- [ ] When True + state was `TIMEOUT` → walltime becomes `1.5 × original` (capped at partition max if introspection in place)
- [ ] Tests + CHANGELOG

### Step 10 — Queue-wait ETA + state-transition log

- [ ] `src/flytetest/server.py:3204`: `monitor_slurm_job` queries `squeue -j <jobid> --start --format='%S'` for PENDING jobs; adds `estimated_start_time`
- [ ] `SlurmRunRecord` adds `state_history` field with structured entries (`state`, `since`, `duration_human`)
- [ ] `monitor_slurm_job` appends an entry whenever observed state differs from last known
- [ ] `monitor_slurm_job` response also carries one-line summary (`"PENDING 47m → RUNNING 2h13m → COMPLETED"`)
- [ ] Tests + CHANGELOG

### Step 11 — list_slurm_accounts MCP tool

- [ ] Extend `src/flytetest/slurm_introspection.py` with `list_slurm_accounts()` wrapping `sshare --user=$USER --format=...`
- [ ] Register as MCP tool
- [ ] `validate_run_recipe` flags unknown accounts using this tool's output
- [ ] Tests + CHANGELOG

### Step 12 — Externalize default module loads to .flytetest/cluster.toml

- [ ] `src/flytetest/spec_executor.py:1290`: `DEFAULT_SLURM_MODULE_LOADS` becomes fallback constant
- [ ] New helper resolves env var `FLYTETEST_DEFAULT_MODULE_LOADS` → `.flytetest/cluster.toml` → fallback (uses stdlib `tomllib`)
- [ ] Create `.flytetest/cluster.toml.example` (committed) and add `.flytetest/cluster.toml` to `.gitignore`
- [ ] Update tests at `tests/test_planning.py:~2017`, `tests/test_spec_executor.py:~1654-1660`, `~1670-1707`, `tests/test_serialization_regression.py:~1527-1529`
- [ ] Tests + CHANGELOG

## Phase 2 — Backlog (no prompts; revisit if/when needed)

- `log_keyword_signals` field on `SlurmFailureClassification` (additive; preserves frozen taxonomy)
- Auto-cleanup of failed-run artifacts (opt-in)
- `replay_run(run_id)` shortcut

## Done criteria

### Phase 0 done

- [x] `.runtime/specs/` directory does not exist; all specs live at `.runtime/runs/<recipe_id>/spec.json`
- [x] `cd .runtime/runs/<recipe_id>` shows spec, run record, slurm logs, and `inputs/` + `outputs/` symlinks; user can investigate any submission without leaving the dir
- [x] `cd .runtime/runs/latest` always works after the most recent submission
- [x] `extend_module_loads=["bcftools/1.20"]` produces 5 modules; warning logged when both `module_loads` and `extend_module_loads` are set
- [x] `ResourceSpec(memory="32 GB")` raises at freeze
- [ ] `list_slurm_partitions()` returns non-empty list on RCC (deferred — verified locally with mocked `sinfo`; full RCC verification is the user's smoke step)
- [x] `validate_run_recipe` catches a typo'd partition/account/qos before sbatch
- [x] `SCIENTIST_GUIDE.md` Step 6 example actually runs
- [x] Recipe ID for a long-named workflow ends in `-<hash4>`
- [x] Full test suite passes (1049 tests; 6 pre-existing failures untouched)
- [x] `CHANGELOG.md` updated for each step

### Phase 1 done

- [ ] `run_slurm_recipe(..., resource_overrides={"partition": "broadwl"})` submits without re-staging
- [ ] `submitted_resources` on the run record records overrides; `resource_request` in the recipe stays frozen
- [ ] OOM-then-retry cycle produces friendly `category_label`, `summary`, `suggested_action`; user can copy the suggestion verbatim
- [ ] `retry_slurm_job(..., retry_with_default_escalation=True)` on a known-OOM job picks `1.5x` memory automatically
- [ ] `monitor_slurm_job(...)` on a PENDING job returns `estimated_start_time`
- [ ] `state_history` shows structured entries with `duration_human`
- [ ] `list_slurm_accounts()` returns non-empty list on RCC
- [ ] `.flytetest/cluster.toml` overrides `DEFAULT_SLURM_MODULE_LOADS`; env var overrides config; fallback works
- [ ] All 4 listed tests retargeted; full suite passes
- [ ] `CHANGELOG.md` updated for each step

### Milestone close

- [ ] All Phase 0 and Phase 1 steps complete
- [ ] `git mv docs/2026-05-07-slurm-ux-rollout/ docs/archive/` once stable
