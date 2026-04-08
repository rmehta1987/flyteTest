Use this prompt when handing the sequential Milestones 13 through 20 tranche
off to another Codex session or when starting a longer implementation pass that
should continue across several small, dependency-aware slices.

Progress note as of 2026-04-08: Milestones 13, 14, and 16 have landed. Future
sessions should read the checklist first and start from the next unchecked
milestone rather than redoing the Slurm submission, generic asset
compatibility, or Slurm lifecycle slices.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
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

- Milestones 13, 16, 18, and 19 build the Slurm submission, lifecycle,
  retry, and resumability path over frozen run records.
- Milestones 14 and 17 move the biology-facing asset model toward generic,
  replay-safe names without breaking historical manifests.
- Milestone 15 is composition and approval only; execution-capable composed
  DAGs stay gated on Milestone 19 caching and resumability.
- Milestone 20 introduces durable asset references without turning the project
  into a database-first architecture.
- Work through the tranche in a dependency-aware sequence and keep each slice
  small enough to review and validate.

Task:

1. Read `docs/realtime_refactor_checklist.md` and the detailed plan docs for
   Milestones 13 through 20.
2. Work through the milestones in this sequence:
   - Milestone 13: deterministic Slurm submission with durable run records
   - Milestone 14: generic asset compatibility and legacy alias support
   - Milestone 16: Slurm job lifecycle reconciliation and cancellation
   - Milestone 18: Slurm retry and resubmission policy
   - Milestone 19: caching and resumability for frozen recipes
   - Milestone 15: registry-driven dynamic composition preview and approval
     only, with execution still gated on Milestone 19
   - Milestone 17: generic asset adoption across planner adapters and workflow
     outputs
   - Milestone 20: storage-native durable asset return
3. For each milestone, investigate the current implementation state in the
   code, docs, registry, planner, MCP server, and tests that the milestone
   touches.
4. Make only the changes needed to satisfy the current milestone while
   preserving the documented compatibility guardrails.
5. Update documentation and tests so the new state is honest, reviewable, and
   aligned with the milestone plan and capability snapshot.
6. Mark the completed checklist item(s) in
   `docs/realtime_refactor_checklist.md`.
7. If you materially revise a detailed milestone plan, save the revision under
   `docs/realtime_refactor_plans/` and archive superseded or completed
   revisions under `docs/realtime_refactor_plans/archive/`.
8. If a milestone is fully complete and the next one is unblocked, continue to
   the next milestone in the same session.
9. Stop when one of the following occurs:
   - the next milestone is blocked by a missing decision, missing dependency,
     or environment limitation
   - the next milestone would require a larger risky jump that should be split
     into a fresh slice
   - a compatibility guardrail would be at risk
   - the Milestones 13 through 20 tranche is complete
10. Use a stop-and-review circuit breaker after each milestone:
   - finish the current milestone only
   - validate the change before moving on
   - report back with a concise summary and wait for the user to continue if
     the next milestone is not trivially safe
   - do not autonomously barrel through multiple milestones in one burst unless
     the current milestone and the next one are both clearly small, tightly
     related, and already unblocked
11. Report back with:
   - checklist item(s) completed
   - files changed
   - validation run
   - current checklist status
   - any new or archived plan documents created
   - remaining blockers or assumptions

Important constraints:

- Keep the Slurm path explicit and filesystem-backed; do not broaden into
  generic remote orchestration.
- Keep Milestone 15 as a bounded composition preview unless and until the
  Milestone 19 resumability work is in place.
- Keep historical manifest replay truthful while generic asset names and
  durable references are introduced.
- Prefer incremental refactors around compatibility seams instead of rewrites.
- Keep README, DESIGN, checklist docs, registry metadata, planner behavior,
  MCP contract, and tests aligned.
```
