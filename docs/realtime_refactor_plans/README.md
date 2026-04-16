# Realtime Refactor Plans

This directory tracks the evolving implementation plans created while the
`realtime` architecture refactor is in progress.

The checklist in `docs/realtime_refactor_checklist.md` is the canonical status
tracker.
This directory is the plan-history workspace that records how individual
critical-path slices or parallel lanes were scoped over time.

This directory is not the canonical statement of what is currently implemented.
For current status, read `docs/realtime_refactor_checklist.md` first, then use
archived plans only as historical implementation context.

Use this plan workspace when:

- a session creates a detailed implementation plan for one refactor slice
- a plan is revised materially after new repo discoveries
- a large milestone is broken into smaller executable subplans
- a parallel lane needs its own concrete execution plan

## How To Use This Directory

- Keep active plan documents in this directory.
- Move superseded or completed plans into `archive/`.
- Do not list archived plans as default required context for new milestone work
  unless the milestone explicitly depends on prior decisions recorded there.
- Prefer one markdown file per meaningful slice or plan revision.
- Keep filenames short, sortable, and descriptive.

Suggested filename pattern:

- `YYYY-MM-DD-<slice-name>.md`

Examples:

- `2026-04-06-resolver-contract.md`
- `2026-04-07-registry-compatibility-graph.md`
- `2026-04-08-mcp-migration-lane.md`

## What Each Plan Should Contain

Each plan should include:

- title
- date
- related checklist milestone or lane
- current state
- target state
- implementation steps
- validation steps
- blockers or assumptions

Keep the plan implementation-focused.
Do not use this directory as a substitute for updating the main checklist.

For coding agents:

- do not restart work from an archived plan without checking the current code
  and checklist state
- treat completed plans as rationale and handoff context, not as open tasks
- if a new dynamic workflow capability is planned here, describe whether it is
  a registered-stage composition, a saved `WorkflowSpec`, or future behavior

## Relationship To Other Docs

- `docs/realtime_refactor_checklist.md`
  Canonical progress tracker and completion gate.
- `docs/realtime_refactor_submission_prompt.md`
  Tells future sessions to continue through checklist items and keep plan
  history up to date.
- `DESIGN.md`
  Architecture source of truth.
