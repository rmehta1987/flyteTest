Use this prompt when handing the Milestone 15 registry-driven dynamic
composition slice off to another Codex session or when starting the next
implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-15-registry-driven-dynamic-composition.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/tasks.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md

If you were assigned a specialist role, also read the matching guide under
`.codex/agent/`.

Context:

- The registry already carries compatibility metadata that can describe stage
  inputs, outputs, execution defaults, and composition constraints.
- Milestone 15 should let the planner compose workflows from biological intent
  only within registry-approved paths.
- Treat this as bounded, reviewable dynamic composition, not autonomous graph
  search.
- Milestone 15 is composition and approval only; execution-capable composed
  DAGs stay gated on Milestone 19 caching and resumability.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-15-registry-driven-dynamic-composition.md`.
2. Investigate the current implementation state in `planning.py`, `registry.py`,
   `specs.py`, `spec_artifacts.py`, `server.py`, and the relevant tests.
3. Add an intent-based planning route that can produce either a supported
   `WorkflowSpec` preview or a structured decline.
4. Implement registry-constrained graph traversal using
   `RegistryEntry.compatibility` so only biologically valid edges are
   considered.
5. Bundle sequential task nodes into a frozen, reviewable multi-node
   `WorkflowSpec`.
6. Enforce cycle detection, maximum-depth limits, and structured decline
   reasons for unsupported or ambiguous compositions.
7. Require explicit user approval for the composed recipe preview and keep
   execution gated until Milestone 19 lands.
8. Add tests for bounded composition, decline behavior, and approval gating.
9. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
10. If you materially revise the detailed milestone plan, save the revision
    under `docs/realtime_refactor_plans/` and archive superseded versions under
    `docs/realtime_refactor_plans/archive/`.
11. Stop when blocked, when a compatibility guardrail would be at risk, or
    when the next step would require a larger risky batch that should be split.

Important constraints:

- Keep the planner typed, bounded, and reviewable.
- Do not implement open-ended autonomous graph search.
- Do not execute composed plans before explicit user approval.
- Do not bypass the frozen recipe boundary.
- Keep README, DESIGN, checklist docs, registry metadata, planner behavior,
  MCP contract, and tests aligned.

Report back with:

- checklist item(s) completed
- files changed
- validation run
- current checklist status
- new or archived plan documents created
- remaining blockers or assumptions
```
