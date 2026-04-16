# Milestone 19 Caching and Resumability

Date: 2026-04-08
Status: Originally proposed as one slice; now tracked as phased implementation

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 19

Implementation note:
- This slice should let interrupted work continue from frozen recipes and
  explicit run records without recomputing already completed stages.
- It should stay explicit and inspectable, not hidden behind mutable local
  process state.
- Cache and resume rules should be compatible with both local saved-spec
  execution and the Slurm path established earlier.
- This milestone follows Milestone 15 rather than preceding it. Milestone 15
  opens the composition preview and approval boundary first; Milestone 19 then
  adds the caching and resumability required before execution-capable composed
  DAGs can be exposed safely.

## Phased Milestone 19 Breakdown

Milestone 19 is now executed as phased slices rather than one large batch.
Core resumability phases follow an ordered path, while async monitoring is a
separate follow-on lane:

1. Core Phase A: durable local run records and baseline cache identity framing.
   Primary references:
   - `docs/realtime_refactor_plans/2026-04-12-milestone-19-phase-a-audit.md`
2. Core Phase B: local resume semantics from prior durable local run records.
   Primary references:
  - `docs/realtime_refactor_plans/archive/realtime_refactor_milestone_19_submission_prompt.md`
3. Core Phase C: Slurm parity for resume plus explicit composed-recipe approval
   acceptance before execution.
   Primary references:
  - `docs/realtime_refactor_plans/archive/realtime_refactor_milestone_19_phase_c_submission_prompt.md`
4. Milestone 19 Part B (follow-on lane): asynchronous Slurm monitoring loop and
   non-blocking state reconciliation.
   Primary references:
   - `docs/realtime_refactor_plans/2026-04-10-milestone-19-part-b-async-slurm-monitoring.md`
   - `docs/realtime_refactor_milestone_19_part_b_submission_prompt.md`
5. Phase D: deterministic cache-key normalization and versioned invalidation
   hardening.
   Primary references:
  - `docs/realtime_refactor_plans/archive/realtime_refactor_milestone_19_phase_d_submission_prompt.md`

### Core Phase A

Scope:
- Introduce durable local run records with schema validation, atomic save/load,
  per-node completion state, and explicit assumptions/limitations metadata.

Dependency note:
- This is the base layer for all later resume behavior.

### Core Phase B

Scope:
- Add local resume semantics based only on frozen recipe identity and prior
  `LocalRunRecord` data; skip completed nodes and rerun only incomplete or
  invalidated nodes.

Dependency note:
- Requires Core Phase A to be in place first.

### Core Phase C

Scope:
- Align Slurm resumability with local resumability boundaries.
- Add explicit composed-recipe approval acceptance before execution-capable
  composed DAG runs.

Dependency note:
- Requires Core Phase B to be complete before landing fully.

### Milestone 19 Part B (Async Monitoring Follow-On)

Scope:
- Move Slurm polling and reconciliation into a background async loop.
- Preserve run-record durability with locking while avoiding synchronous MCP
  request blocking.

Dependency note:
- Separate lane from core cache/reuse semantics; can be delivered as follow-on
  work while keeping resumability behavior explicit and stable.

### Phase D

Scope:
- Compute deterministic cache identity keys from frozen workflow/binding/input
  state.
- Add versioned invalidation controls so handler/schema evolution does not
  silently reuse stale results.

Dependency note:
- Final cache-identity hardening layer after resumability behavior is already
  explicit.

## Current State

- The repo already has frozen `WorkflowSpec` and `BindingPlan` artifacts plus
  durable local result bundles.
- Milestones 13, 16, and 18 are expected to establish Slurm submission,
  lifecycle reconciliation, and retry semantics.
- There is not yet an explicit cache-key or resumability model for stage
  completion.

Milestone 19 planning now spans multiple handoff documents, and this file acts
as the canonical phase map for the overall milestone narrative. The checklist
remains the canonical status source:

- `docs/realtime_refactor_checklist.md`

## Target State

- Cache keys are derived from the frozen `WorkflowSpec`, resolved inputs, and
  relevant runtime bindings or execution profile data.
- Stage completion state is persisted in run records.
- Resuming a run reuses completed stages and only reruns missing or invalidated
  work.
- Cache hits and misses are visible and testable rather than implicit.
- Local saved-spec execution and Slurm-backed execution can both honor the
  same replayable resume rules.
- Once this lands, execution-capable composed DAGs can be exposed safely for
  the Milestone 15 composition path.

## Scope

In scope:

- Define cache keys for frozen specs and resolved inputs.
- Persist stage completion state in durable run records.
- Implement resume behavior for interrupted runs.
- Re-execute only missing or invalidated stages.
- Add tests for cache hits, cache misses, and interrupted-run recovery.

Out of scope:

- Database-backed cache state.
- Non-Slurm remote orchestration.
- Hidden implicit retries without a frozen recipe.
- Any change that breaks replay of existing manifests.

## Implementation Steps

1. Core Phase A: land durable local run-record modeling, schema/version checks,
  atomic persistence helpers, and phase-A baseline tests.
2. Core Phase B: land local resume semantics (`resume_from` record loading,
  identity validation, explicit node skip/rerun reasoning, and resume tests).
3. Core Phase C: align Slurm resume behavior with local record semantics and
  add explicit composed-recipe approval acceptance before execution.
4. Milestone 19 Part B: land async Slurm monitoring as a bounded follow-on
  observability lane without changing core cache/reuse semantics.
5. Phase D: harden deterministic cache-key normalization plus versioned
  invalidation rules; enforce key-mismatch rejection in resume guards.
6. Keep docs/checklist/changelog aligned after each phase lands rather than at
  the end of the entire milestone.

### Phase References

The phase handoff prompts now live under `docs/realtime_refactor_plans/archive/`
because Milestone 19 is complete. Treat them as historical context rather than
as active implementation prompts.

- Core Phase A audit and implementation framing:
  - `docs/realtime_refactor_plans/2026-04-12-milestone-19-phase-a-audit.md`
- Core Phase B handoff prompt:
  - `docs/realtime_refactor_plans/archive/realtime_refactor_milestone_19_submission_prompt.md`
- Core Phase C handoff prompt:
  - `docs/realtime_refactor_plans/archive/realtime_refactor_milestone_19_phase_c_submission_prompt.md`
- Milestone 19 Part B plan and handoff prompt:
  - `docs/realtime_refactor_plans/2026-04-10-milestone-19-part-b-async-slurm-monitoring.md`
  - `docs/realtime_refactor_milestone_19_part_b_submission_prompt.md`
- Phase D handoff prompt:
  - `docs/realtime_refactor_plans/archive/realtime_refactor_milestone_19_phase_d_submission_prompt.md`

## Validation Steps

- Run `python3 -m py_compile` on touched Python files if code changes land.
- Run focused tests:
  - `python3 -m unittest tests.test_spec_executor`
  - `python3 -m unittest tests.test_server`
  - `python3 -m unittest tests.test_specs`
- Run `git diff --check`.
- Expand coverage if the caching work touches shared planner or run-record
  contracts.

## Blockers or Assumptions

- This milestone assumes the run record can store enough stage-completion
  detail to make resume deterministic.
- It assumes cache reuse must be explicit and reproducible, not heuristic.
- If the frozen recipe or resolved inputs differ, the system should treat the
  run as a cache miss rather than guessing.

Phase-level sequencing assumption:

- Core resumability work should follow A -> B -> C, while async monitoring
  remains a separate operational lane and cache-key hardening closes in
  Phase D.
