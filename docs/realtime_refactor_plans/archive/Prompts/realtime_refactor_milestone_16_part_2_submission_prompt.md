Historical note: Milestone 16 Part 2 landed on 2026-04-09 with explicit
authenticated-environment diagnostics for `run_slurm_recipe`,
`monitor_slurm_job`, and `cancel_slurm_job`, plus docs that describe the
supported Slurm topology as a local MCP/server process running inside an
already-authenticated scheduler-capable environment.

Use this prompt only when reviewing or repairing the Milestone 16 Part 2
authenticated-access slice. For new work, start from the next unchecked item in
`docs/realtime_refactor_checklist.md`.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-09-milestone-16-part-2-authenticated-slurm-access-boundary.md
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

- Milestone 13 should already have introduced deterministic `sbatch`
  submission and durable Slurm run records.
- Milestone 16 should already have introduced run-record reconciliation through
  `squeue`, `scontrol show job`, and `sacct`, plus cancellation through
  `scancel`.
- The target HPC environment requires SSH plus 2FA and does not permit shared
  keys or unattended SSH pairing for user jobs.
- The default design direction is that the MCP server runs as a local process
  inside an already-authenticated HPC session and uses local Slurm CLI
  subprocess calls.
- The next step is to make that authenticated-access boundary explicit in the
  executor, MCP surface, durable run-record model, and docs.
- You may inspect `/home/rmeht/Projects/flytekitplugins_slurm-1.16.16` as
  comparative context, but do not assume its unattended SSH model is valid for
  this repo's default path.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-09-milestone-16-part-2-authenticated-slurm-access-boundary.md`.
2. Investigate the current implementation state in `spec_executor.py`,
   `server.py`, `mcp_contract.py`, `README.md`, `DESIGN.md`,
   `docs/mcp_showcase.md`, and the relevant tests.
3. Audit the current Slurm lifecycle path for hidden assumptions about where
   `sbatch`, `squeue`, `scontrol`, `sacct`, and `scancel` are expected to run.
4. Define the smallest supported execution topology for sites that require an
   already-authenticated SSH plus 2FA session.
5. Treat the default runtime model as a local MCP server process running in a
   login-node shell, `tmux` or `screen` session, or another already-authenticated
   environment. Treat a lightweight persistent interactive allocation as an
   optional site-specific variation rather than the default assumption.
6. Decide how Slurm capabilities should be advertised when the MCP server is
   started outside a scheduler-capable environment. Prefer a small environment
   check for `sbatch`, `squeue`, `scontrol`, `sacct`, and `scancel`, then
   either hide Slurm tools or return explicit unsupported-environment
   limitations.
7. Tighten lifecycle behavior so unsupported execution contexts are reported
   explicitly instead of looking like generic scheduler failures.
8. Add minimal run-record or lifecycle metadata if needed to preserve
   submission or reconciliation context across restarts and later checks.
9. Add focused tests for unavailable scheduler commands, inaccessible execution
   context, capability gating, or related lifecycle diagnostics if code changes
   land.
10. Document live HPC integration testing as a manual layer that runs only
    after the user authenticates with SSH plus 2FA and starts the MCP server in
    that HPC session.
11. Update docs and the checklist only as needed so the supported boundary is
   honest, reviewable, and aligned with the milestone plan.
12. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
13. Stop when blocked, when a compatibility guardrail would be at risk, or
    when the next step would require a larger risky batch that should be split.

Important constraints:

- Do not automate SSH 2FA or assume reusable shared keys are allowed.
- Treat the durable filesystem run record as the source of truth across time.
- Treat live scheduler commands as valid only when FLyteTest is running from an
  already-authenticated environment or another explicitly approved site
  interface.
- Do not assume a continuously running polling loop is required; on-demand
  reconciliation from durable run records is still a valid lifecycle model.
- Be careful with transport assumptions: `stdio` works naturally only when the
  client and server are co-located, and any remote transport must be explicit.
- Do not broaden the repo into generic remote orchestration.
- Keep README, DESIGN, checklist docs, MCP contract, lifecycle docs, and tests
  aligned.

Report back with:

- checklist item(s) completed
- files changed
- validation run
- current checklist status
- new or archived plan documents created
- remaining blockers or assumptions
```
