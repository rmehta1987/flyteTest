Historical note: Milestone 13 landed on 2026-04-08 with
`SlurmWorkflowSpecExecutor`, `run_slurm_recipe`, deterministic `sbatch` script
rendering, and filesystem-backed run records under `.runtime/runs/`.

Use this prompt only when reviewing or repairing the Milestone 13 Slurm
executor slice. For new work, start from the next unchecked milestone in
`docs/realtime_refactor_checklist.md`.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-13-slurm-executor-engine.md
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

- Milestone 12 should already have made resource requests and execution
  profiles explicit in saved recipes.
- `src/flytetest/specs.py` already defines `ResourceSpec`,
  `RuntimeImageSpec`, and `ExecutionProfile`.
- The next step is to add a Slurm executor engine that consumes frozen recipes
  instead of reinterpreting prompt text.
- The current MCP recipe surface is local-first and handler-based; keep that
  path intact while adding the Slurm path.
- Do not introduce scheduler monitoring or cancellation in this slice unless
  the milestone scope is intentionally expanded.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-13-slurm-executor-engine.md`.
2. Investigate the current implementation state in `specs.py`, `spec_artifacts.py`,
   `spec_executor.py`, `server.py`, `mcp_contract.py`, `registry.py`, and the
   relevant tests.
3. Add `SlurmWorkflowSpecExecutor` as a sibling to `LocalWorkflowSpecExecutor`.
4. Render a deterministic Slurm script from the frozen `WorkflowSpec`, resolved
   bindings, and explicit `ExecutionProfile`.
5. Submit the rendered script with
   `subprocess.run(["sbatch", script_path], capture_output=True, text=True, check=True)`
   or an equivalent explicit wrapper that preserves the same behavior.
6. Parse and persist the emitted Slurm job ID into a run-scoped filesystem
   record alongside the script path, stdout / stderr paths, and selected
   execution profile.
7. Expose `run_slurm_recipe` as an MCP tool and preserve the existing local
   recipe execution path.
8. Add tests for script determinism, `sbatch` parsing, run-record persistence,
   and MCP wiring.
9. Update docs and the checklist so the new state is honest, reviewable, and
   aligned with the milestone plan.
10. If you materially revise the detailed milestone plan, save the revision
    under `docs/realtime_refactor_plans/` and archive superseded versions under
    `docs/realtime_refactor_plans/archive/`.
11. Stop when blocked, when a compatibility guardrail would be at risk, or
    when the next step would require a larger risky batch that should be split.

Important constraints:

- Treat the filesystem record as the durable source of truth for Slurm runs.
- Do not key run state only by recipe spec ID.
- Keep current runnable targets, manifest contracts, and recipe-backed local
  behavior intact.
- Do not add monitoring or cancellation unless you are explicitly expanding
  the milestone scope.
- Do not overwrite unrelated user changes in a dirty worktree.
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
