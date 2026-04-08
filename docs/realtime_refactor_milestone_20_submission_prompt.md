Use this prompt when handing the Milestone 20 durable asset return slice off
to another Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-20-storage-native-durable-asset-return.md
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

- The repo already produces deterministic local result bundles and manifests.
- The next step is to make workflow outputs durable and reusable as asset
  references without becoming a database-first platform.
- Keep the first version filesystem-backed and manifest-driven.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-20-storage-native-durable-asset-return.md`.
2. Investigate the current implementation state in `resolver.py`,
   `spec_executor.py`, `spec_artifacts.py`, `types/assets.py`, and the
   relevant tests.
3. Define a durable asset reference model for outputs.
4. Update manifests to carry durable references where appropriate while
   preserving path-based compatibility.
5. Make outputs reloadable after the local run directory is gone.
6. Add tests for asset lookup, replay, and downstream reuse.
7. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
9. Stop when blocked, when a compatibility guardrail would be at risk, or
   when the next step would require a larger risky batch that should be split.

Important constraints:

- Stay manifest-driven and filesystem-backed in the first version.
- Do not break current result-bundle replay.
- Do not introduce a database-first architecture.
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
