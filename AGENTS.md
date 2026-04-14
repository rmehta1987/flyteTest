# FLyteTest Development Guide

## 1. Purpose

This is the working rulebook for implementation discipline. `DESIGN.md`
describes the target architecture; when the two diverge, follow `DESIGN.md`.
For current milestone status, see `docs/realtime_refactor_checklist.md`.

## 2. Working Rules

### Hard constraints [required — never violate]

- Do not silently rewrite the existing baseline; only change what the task requires.
- Do not modify frozen saved artifacts at retry or replay time.
- Do not submit a Slurm job without a frozen run record.
- Do not invent biological tool behavior not supported by notes, source code,
  or an explicitly documented assumption.
- Do not change `classify_slurm_failure()` semantics without an explicit decision record.
- Update docs, manifests, and tests whenever behavior changes — never leave them stale.

- Read `DESIGN.md` before making architecture or behavior changes.
- Read the relevant `.codex/*.md` guide before editing code, docs, or tests,
  especially [`.codex/documentation.md`](.codex/documentation.md) for
  documentation-style rules, [`.codex/testing.md`](.codex/testing.md) for
  test-writing guidance, [`.codex/code-review.md`](.codex/code-review.md) for
  review expectations, [`.codex/tasks.md`](.codex/tasks.md) for task-module
  work, and [`.codex/workflows.md`](.codex/workflows.md) for workflow-module
  work.
- Prefer registered tasks, workflows, planners, and manifest helpers over new
  one-off runtime logic for ordinary user requests.
- Keep biological steps narrow and faithful to `docs/braker3_evm_notes.md`.
- Preserve `flyte_rnaseq_workflow.py` as a compatibility entrypoint until the
  repo no longer needs the old `flyte run` surface, and keep new business logic
  out of that shim.
- Treat Slurm as a real execution target: submit, schedule, monitor, and cancel
  jobs from frozen run records rather than from ad hoc shell behavior.
- Keep `CHANGELOG.md` current as the shared agent memory for meaningful units
  of work, not only finalized milestones.
- Use dated checklist items or dated bullets in `CHANGELOG.md` for completed
  work so later agents can see when progress landed.
- Record what was tried, what worked, what failed, what is blocked, and any
  dead ends that should not be retried without a new reason.
- Add newly discovered tasks or follow-up risks to `CHANGELOG.md` while the
  implementation is still in progress.
- Make changes as small as possible while still solving the problem cleanly.
- Avoid broad refactors unless the requested change truly depends on them.
- If a change affects the biological pipeline order or supported workflow
  families, call that out explicitly in the change notes.

## 3. What To Update When Behavior Changes

- `README.md` when the user-facing workflow, examples, or supported scope
  change
- `DESIGN.md` when the architecture, execution model, or planning model changes
- `CHANGELOG.md` when the change is worth preserving as a visible project
  history note
- `docs/realtime_refactor_checklist.md` when a refactor milestone changes status
- `docs/realtime_refactor_plans/archive/` when a milestone is completed and
  should be kept as historical context
- `docs/realtime_refactor_milestone_*_submission_prompt.md` when the milestone
  scope, key decisions, or accepted constraints change
- `AGENTS.md` and this guide when the working rules themselves change
- manifests and result records when runtime output shapes change
- tests when the behavior, supported workflow family, or validation path
  changes

## 4. Validation Expectations

Run the checklist in `.codex/testing.md` before declaring a change complete.

## 5. Biological Guardrails

See `.codex/tasks.md` and `.codex/workflows.md` for biological and workflow constraints.

## 6. Prompt / MCP / Slurm Rules

- Treat natural-language prompts as requests for supported workflows, not as a
  license to invent new biology or new runtime behavior.
- Use the prompt layer to identify the biological goal, the workflow family,
  the needed inputs, and any resource request the user made.
- Freeze the chosen plan into a saved run recipe before execution starts.
- Keep prompt interpretation separate from execution so the same saved plan can
  be inspected and replayed later.
- Use MCP as the user-facing interface layer for planning, recipe preparation,
  validation, result inspection, and status reporting.
- Keep MCP responses structured and machine-readable so clients do not need to
  guess what the system meant.
- Treat Slurm as a real execution target: submit jobs from frozen run records,
  monitor job state, collect logs, and support cancellation.
- Use `sbatch` for submission from an already-authenticated HPC login session
  (the cluster's 2FA policy prevents SSH key pairing, so the Flyte Slurm plugin
  cannot be used); use `squeue` / `scontrol show job` / `sacct` for
  observation, and `scancel` for cancellation.
- MCP tool surface: `prepare_run_recipe` (freeze a recipe), `run_slurm_recipe`
  (submit), `monitor_slurm_job` (reconcile + log tail), `cancel_slurm_job`,
  `retry_slurm_job` (including resource-escalation retries for OOM/TIMEOUT via
  `resource_overrides`), `list_slurm_run_history`.
- `resource_request` accepts `module_loads` (list of Slurm module names) to
  override the default `python/3.11.9` / `apptainer/1.4.1` loads per recipe.
- `monitor_slurm_job` accepts `tail_lines` (default 50) to return bounded
  stdout/stderr tails for terminal jobs; set to 0 to disable.
- Record the scheduler job ID as soon as a job is accepted.
- Track the job through the scheduler lifecycle, including pending, running,
  completed, failed, and cancelled states.
- Record stdout and stderr log paths in the run record.
- Preserve the final scheduler state and any exit code or cancellation reason.
- Check offline compute-node assumptions before submission when the job depends
  on staged containers, databases, or inputs.
- Do not submit a Slurm job from vague resource language if the plan still
  needs clarification or confirmation.
- When the user does not specify Slurm resources, read
  `compatibility.execution_defaults.slurm_resource_hints` from the target
  workflow's registry entry and use those values as the starting-point
  `resource_request`; surface them to the user before freezing so they can
  adjust.  Queue and account are never in the hints and must always come from
  the user.
- Prefer explicit resource choices over registry hints when the user asks for
  specific CPUs, memory, walltime, or partitioning.
