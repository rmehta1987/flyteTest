# Codex Review of `mcp_reshape_plan.md`

This document is a section-by-section architecture review of
`docs/mcp_reshape/mcp_reshape_plan.md`.

It is not a replacement for the master plan. It is a companion note that says
which parts I approve, which parts I approve with caveats, and which parts I
do not think are ready to implement as written.

The goal is to preserve the plan's strong direction while making the risky
parts explicit before later steps reach the server, planner, and Slurm
execution paths.

Some additive steps from the master plan have already landed on this branch,
but the assessments below critique the plan text itself, not just the current
implementation state.

## Overall Stance

Assessment: `Approve with targeted revisions`

- The plan is directionally strong. It is scientist-centered, registry-first,
  and correctly anchored on frozen recipes, typed contracts, and offline-HPC
  reality.
- The additive foundation steps are good and can proceed independently.
- The main unresolved design gaps are concentrated in a few sections, not the
  whole document.

## Highest-Priority Revisions Before the Later Server/Planner Steps

These are the sections I would tighten before implementing the planner-heavy
and execute-path steps:

1. `§5 Remove prose heuristics from planning.py`
   The plan deletes the current free-text machinery without fully specifying
   the deterministic replacement for target matching and ambiguity handling.
2. `§7 Binding-value grammar and cross-run output reuse`
   The plan needs an explicit type-compatibility check between the requested
   planner type and the resolved prior-run output.
3. `§8 Preflight offline-compute staging validation`
   The plan needs a precise reply/status contract for pre-submit staging
   failures on real `run_task` / `run_workflow` calls.
4. `§13 Seed-bundle tool-DB reality check`
   This section still refers to import-time bundle validation even though `§4`
   already rejects that design.
5. `§3j plan_request asymmetric freeze`
   The no-freeze single-entry path needs an explicit statement about the
   re-resolution window between preview and execution.

## Context

### Why this change is happening

Assessment: `Approve`

- The problem statement matches the current repo reality.
- The scientist-facing framing is strong and grounded in `DESIGN.md` rather
  than generic UX language.
- The critique of the current heuristic-heavy MCP surface is fair.

### The four pillars this plan preserves

Assessment: `Approve`

- These are the right invariants to optimize for.
- They are useful as acceptance criteria, not just narrative framing.
- Nothing in this section feels inflated or disconnected from the actual repo.

### Two ideas borrowed from `../stargazer/`

Assessment: `Approve with critique`

- The task-vs-workflow split is a good mental model for scientists.
- Bundles are a good convenience layer when treated as explicit starter kits.
- The caution here is to keep bundles as convenience, not as a second hidden
  planning system.

### Family extensibility is load-bearing

Assessment: `Approve with critique`

- The registry-driven extension story is one of the plan's strongest parts.
- The section is honest about the remaining `TASK_PARAMETERS` coupling, which
  is good.
- The only caveat is that the "no MCP-layer edits" claim remains conditionally
  true until the task-parameter follow-up actually lands.

### What already exists (do not reimplement)

Assessment: `Approve`

- This is an effective anti-scope-creep section.
- It correctly points future implementers toward reuse instead of duplication.

### Outcome

Assessment: `Approve`

- This is a good target-state description of the intended scientist loop.
- It reads like a target experience, not a false claim that the repo already
  behaves this way.

### Backward compatibility — intentional coordinated migration

Assessment: `Approve with critique`

- The hard-break framing is honest and appropriate.
- The plan is right not to promise a shim if the migration is coordinated.
- The caveat is executional: tests, docs, and examples are part of the change,
  not just cleanup after the change.

## Changes (with concrete code)

Assessment: `Approve as an organizing section`

- The change list is concrete enough to guide implementation.
- The section is valuable because it splits the reshape into smaller pieces.

### 1. Widen the MCP `list_entries` tool

Assessment: `Approve`

- This is low-risk and additive.
- The widened payload improves discoverability without changing execution
  semantics.
- The `pipeline_family` filter is a good scientist-facing browse affordance.

### 2. Reshape `run_task` in place (`server.py:995`)

Assessment: `Approve with critique`

- The freeze-first, typed-binding shape fits the repo's architecture well.
- The main concern is `_scalar_params_for_task`: it works as a near-term bridge
  but still depends on current `TASK_PARAMETERS` names lining up with typed
  binding field names.
- I would keep this section, but link it more explicitly to the known coupling
  so implementers do not mistake it for a fully general solution.

### 3. Reshape `run_workflow` in place (`server.py:869`) — symmetric with `run_task`

Assessment: `Approve`

- Symmetry between `run_task` and `run_workflow` is the right choice.
- It avoids an unnecessary mental split between task calls and workflow calls.
- This is one of the cleaner sections of the plan.

### 3b. Stable named outputs (replace positional `output_paths`)

Assessment: `Approve with critique`

- The direction is correct: named outputs are a clear improvement over
  positional lists.
- Treating the registry as the public contract is also the right choice.
- The caution is implementation scale: the initial registry-manifest alignment
  is a large manual sweep and should be treated as real work, not a small
  mechanical touch-up.

### 3c. Expanded `execution_defaults` — environment as a first-class registry concern

Assessment: `Approve with critique`

- Keeping environment defaults on the registry is better than introducing a
  parallel environment catalog.
- The documented resolution order is sensible.
- I would strengthen this section by adding one canonical merge algorithm so
  implementers do not each infer slightly different precedence rules.

### 3d. Typed reply dataclasses — one source of truth for the MCP wire format

Assessment: `Approve`

- Centralizing reply shapes is a good additive step.
- It reduces drift across `run_*`, `plan_request`, and validation flows.
- The one improvement I would make to the plan text is consolidation: `§3g`,
  `§3i`, and `§3j` all add fields later, so the final dataclass shapes should
  be restated once in a single canonical block.

### 3e. Operator-side logging — minimal, error-path only

Assessment: `Approve`

- The narrow scope is appropriate for this repo.
- Error-path logging is enough to support operators without inventing a full
  observability stack.
- I agree with not expanding this into happy-path event logging.

### 3f. `list_available_bindings` — additive `typed_bindings` field

Assessment: `Approve`

- This is a good bridge from current discovery behavior to the new binding
  model.
- The type-annotation-driven field discovery is also a good choice.
- No major objections here.

### 3g. Error surfacing — typed exceptions + exception-to-decline translation

Assessment: `Approve with critique`

- The handling buckets are well-chosen.
- The distinction between MCP-layer failure and task-side execution failure is
  particularly important and correct.
- The only caution is compositional: make sure this wrapper complements the
  later decline-routing helpers rather than creating two overlapping decline
  shaping systems.

### 3h. `recipe_id` format — millisecond timestamp + target name, no hash

Assessment: `Approve with critique`

- The new ID shape is more readable and more useful in logs.
- The caveat is precision vs uniqueness: a timestamp-only ID does not truly
  guarantee same-millisecond uniqueness.
- The test guidance currently leaves two incompatible expectations on the
  table. The plan should choose one explicit uniqueness story before the step
  is implemented.

### 3i. Dry-run flag — `dry_run=True` on `run_task` / `run_workflow`

Assessment: `Approve with critique`

- The preview use case is real and worth supporting.
- Returning the frozen artifact path is especially valuable.
- The missing piece is a precise mapping from current frozen artifact fields to
  `resolved_bindings` and `resolved_environment`; that should be specified
  against the actual artifact/binding shapes before implementation.

### 3j. `plan_request` asymmetric freeze — NL preview without double-work

Assessment: `Critique / needs clarification before implementation`

- The conceptual split between single-entry and composed plans is elegant.
- The problem is the single-entry no-freeze path: it creates a re-resolution
  window between preview and execution.
- If that is an accepted tradeoff, the plan should say so explicitly. If not,
  the plan needs a stronger answer than "freeze only the composed case."

### 4. New module `src/flytetest/bundles.py`

Assessment: `Approve`

- Deferring validation to runtime is the right correction.
- `list_bundles()` plus `load_bundle()` is a good explicit surface.
- I strongly agree with shipping fewer, working bundles instead of pretending
  a broken seed set is acceptable.

### 5. Remove prose heuristics from `src/flytetest/planning.py`

Assessment: `Disagree as currently specified / needs clarification before implementation`

- This is the biggest unresolved section in the entire plan.
- The plan correctly wants to remove brittle extraction logic.
- But it does not yet fully specify the deterministic replacement for
  free-text target selection, tie-breaking, ambiguity, or decline behavior.
- I would not implement this section from the current text alone.

### 6. Tool descriptions in `src/flytetest/mcp_contract.py`

Assessment: `Approve`

- This is a documentation-facing refinement and fits the proposed UX.
- The resource-handoff note is especially important for Slurm honesty.

### 7. Binding-value grammar and cross-run output reuse

Assessment: `Critique / needs clarification before implementation`

- The unified binding grammar is a strong UX idea.
- The missing requirement is typed compatibility validation: if a prior-run
  output resolves to the wrong biological kind, the plan currently does not say
  how that mismatch is detected and declined.
- I would revise this section before implementation so the type contract stays
  real, not just ergonomic.

### 8. Preflight offline-compute staging validation

Assessment: `Critique / needs clarification before implementation`

- The underlying idea is unquestionably correct.
- The unresolved piece is reply semantics for real runs: when staging fails
  before `sbatch`, is that a `PlanDecline`, a failed `RunReply`, or another
  structured reply?
- The section should also say how strictly the shared-filesystem rule is
  defined for symlinks and mount layouts.

### 9. `source_prompt` empty-warning

Assessment: `Approve`

- This is small, honest, and aligned with the provenance goal.
- No objections.

### 10. Structured decline routing with broad next-step suggestions

Assessment: `Approve`

- This is one of the better scientist-facing parts of the plan.
- The recovery channels are concrete and practical.
- A later cap on `suggested_prior_runs` may be needed, but that is a sensible
  follow-up rather than a blocker.

### 11. New `validate_run_recipe` MCP tool

Assessment: `Approve with critique`

- This is a useful power-user inspection tool and fits the frozen-recipe model.
- The caveat is implementation precision: the pseudocode should be treated as a
  behavior sketch, because the current resolver and artifact APIs will need an
  exact, repo-aligned implementation.

### 12. Call-site sweep for the BC migration

Assessment: `Approve`

- This is essential and correctly called out.
- The migration sweep is part of the milestone, not optional cleanup.

### 13. Seed-bundle tool-DB reality check

Assessment: `Disagree as written`

- This section still talks about `_validate_bundles()` firing at import and the
  server failing to boot on missing bundle paths.
- That directly contradicts `§4`, which already makes the correct decision to
  remove import-time bundle hard-fail behavior.
- Keep the recommendation to ship fewer, working bundles, but rewrite this
  section so it matches the corrected runtime-validation design.

### 14. Documentation and coding-agent context refresh

Assessment: `Approve`

- This is necessary and correctly scoped.
- The only improvement I would suggest is sequencing: separate docs that must
  update in the same PR from agent-context refreshes that can follow
  immediately after if needed.

### 15. Docstrings to update

Assessment: `Approve`

- Good and necessary.
- No major objections.

### 16. Testing patterns (beyond per-commit test bullets)

Assessment: `Approve with critique`

- This is a very strong testing section.
- The caution is operational: it reads more like a test strategy document than
  a single milestone gate.
- I would keep the content but use it as per-slice guidance, not as an
  all-at-once expectation for every PR in the series.

## Extensibility: Adding a New Pipeline Family (GATK walkthrough)

Assessment: `Approve with critique`

- This is one of the strongest sections in the document.
- The worked example makes the extensibility claim concrete.
- The caveat is the same as earlier: for tasks, the `TASK_PARAMETERS` coupling
  remains real until the follow-up lands.

## Critical Files

Assessment: `Approve`

- Good implementation map.
- Useful for sequencing and reviewer orientation.

## Reused Utilities

Assessment: `Approve`

- Good inventory.
- Helps keep the implementation grounded in current repo reality.

## Verification

Assessment: `Approve with critique`

- The verification section is thorough and mostly well-targeted.
- It is too large to function as a single undifferentiated gate for every PR.
- I would partition it into additive-step checks versus coordinated-cutover
  checks.
- A few verification items also assume unresolved design decisions are already
  settled, especially around heuristic removal, staging failure semantics, and
  single-entry `plan_request` behavior.

## Out of Scope

Assessment: `Approve with one correction`

- The scope boundaries are good and mostly disciplined.
- Keeping the `TASK_PARAMETERS` follow-up visible is important.
- After `§13` is rewritten, make sure nothing in the out-of-scope narrative
  still implies the rejected import-time bundle validation path.

## Recommended Edits to the Master Plan

If I were revising `mcp_reshape_plan.md` before the later implementation
steps, I would make these changes first:

1. Rewrite `§5` so the deterministic free-text replacement is fully specified.
2. Add typed compatibility validation to `§7` for `$ref` and `$manifest`
   binding resolution.
3. Add explicit reply semantics to `§8` for pre-submit staging failure in real
   run calls.
4. Rewrite `§13` so it matches the `§4` runtime-validation bundle design.
5. Clarify in `§3j` whether the single-entry preview re-resolution window is an
   accepted tradeoff or a problem to solve.
6. Consolidate the final dataclass shapes after `§3d`, `§3g`, `§3i`, and `§3j`
   so there is one canonical field definition per reply type.
7. Treat `§12` and the docs/tests migration work as first-class milestone work,
   not late cleanup.