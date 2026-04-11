# FLyteTest Development Guide

## 1. Purpose

FLyteTest is a prompt-driven biology workflow platform for composing, validating,
and executing curated bioinformatics pipelines from natural-language requests.
This guide tells contributors and agents how to work in the repository without
drifting from the architecture in `DESIGN.md`.

The default approach is to compose supported workflows from registered tasks
and workflows, keep biological steps faithful to the pipeline notes, and keep
planning, input resolution, and execution records explicit. Changes should stay
reproducible while the project grows toward broader workflow composition,
saved run recipes, and Slurm-oriented job handling.

This guide is the working rulebook for implementation discipline. `DESIGN.md`
describes the target architecture; when the two diverge, follow the biological
and architectural rules in `DESIGN.md`.

## 2. Current State

The repository is still an in-place evolution of the original Flyte RNA-seq
example, not a clean-slate rewrite. The current checked-in work should be
treated as the starting point for the broader prompt-driven annotation system.

What currently exists:

- a current workflow entrypoint in `flyte_rnaseq_workflow.py`
- a local-first execution model built around Flyte tasks and manifest-bearing
  result bundles
- an implemented baseline that covers RNA-seq QC, transcript evidence
  generation, PASA transcript alignment and assembly, and TransDecoder coding
  prediction from PASA outputs
- typed planner, resolver, registry, spec, and saved-spec executor modules that
  support the new design direction
- a small MCP showcase for a limited runnable surface
- README, docs, manifests, and tests that must stay aligned when behavior changes

What is still a target or in progress:

- broader genome annotation workflows beyond the current baseline
- more complete saved run recipe generation and replay
- Slurm-oriented submission, scheduling, monitoring, and cancellation
- prompt-driven planning that selects from registered workflows for the broader
  annotation path
- stronger validation around the notes-faithful pipeline boundaries

When working in the repo, treat the current code as a supported baseline and the
new design as the direction of travel. Do not silently rewrite the existing
baseline unless the change is explicitly needed to support the target design.

## 3. Working Rules

- Read `DESIGN.md` before making architecture or behavior changes.
- Read the relevant `.codex/*.md` guide before editing code, docs, or tests,
  especially [`.codex/documentation.md`](.codex/documentation.md) for
  documentation-style rules, [`.codex/testing.md`](.codex/testing.md) for
  test-writing guidance, [`.codex/code-review.md`](.codex/code-review.md) for
  review expectations, [`.codex/tasks.md`](.codex/tasks.md) for task-module
  work, and [`.codex/workflows.md`](.codex/workflows.md) for workflow-module
  work.
- Prefer registered tasks, workflows, planners, and manifest helpers over new
  one-off runtime logic for ordinary user requests.
- Keep biological steps narrow and faithful to `docs/braker3_evm_notes.md`.
- Keep prompt planning, input resolution, and execution records explicit and inspectable.
- Preserve `flyte_rnaseq_workflow.py` as a compatibility entrypoint until the
  repo no longer needs the old `flyte run` surface, and keep new business logic
  out of that shim.
- Treat Slurm as a real execution target: submit, schedule, monitor, and cancel
  jobs from frozen run records rather than from ad hoc shell behavior.
- Use the Flyte Slurm plugin or `sbatch` for submission, `squeue` / `scontrol
  show job` / `sacct` for observation, and `scancel` for cancellation.
- Update the docs, manifests, and tests that describe a behavior when that
  behavior changes.
- Make changes as small as possible while still solving the problem cleanly.
- Avoid broad refactors unless the requested change truly depends on them.
- If a change affects the biological pipeline order or supported workflow
  families, call that out explicitly in the change notes.
- Keep the documentation structure consistent across the codebase when adding
  or revising files. New or touched code assets should follow the same basic
  shape in the idiom appropriate to that language or file type:
  module/file header docs with purpose and scope, clear sectioned function or
  class docs where the language supports them, and explicit notes for
  assumptions or boundary behavior when they matter.

## 4. What To Update When Behavior Changes

When code changes behavior, update the docs and records that describe that
behavior instead of leaving them stale.

At minimum, consider the following:

- `README.md` when the user-facing workflow, examples, or supported scope
  change
- `DESIGN.md` when the architecture, execution model, or planning model changes
- `CHANGELOG.md` when the change is worth preserving as a visible project
  history note
- `docs/realtime_refactor_checklist.md` when a refactor milestone changes status
- `docs/realtime_refactor_plans/archive/` when a milestone is completed and
  should be kept as historical context
- `AGENTS.md` and this guide when the working rules themselves change
- manifests and result records when runtime output shapes change
- tests when the behavior, supported workflow family, or validation path
  changes

The rule is simple: if a change would surprise a future reader, update the
document in a user-friendly way so it helps that reader understand what
changed.

## 5. Validation Expectations

Validation should happen early and stay small enough to run often.

Default tests should be local and offline-friendly. Use real tool runs, Slurm,
or cluster-specific checks only when the change truly depends on them.

Before considering a change complete, check that:

- touched Python files still compile cleanly
- the relevant unit tests pass
- fixture-backed tests cover the behavior when real tools are too heavy or too
  slow for everyday validation
- smoke-test outputs and host scratch directories stay under the project tree,
  preferably `results/`, rather than host `/tmp`; container-visible `/tmp`
  should be a bind mount backed by a project-local directory when a tool expects
  `/tmp`
- when a new bioinformatics tool is introduced, look first for a small
  tutorial-backed dataset, mirrored fixture set, or similar ground-truth smoke
  test before expanding scope
- the README examples still match the supported entrypoints and arguments
- manifests and result directories still have the expected shape
- any behavioral change has a matching documentation update

Tests should also be readable on their own. New or modified tests should
include:

- a short module docstring when the file is not obvious from its path
- concise test method docstrings when the name alone does not explain the
  intent
- inline comments for non-obvious setup, path handling, biological assumptions,
  or fixture choices

Treat this as a repo-wide style rule, not just a suggestion for the current
milestone. When a file is touched, its documentation should match the same
structure that nearby files use unless there is a clear reason to differ.

Production code in `src/flytetest/tasks/*.py` and
`src/flytetest/workflows/*.py` should also keep docstrings PEP 257-compliant,
use verbose Google-style sections where helpful, and add inline comments when
taking ambiguous shortcuts that would not be obvious to a future reader. For
non-Python code, use the native documentation or comment conventions with the
same intent: make purpose, scope, assumptions, and boundary behavior explicit.

The goal is not to comment every line. The goal is to make it clear why the
test exists and what it is proving.

## 6. Biological Guardrails

The current notes-faithful genome annotation pipeline is the baseline, but it is
not the only pipeline this repo may ever support.

When adding new biological workflows or tools:

- keep the current pipeline order intact unless a change is explicitly needed
  to support the new workflow family
- do not invent tool behavior that is not supported by the notes, source code,
  or an explicitly documented assumption
- add new tasks and workflows only when they represent a real biological step or
  a clear stage boundary
- give every new task a typed dataclass input or output when it represents a
  real biological object or stage boundary
- reuse an existing dataclass when the same biological meaning already exists
- add a new dataclass only when the workflow family needs a new biological
  concept that is not already covered
- allow future pipeline families to grow from the same pattern of registered
  tasks, typed planning, saved run recipes, and explicit execution records
- document when a new workflow family shares code with the current baseline and
  when it introduces a genuinely new biological path

The guiding rule is to preserve the current annotation path while leaving room
for more workflows, more tools, and more supported biology over time.

## 7. Prompt / MCP / Slurm Rules

- Treat natural-language prompts as requests for supported workflows, not as a
  license to invent new biology or new runtime behavior.
- Use the prompt layer to identify the biological goal, the workflow family,
  the needed inputs, and any resource request the user made.
- Freeze the chosen plan into a saved run recipe before execution starts.
- Keep prompt interpretation separate from execution so the same saved plan can
  be inspected and replayed later.
- Use MCP as the user-facing interface layer for planning, recipe preparation,
  validation, result inspection, and status reporting.
- Keep MCP responses structured and machine-readable so clients do not need to
  guess what the system meant.
- Treat Slurm as a real execution target: submit jobs from frozen run records,
  monitor job state, collect logs, and support cancellation.
- Use the Flyte Slurm plugin or `sbatch` for submission, `squeue` / `scontrol
  show job` / `sacct` for observation, and `scancel` for cancellation.
- Record the scheduler job ID as soon as a job is accepted.
- Track the job through the scheduler lifecycle, including pending, running,
  completed, failed, and cancelled states.
- Record stdout and stderr log paths in the run record.
- Preserve the final scheduler state and any exit code or cancellation reason.
- Check offline compute-node assumptions before submission when the job depends
  on staged containers, databases, or inputs.
- Do not submit a Slurm job from vague resource language if the plan still
  needs clarification or confirmation.
- Prefer explicit resource choices over hidden defaults when the user asks for
  CPUs, memory, walltime, or partitioning.
