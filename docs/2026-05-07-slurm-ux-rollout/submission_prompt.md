# Submission Prompt — Slurm UX Rollout

You are picking up the Slurm UX Rollout milestone — a phased ergonomics improvement for flyteTest's Slurm submission / monitoring / retry surface. The milestone is sized to ship in two passes (Phase 0 polish, then Phase 1 small structural wins) with explicit gates between phases. Phase 2 is backlog only.

## Goal

Reduce friction for scientists running Slurm-backed workflows on caslake/Midway3 (or comparable HPCs). Concrete wins per phase:

- **Phase 0** (this week): collapse the spec/run directory split, fix the #1 silent footgun (`module_loads` replace), make partition introspection a real API, catch sbatch-rejection errors before queuing, validate `ResourceSpec` formats at freeze, fix the SCIENTIST_GUIDE Step 6 docs bug.
- **Phase 1** (2-4 weeks, only after Phase 0 pays off): first-submission resource overrides, default OOM escalation, queue-wait ETA, friendly failure messages, account introspection, externalized cluster-config for module defaults.
- **Phase 2** (backlog): log-keyword signals on `classify_slurm_failure`, auto-cleanup of failed-run artifacts, `replay_run` shortcut.

The full plan, scope, and gating logic live in `slurm-ux-rollout_plan.md`. Implementation tasks are tracked in `checklist.md`. Each Phase 0 step has a self-contained prompt under `prompts/`.

## Read First

Before touching code:

1. `AGENTS.md` — especially §Hard Constraints, §Read Before Editing, §Prompt/MCP/Slurm
2. `DESIGN.md`
3. `docs/2026-05-07-slurm-ux-rollout/slurm-ux-rollout_plan.md` — full milestone plan
4. `docs/2026-05-07-slurm-ux-rollout/checklist.md` — actionable tasks per phase
5. `.codex/code-review.md` — code-review discipline (MCP-Layer Branch-Free Rule)
6. `SCIENTIST_GUIDE.md` — current user-facing flow; Step 6 has a docs bug fixed in step 01
7. `src/flytetest/spec_artifacts.py`, `spec_executor.py`, `staging.py`, `server.py`, `specs.py` — every Phase 0 step touches at least one

## Architectural Anchors (do not change)

These are frozen per `AGENTS.md` §Hard Constraints and the milestone plan:

1. **Frozen recipe before sbatch.** Reproducibility-first.
2. **sbatch-from-session, not the Flyte Slurm plugin.** 2FA constraint.
3. **`check_offline_staging` runs before any sbatch.**
4. **`classify_slurm_failure()` internal 6-class taxonomy is frozen.** Phase 1 step 08 adds *additive* friendly fields (`category_label`, `summary`, `suggested_action`) — it does NOT rename the enum or change the existing 6 values.

If you find a reason any of these should change, write an ADR (`templates/decision-record.md`) and stop — do not silently violate.

## Tooling that should be active on this branch

The branch was rebased onto `main` after PR #13 merged, so these are live:

- `.claude/hooks/protect-files.sh` blocks edits to `server.py`, `mcp_contract.py`, `planning.py`, `spec_executor.py`, `registry/__init__.py`, `flyte_rnaseq_workflow.py` unless `FLYTETEST_ALLOW_COMPAT_EDIT=1` is set. Several Phase 0 / 1 steps legitimately need edits to these files — set the override env var for the duration of the work and unset it after.
- `.claude/hooks/post-edit-lint.sh` runs `ruff check --fix` on every Python edit via the project venv.
- `.claude/agents/drift-auditor.md` — invoke after each step to catch stale `.runtime/specs/` references, outdated docstrings, or registry drift.
- `templates/decision-record.md` — use whenever you make an architectural decision worth capturing (e.g., the `outputs/` symlink target convention in step 02, or any deviation from the plan).

Hooks load at session start, not mid-session. If they don't fire on your first edit, restart the Claude Code session.

## Order of Operations

Work Phase 0 in step order (01 → 06). Each step's prompt is self-contained.

| Step | File | Depends on |
|---|---|---|
| 01 | `prompts/step_01_canonical_run_dir.md` | — (foundational; do first) |
| 02 | `prompts/step_02_runs_latest_and_paths.md` | step 01 (run dir layout) |
| 03 | `prompts/step_03_extend_module_loads.md` | independent |
| 04 | `prompts/step_04_resource_spec_validators.md` | independent |
| 05 | `prompts/step_05_list_slurm_partitions.md` | independent |
| 06 | `prompts/step_06_sbatch_test_only.md` | step 05 helpful but not required |

Steps 03-06 can ship in any order after step 01 lands. Step 02 must follow step 01.

### After each step

1. Run focused tests: `pytest -k <touched-area>`
2. Update `CHANGELOG.md` per the template at the bottom of the step prompt
3. Tick the matching items in `checklist.md`
4. Commit with project prefix style (`infra(...)`, `docs(...)`, `fix(...)`); reference the step number in the message body
5. If hooks blocked a legitimate edit, document the `FLYTETEST_ALLOW_COMPAT_EDIT=1` override use in the CHANGELOG entry

### After Phase 0 (all 6 steps merged)

1. Run the **full** test suite locally
2. Invoke `Agent(subagent_type="drift-auditor", prompt="audit the Slurm UX rollout Phase 0 work for stale .runtime/specs/ references in docs, MCP docstrings, and milestone notes")` to catch any lingering pre-migration paths
3. Verify every "Phase 0 done" gate in `checklist.md` is met (not just "feature was built" but "feature paid back")
4. Only after the gates are verified, draft the Phase 1 step prompts (07-12) following the same format as Phase 0's prompts and continue

## Hard Don'ts

- Do not change `failure_class` enum values — frozen taxonomy (AGENTS.md hard constraint)
- Do not promote Phase 2 items into Phase 1 without explicit user OK
- Do not start Phase 1 before Phase 0 gates are met
- Do not skip the one-shot migration script in step 01 — leaving stale `.runtime/specs/` files breaks the canonical-run-dir invariant
- Do not bypass `protect-files.sh` without setting `FLYTETEST_ALLOW_COMPAT_EDIT=1` and documenting the override use
- Do not auto-merge any PR; the user merges after review

## Handoff Format

When pausing partway through, or completing a phase:

- Update `CHANGELOG.md` with dated entries per step
- Tick `checklist.md` items
- If any step's prompt diverged from what actually got implemented, update the prompt or append a `### Notes from execution` section to it
- Report concisely:
  - Which steps shipped (with commit SHAs)
  - Which are in flight
  - Any compat-critical edits with `FLYTETEST_ALLOW_COMPAT_EDIT=1` rationale
  - Any drift-auditor findings + their resolution
  - Any ADRs written

When the milestone is fully done (Phase 0 + Phase 1 gates met):

- `git mv docs/2026-05-07-slurm-ux-rollout/ docs/archive/`
- `CHANGELOG.md` final milestone-close entry
