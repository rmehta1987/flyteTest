# Documentation Guide

This file is a repo-specific guide for FLyteTest documentation work.

## Purpose

Use this guide when updating:

- `README.md`
- `DESIGN.md`
- `AGENTS.md`
- `docs/tool_refs/*.md`
- milestone or architecture notes

## Documentation Goals

Documentation in FLyteTest should:

- describe what is actually implemented now
- distinguish clearly between implemented scope and future scope
- explain pipeline position and stage boundaries
- document assumptions honestly
- keep local, container, and HPC expectations visible
- describe deterministic execution as reproducible and reviewable, not as a
  ban on dynamic workflow generation from prompts

## Read First

Before writing docs, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. the touched task/workflow modules
4. `src/flytetest/registry.py`
5. any existing result-manifest structure if the stage writes one

## What To Update

For a new milestone, docs are usually incomplete unless all of these are considered:

- `README.md` for user-facing usage and current scope
- `CHANGELOG.md` for a visible history note when the change is worth keeping
- `docs/tool_refs/...` for concise tool-stage notes
- `DESIGN.md` only if the architecture or stated roadmap meaningfully changed
- `docs/realtime_refactor_plans/archive/` when the milestone is complete and
  should remain available as historical context
- registry descriptions if they act as machine-readable docs

## README Expectations

When documenting a workflow in `README.md`, include:

- what the workflow does
- exact local inputs it consumes
- the task graph
- expected result bundle contents
- simplifications and assumptions
- what this milestone does not yet include
- runtime/tooling notes

## Tool Reference Expectations

Tool refs under `docs/tool_refs/` should stay concise.

They should say:

- what the tool stage is for
- key inputs and outputs
- where it fits in the pipeline
- caveats for this repo’s current milestone

They should not become full external manuals.

## Tone Rules

- be precise, not promotional
- do not imply support that does not exist
- prefer “this milestone does X” over “the platform fully supports Y” unless it truly does
- state inferred behavior as inferred behavior

## Assumptions and Boundaries

Always separate:

- implemented now
- intentionally deferred
- inferred from notes
- environment-specific requirements

When documenting prompt-driven workflow generation, also separate:

- dynamic workflow planning that produces typed, saved, replayable
  `WorkflowSpec` / `BindingPlan` artifacts
- opaque one-off code generation, which is not the default project direction

If working rules changed, make sure `AGENTS.md` is updated too.

This is especially important for:

- BRAKER3
- EVM
- protein database acquisition or preprocessing
- repeat filtering
- functional annotation and submission steps

## Validation Expectations

Documentation authors should verify:

- names match code exactly
- parameters match signatures
- outputs match manifests or collector logic
- current-scope bullets reflect the actual repo state
- “not yet implemented” lists do not accidentally contradict the code

## Don’t

- don’t describe planned code as if it already landed
- don’t copy generic Flyte or tool docs that are not specific to this repo
- don’t leave outdated milestone language behind after code has shipped
- don’t let README, registry, and code disagree on task names or outputs

## Handoff

When finishing documentation work, communicate:

- which docs were updated
- which scope boundaries were clarified
- any assumptions that still need engineering confirmation
