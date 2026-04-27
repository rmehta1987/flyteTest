# Loop driver — critique follow-up milestone

This is the prompt fed to `/loop` to walk the
`docs/2026-04-25-critique-followup/` milestone end-to-end. Self-paced (no
interval); the model decides when to schedule its next wake-up via
`ScheduleWakeup`.

---

You are executing the `2026-04-25-critique-followup` milestone in the
flyteTest repo on branch `critique`. Source review:
`/home/rmeht/Projects/flyteTest/CRITIQUE_REPORT.md`. Plan:
`/home/rmeht/Projects/flyteTest/docs/2026-04-25-critique-followup/critique-followup_plan.md`.
Step prompts:
`/home/rmeht/Projects/flyteTest/docs/2026-04-25-critique-followup/prompts/step_01..06_*.md`.

## Loop contract

Each iteration:

1. **Read the checklist**:
   `/home/rmeht/Projects/flyteTest/docs/2026-04-25-critique-followup/checklist.md`.
   Find the **first unchecked** primary item. If everything is checked, stop
   the loop (do not call `ScheduleWakeup`) and post a one-line summary.
2. **Open the corresponding step prompt** under `prompts/step_NN_*.md`. Treat
   it as your full brief for this iteration.
3. **Execute exactly that step.** Do not bundle multiple steps. Do not work
   ahead. Do not refactor anything not named in the step's "Files to touch"
   section.
4. **Validate.** After every code-touching step, run
   `PYTHONPATH=src python3 -m pytest tests/ -q`. All tests must pass before
   you commit. (Memory pointer: `feedback_venv_invocation.md` — set
   `PYTHONPATH=src`; no editable install.) For docs-only steps, spot-check
   rendering of the touched markdown.
5. **Commit atomically.** One commit per step (step 04 has three sub-steps,
   each its own commit). Subject line per the step prompt's "Commit:" line.
   Do not stage unrelated files. Do not stage the untracked
   `docs/showcase_flyte_plain_language.md`.
6. **Update the checklist.** Tick the item you just finished
   (`[ ]` → `[x]`). Stage and amend it into the same commit, or commit
   separately as `critique-followup: tick step NN in checklist`.
7. **Schedule next wake-up via `ScheduleWakeup`** with `delaySeconds` between
   `60` (steps that left tests running in background) and `1800` (idle
   pacing). Pass this entire prompt back via the `prompt` field so the next
   firing repeats the loop contract. **Set `reason` to a one-sentence
   description of what just happened and what you're waiting for.** If the
   step you just finished was step 01 (decision-only, no code), include
   "blocked on user decision" in the reason and **do not** call
   `ScheduleWakeup` — let the user resume the loop manually.

## Hard stops (do not loop past these)

- **Step 01 result** is decision-only. If you finish step 01 without a clear
  decision recorded in the checklist or as a comment in
  `critique-followup_plan.md`, stop the loop and ask the user.
- **Any test failure** that isn't directly caused by the step's own changes:
  stop, post the failure, do not commit, do not schedule next wake-up.
- **Any divergence between two `ReferenceGenome` definitions in step 03**:
  per the step prompt, stop and report rather than silently align fields.
- **Any file under `src/flytetest/tasks/`, `src/flytetest/workflows/`, or the
  Slurm submission paths in `src/flytetest/spec_executor.py`** appearing in
  your diff: stop. You've left scope.

## Hard constraints (per `AGENTS.md`)

- Do not modify frozen saved artifacts at retry or replay time.
- Do not submit a Slurm job (you have no reason to in this milestone).
- Do not change `classify_slurm_failure()` semantics.
- Do not silently rewrite the existing baseline; only change what the step
  explicitly says to change.
- Never use `--no-verify`, `--amend` on already-published commits, or
  destructive git ops without explicit user authorization.
- Do not push to origin. The user will push when the milestone is done or at
  a checkpoint of their choosing. (If you've been explicitly told elsewhere
  in the session to push, follow that — but the default is local only.)

## When you're done

After step 06's checklist item is ticked, post a final summary:

- Number of commits made this run.
- Tests passing? (final pytest summary line.)
- Any items in the checklist's "Secondary" section that became trivially
  doable along the way and were also closed.
- Any items in the checklist's "Open questions" section that you resolved.

Then stop. Do not call `ScheduleWakeup`. Do not open a PR. Do not push.
