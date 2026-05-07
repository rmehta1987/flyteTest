# Slurm UX Rollout — Milestone Plan

**Date:** 2026-05-07
**Status:** Planning

## Problem

flyteTest's Slurm submission/monitoring/retry surface works but isn't intuitive. A scientist running `germline_short_variant_discovery` on caslake/Midway3 has to:

- Track 3-5 paths per submission (spec at `.runtime/specs/`, run record + stdout + stderr at `.runtime/runs/<recipe_id>/`, output artifacts elsewhere) and `cd` between them to investigate a single failure.
- Read `AGENTS.md` to learn that `module_loads=["bcftools/1.20"]` silently drops `gatk/4.5.0` + `samtools/1.22.1` + `python/3.11.9` + `apptainer/1.4.1`. The escape hatch (`from flytetest.spec_executor import DEFAULT_SLURM_MODULE_LOADS`) requires importing a private constant.
- Know their cluster's valid `partition` and `account` strings — typos are caught 30 seconds into the sbatch attempt, not at freeze.
- Decode failures from internal-enum jargon (`failure_class: "scheduler_infrastructure"`) instead of friendly strings ("Cluster issue — safe to retry").
- Pick OOM-retry memory values manually (`32G → 48G`) when the system has every signal it needs to recommend `1.5x`.

This milestone delivers the Phase 0 polish wins (no architectural risk, ship-this-week) and Phase 1 small structural wins (gated on Phase 0 paying off). Phase 2 is documented as backlog.

## Solution overview

### Phase 0 — Polish (6 steps, this week)

| Step | Concern |
|---|---|
| 01 | Single canonical run dir migration: `.runtime/specs/<recipe_id>.json` → `.runtime/runs/<recipe_id>/spec.json`; eliminate the directory split. Includes recipe-id hash suffix for long workflow names + SCIENTIST_GUIDE Step 6 docs fix. |
| 02 | `runs/latest` symlink + `monitor_slurm_job` response carries every relevant path. |
| 03 | `extend_module_loads` first-class kwarg with documented precedence (legacy `module_loads` wins if both set; warn). |
| 04 | `ResourceSpec` format validators in `__post_init__`: memory, walltime, cpu, partition, account regex / non-empty checks. |
| 05 | `list_slurm_partitions()` MCP tool wrapping `sinfo`. No-auth introspection. |
| 06 | `sbatch --test-only` integration in `validate_run_recipe` to catch partition/account/qos errors before queuing. |

### Phase 1 — Small structural wins (6 steps, gated on Phase 0)

| Step | Concern |
|---|---|
| 07 | First-submission `resource_overrides` on `run_slurm_recipe`; new `submitted_resources` field on `SlurmRunRecord` for provenance. |
| 08 | User-friendly failure presentation layer: `category_label`, `summary`, `suggested_action` on `SlurmFailureClassification`. Internal `failure_class` taxonomy stays frozen. |
| 09 | `retry_with_default_escalation=True` 1.5x escalation for OOM/timeout. |
| 10 | Queue-wait ETA via `squeue --start`; structured `state_history` with `duration_human` per entry. |
| 11 | `list_slurm_accounts()` MCP tool wrapping `sshare`. |
| 12 | Externalize `DEFAULT_SLURM_MODULE_LOADS` to `.flytetest/cluster.toml` (gitignored); env-var override; hardcoded fallback. |

### Phase 2 — Backlog (no prompts; revisit when needed)

- `log_keyword_signals` field on `SlurmFailureClassification` (additive; preserves frozen taxonomy)
- Auto-cleanup of failed-run artifacts (opt-in)
- `replay_run(run_id)` shortcut

## Architectural anchors (do not change)

1. Frozen recipe before sbatch (AGENTS.md §Hard Constraints)
2. sbatch-from-session, not the Flyte Slurm plugin (2FA constraint)
3. `check_offline_staging` runs before any sbatch
4. `classify_slurm_failure()` internal 6-class taxonomy is frozen — Phase 1 step 08's user-friendly fields are *additive*, not a rename

## Files Changed

### Phase 0

**New:**
- `src/flytetest/slurm_introspection.py` (or extend `slurm_monitor.py`) — `list_slurm_partitions`
- `scripts/migrate_specs_to_runs.py` — one-shot migration of pre-existing spec files

**Modified:**
- `src/flytetest/spec_artifacts.py` — spec write/read paths to `.runtime/runs/<recipe_id>/spec.json`; recipe-id hash suffix on long target names
- `src/flytetest/spec_executor.py` — spec reads; `inputs/` + `outputs/` symlink farm in `_submit_saved_artifact`; `runs/latest` symlink update; `module_loads` precedence + warning
- `src/flytetest/specs.py` — `ResourceSpec` adds `extend_module_loads`; adds `__post_init__` validators
- `src/flytetest/planning.py` — spec-path resolution
- `src/flytetest/server.py` — `validate_run_recipe` adds `--test-only`; `monitor_slurm_job` response carries paths; `run_local_recipe` / `run_slurm_recipe` spec-path updates
- `src/flytetest/staging.py` — (optional) `--test-only` integration if hosted here instead of `server.py`
- `src/flytetest/mcp_contract.py` — tool name constant + `TOOL_DESCRIPTIONS` entry for `list_slurm_partitions`
- `SCIENTIST_GUIDE.md` — Step 6 fix (line ~168)
- `CLAUDE.md`, `AGENTS.md` — `.runtime/specs/` mentions update
- Tests asserting on `.runtime/specs/` paths
- `CHANGELOG.md`

### Phase 1

**New:**
- `.flytetest/cluster.toml.example` (committed) and `.flytetest/cluster.toml` (gitignored)
- `.gitignore` entry for `.flytetest/cluster.toml`

**Modified:**
- `src/flytetest/server.py:2998` — `run_slurm_recipe` adds `resource_overrides`
- `src/flytetest/server.py:3204` — `monitor_slurm_job` adds queue ETA, `state_history` append, `category_label`/`summary`/`suggested_action` surfacing
- `src/flytetest/server.py:3292` — `retry_slurm_job` adds `retry_with_default_escalation`; surfaces `suggested_action` echo
- `src/flytetest/spec_executor.py:1043` — `SlurmFailureClassification` adds `category_label`, `summary`, `suggested_action`
- `src/flytetest/spec_executor.py:1290` — `DEFAULT_SLURM_MODULE_LOADS` becomes fallback; loader resolves env var → `.flytetest/cluster.toml` → fallback
- `src/flytetest/spec_executor.py` — `SlurmRunRecord` adds `submitted_resources`, `state_history` fields
- `src/flytetest/slurm_introspection.py` — `list_slurm_accounts`
- `src/flytetest/mcp_contract.py` — tool name constant + `TOOL_DESCRIPTIONS` entry for `list_slurm_accounts`
- Tests: `tests/test_planning.py:~2017`, `tests/test_spec_executor.py:~1654-1660` and `~1670-1707`, `tests/test_serialization_regression.py:~1527-1529` (retarget against test-fixture config or mock loader)
- `CHANGELOG.md`

## Non-Goals

- Replacing the frozen-recipe model with mutable submissions
- Building a Flyte Slurm plugin alternative (sbatch-from-session is correct given 2FA)
- Compute-node access probing via canary sbatch (`--test-only` is the cheap-and-different version)
- Streaming logs over websocket (`monitor_slurm_job` tails are fine for HPC scale)
- Lifting `max_attempts=3` cap (low-frequency pain)
- Changing the 6-class failure taxonomy (hard constraint)
- `extend_module_loads` mutual-exclusion with hard freeze error (replaced by precedence + warning)

## Source plan

Full PD-feedback assessment that produced this milestone: `~/.claude/plans/examine-the-agents-within-optimized-tome.md`

Two reviewer passes (Plan + Explore agents) ran against v1; the v2 plan folded in Block-level fixes (already-existing `retry_slurm_job(resource_overrides)` discovered, `extend_module_loads` mutual-exclusion replaced with precedence) and Flag-level fixes (mis-tiered docs bug, wrong phase for the major-version-modules change → externalized config approach instead, missed `submitted_resources` audit field, hardcoded module versions in 4 tests).
