# Milestone 16 Part 2 Authenticated Slurm Access Boundary

Date: 2026-04-09
Status: Complete

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 16

Implementation note:
- This follow-up should refine the Milestone 16 lifecycle boundary for HPC
  sites where Slurm access requires interactive SSH plus 2FA and does not
  permit shared keys or unattended SSH pairing.
- It should preserve the durable filesystem run-record model from Milestone 16
  while making the authenticated execution context explicit.
- It should treat a locally running MCP server inside an already-authenticated
  HPC session as the default execution model for Slurm-backed MCP operations.
- It should not broaden the project into a remote SSH agent or attempt to
  automate 2FA.

## Current State

- Milestone 13 introduced deterministic `sbatch` submission and durable Slurm
  run records.
- Milestone 16 added run-record loading, lifecycle reconciliation through
  `squeue`, `scontrol show job`, and `sacct`, plus cancellation through
  `scancel`.
- The current implementation works when those scheduler commands are available
  in the environment where FLyteTest is running, but the docs do not yet state
  clearly how that boundary behaves on HPC systems that require SSH plus 2FA.
- The repo also contains design references to the Flyte Slurm plugin and
  SSH-oriented approaches, but those assumptions are not a safe default when
  scheduler access depends on an already-authenticated user session.
- The repo does not yet state clearly that a user may need to start the MCP
  server manually inside a login-node shell, `tmux` session, `screen` session,
  or another already-authenticated environment before Slurm tools should be
  advertised.

## Landed Result

- Slurm submission now checks explicitly for `sbatch` before attempting
  submission and reports an unsupported-environment limitation when FLyteTest is
  started outside an authenticated scheduler-capable environment.
- Slurm monitoring now distinguishes missing scheduler query commands from
  ordinary lifecycle state and reports an unsupported-environment limitation
  when none of `squeue`, `scontrol`, or `sacct` are available.
- Slurm cancellation now checks for `scancel` explicitly and reports the same
  authenticated-environment boundary instead of returning only generic command
  failures.
- README, MCP showcase docs, capability notes, and MCP contract text now state
  that the default supported topology is an MCP/server process running inside an
  already-authenticated HPC session.

## Target State

- Slurm submission, monitoring, and cancellation are documented as operations
  that run only from an already-authenticated scheduler environment unless a
  site-approved machine interface is configured explicitly.
- The default supported topology is: authenticated HPC session -> local MCP
  server process -> local `sbatch` / `squeue` / `scontrol` / `sacct` /
  `scancel` subprocess calls.
- The executor and MCP layer report access limitations clearly when scheduler
  commands are unavailable because FLyteTest is running outside the
  authenticated environment.
- The durable run record remains the source of truth across time while the
  scheduler remains the source of live state.
- The lifecycle model does not depend on a continuously running polling loop;
  a restarted MCP server can reconcile durable run records later.
- Slurm-backed MCP capabilities are exposed only when the local environment can
  actually reach the required scheduler commands, or they fail with explicit
  unsupported-environment diagnostics.
- The implementation and docs do not imply support for unattended SSH login,
  stored private-key sharing, or automated 2FA handling.

## Scope

In scope:

- Define the authenticated-access model for Slurm lifecycle operations.
- Audit `spec_executor.py`, `server.py`, `mcp_contract.py`, and the Slurm docs
  for hidden assumptions about where scheduler commands run.
- Define how the MCP server should behave when started on a laptop or other
  non-HPC environment where Slurm commands are unavailable.
- Add the smallest executor or MCP diagnostics needed to distinguish:
  missing run record, command unavailability, scheduler reachability issues,
  and unauthenticated or wrong-environment execution.
- Record minimal provenance about submission or reconciliation context if that
  materially helps explain durable run-record history.
- Define the live-HPC validation boundary honestly: mocked subprocess tests stay
  local and offline-friendly, while real Slurm integration remains a manual
  authenticated test layer.
- Update docs and handoff prompts so the supported boundary is explicit.

Out of scope:

- Automating SSH 2FA challenges.
- Storing shared private keys or other unattended SSH credentials as the
  default project path.
- Replacing the current local-first executor with a generic remote orchestration
  system.
- Making `slurmrestd`, Open OnDemand, or the Flyte Slurm plugin the default
  execution path in this slice.
- Requiring a long-lived background polling daemon as the only valid lifecycle
  model.

## Implementation Steps

1. Audit `src/flytetest/spec_executor.py`, `src/flytetest/server.py`,
   `src/flytetest/mcp_contract.py`, `README.md`, `DESIGN.md`,
   `docs/mcp_showcase.md`, and `docs/capability_maturity.md` for assumptions
   about Slurm access and execution location.
2. Review the local reference copy of the Flyte Slurm plugin under
   `/home/rmeht/Projects/flytekitplugins_slurm-1.16.16` only as comparative
   context, not as the default implementation model.
3. Define the smallest supported execution topology for Milestone 16 Part 2,
   with submission and lifecycle commands running from an already-authenticated
   environment such as a login-node shell, a `tmux` or `screen` session, or an
   equivalent trusted session. Treat a persistent interactive allocation as an
   optional deployment variation, not the default assumption.
4. Decide how the MCP server should advertise Slurm capabilities when the
   process is started outside that environment. Prefer a small environment check
   for required commands such as `sbatch`, `squeue`, `scontrol`, `sacct`, and
   `scancel`, then either hide Slurm tools or return an explicit unsupported
   limitation.
5. Tighten lifecycle error reporting so failures outside that environment are
   reported explicitly rather than reading like generic scheduler bugs.
6. Add any minimal run-record fields or lifecycle metadata needed to preserve
   authenticated-context provenance across restarts and later reconciliation.
7. Add focused tests for unavailable scheduler commands, inaccessible execution
   context, capability gating, or related lifecycle diagnostics if code changes
   land.
8. Document the live-HPC validation layer as manual: the user authenticates
   with SSH plus 2FA, starts the MCP server inside the HPC session, and then
   runs any real Slurm smoke or integration checks there.
9. Update docs and handoff prompts so the authentication boundary is visible and
   honest.

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests if runtime or MCP behavior changes:
  - `python3 -m unittest tests.test_spec_executor`
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_specs`
- Run `git diff --check`.
- Re-read the touched docs to ensure they do not imply unattended SSH or 2FA
  automation support that the repo does not implement.
- If a live-HPC validation note is added, make sure it distinguishes manual
  authenticated testing from ordinary local unit or fixture-backed tests.

## Blockers or Assumptions

- Some HPC sites expose Slurm commands only after the user completes an
  interactive SSH plus 2FA login.
- Some sites do not permit reusable key-based automation for user jobs, so a
  long-running remote agent may be operationally or policy-wise inappropriate.
- Some sites may kill idle login-node processes, so users may need to keep the
  MCP server alive with `tmux`, `screen`, or a lightweight persistent
  interactive allocation.
- If the user-facing stdio connection drops while a lifecycle request is in
  flight, local Slurm subprocess work may still complete on the HPC side even
  though the current MCP response is lost. The preferred behavior is to persist
  any successfully reconciled run-record state before exiting and let a later
  restart re-reconcile from the durable record if needed.
- If FLyteTest is run outside the authenticated scheduler environment, the
  correct behavior is to preserve the durable run record and report the access
  limitation explicitly rather than guessing or silently retrying through an
  unsupported path.
- If the MCP client is not co-located with the HPC-side server process, any
  client-server transport still needs an explicitly supported path; this slice
  should not assume hidden tunneling or implicit remote connectivity.
