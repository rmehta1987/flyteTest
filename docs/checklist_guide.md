# Checklist Guide

Use this guide to decide which checklist governs a piece of work.

## Primary Rule

- Use `docs/refactor_completion_checklist.md` for notes-faithful biology and
  pipeline completion work.
- Use `docs/realtime_refactor_checklist.md` for platform and architecture
  refactor work described by `DESIGN.md`.

These checklists should stay separate because they answer different questions:

- the refactor completion checklist asks whether the implemented annotation
  pipeline matches `docs/braker3_evm_notes.md`
- the realtime checklist asks whether the platform architecture matches
  `DESIGN.md` without breaking compatibility guardrails

## Use `docs/refactor_completion_checklist.md` When

- changing task or workflow behavior for the annotation pipeline
- updating notes-backed stage contracts or output bundle shape
- validating README, registry, or manifest claims about implemented biology
- deciding whether later downstream biological stages may open

## Use `docs/realtime_refactor_checklist.md` When

- changing typed planning, saved recipe artifacts, resolver contracts, or
  replay behavior
- changing MCP execution surfaces, compatibility guardrails, or prompt-driven
  architecture behavior
- changing Slurm execution, resumability, approval-gating, or durable run
  record behavior
- creating or updating detailed plan-history docs under
  `docs/realtime_refactor_plans/`

## Update Both When

- a platform change also changes a user-visible biological contract
- a workflow or manifest change needs both notes-faithful validation and
  architecture-tracker updates
- README or compatibility language crosses both the implemented pipeline scope
  and the realtime architecture scope

In mixed cases, keep each checklist concise and update only the items that are
actually affected.

## Related Docs

- `docs/braker3_evm_notes.md`: source of truth for notes-faithful pipeline
  behavior
- `DESIGN.md`: source of truth for the `realtime` architecture target
- `docs/refactor_submission_prompt.md`: handoff prompt for the notes-faithful
  refactor path
- `docs/realtime_refactor_submission_prompt.md`: handoff prompt for the
  architecture refactor path