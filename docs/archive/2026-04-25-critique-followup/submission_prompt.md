# Submission prompt — critique follow-up

You are picking up the `2026-04-25-critique-followup` milestone in the
flyteTest repo. The full review that motivated this milestone lives at
`CRITIQUE_REPORT.md` (repo root). The plan is at
`docs/2026-04-25-critique-followup/critique-followup_plan.md`. The bullet
list of work is at `docs/2026-04-25-critique-followup/checklist.md`.

## Read first

1. `CRITIQUE_REPORT.md` end-to-end. The findings cite `path:line`; trust
   them but verify before deleting.
2. `AGENTS.md` — hard constraints (frozen artifacts, Slurm submission rules,
   `classify_slurm_failure` semantics, baseline preservation). None of the
   work in this milestone should touch them; if you find yourself wanting
   to, stop and report.
3. The plan and checklist in this folder.

## Order of operations

Execute steps **01 → 06** in order using the prompts under `prompts/`.
Each prompt is self-contained: it names the files to touch and the
acceptance criteria. Step 02 depends on the decision made in step 01;
the rest can be done in any order, but the sequence above keeps commits
small and readable.

## Commit hygiene

- One logical change per commit. Atomic commits per `AGENTS.md`.
- Never bundle unrelated changes (e.g., don't combine a docstring strip
  with a `ReferenceGenome` dedupe).
- Subject lines: `critique-followup: <short>` for milestone commits.

## Validation per step

- After every code-touching step: `PYTHONPATH=src python3 -m pytest tests/ -q`.
  All 887 tests must pass. (Memory pointer:
  `feedback_venv_invocation.md` — set PYTHONPATH=src; no editable install.)
- After docs-only steps: spot-check rendering of the touched markdown.

## When to stop and ask

- If step 01's decision is unclear from telemetry or recall, stop and ask
  the maintainer rather than guessing.
- If a step's diff would touch any file under `src/flytetest/tasks/`,
  `src/flytetest/workflows/`, or `src/flytetest/spec_executor.py`'s Slurm
  paths, stop — you've gone outside scope.

## Done when

The acceptance criteria in `critique-followup_plan.md` §Acceptance hold,
the checklist's primary section is fully checked, and `CHANGELOG.md` has
a dated entry summarizing the milestone.
