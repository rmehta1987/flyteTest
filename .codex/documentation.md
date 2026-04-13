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

## Code Documentation Expectations

**The depth target is `slurm_poll_loop` in `src/flytetest/slurm_monitor.py`.**
That docstring explains deployment context (started as a background task inside
the MCP server event loop), lifecycle contract ("never returns normally; runs
until cancelled"), error handling strategy (exponential backoff on failure,
cancellation re-raised immediately), and Args entries that explain *why each
parameter exists*, not just its type.  Any function with non-trivial lifecycle
behavior, error handling, or pipeline assumptions should reach that level of
substance.  A one-liner is correct when it captures everything a maintainer
needs to know without reading the body.

For all code files in the repository, documentation comments and docstrings
should follow these rules, using the idiomatic style for the language or file
type in question:

- comply with PEP 257
- use Google-style docstring structure (summary line, then Args / Returns /
  Raises sections as needed) for modules, functions, tasks, and workflows
- use named sub-sections (`Error handling:`, `Output contract:`, `Retry
  logic:`) when a function has behavior complex enough that a reader would
  otherwise need to read the full body to understand the boundary
- each Args entry must answer why the stage or function needs that input: its
  role in the biological pipeline, the constraint that governs its value, or
  the execution contract it participates in — restating the type name is not
  a description
- each Returns entry must explain what the caller can do with the result and
  what invariant it can rely on, not just name the type being returned
- stay aligned with the current code path rather than describing an idealized
  or future implementation

**The Args and Returns sections are not always required.** Include them when:

- a parameter name is ambiguous without explanation (`label`, `source`, `value`)
- a parameter has a non-obvious constraint (e.g., "must be a directory, not a
  file path", "lineage name must include the `_odb10` suffix")
- the return value is not self-evident from the function name and type hint

Omit them when:

- the function name and type hint are unambiguous (`def _created_at() -> str`)
- the parameter role is obvious from the name and its position in a short
  function

**Anti-pattern to avoid:** boilerplate that restates the type without adding
content. This pattern appears in the codebase and should not be continued:

```python
def _manifest_path(directory: Path, label: str) -> Path:
    """Resolve the manifest expected under a stage output directory.

    Args:
        directory: A value used by the helper.
        label: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
    """
```

Preferred — each description answers why the function needs that input:

```python
def _manifest_path(results_dir: Path, stage_label: str) -> Path:
    """Resolve the run_manifest.json expected under a stage output directory.

    Args:
        results_dir: Root of the stage result bundle.  Must be a directory,
            not a file path; the manifest is always one level inside the
            bundle root.
        stage_label: Name of the pipeline stage, used in the missing-manifest
            error so the caller knows which upstream stage failed to write its
            output contract.

    Returns:
        Path to run_manifest.json; raises if the file is absent so callers
        never silently proceed without a stage record.
    """
```

Apply the same documentation structure consistently across the codebase when
adding or revising files. In practice, that means:

- Python module docstrings should explain purpose, pipeline position, and any
  notable boundary assumptions; continuation lines should be indented to match
  the opening `"""` column, not the enclosing scope
- Python function, task, workflow, and class docstrings should use the same
  Google-style sections that the surrounding files use
- dataclass fields that are not self-evident from the name should be documented
  with an `Attributes:` section in the class docstring (see `SlurmPollingConfig`
  in `slurm_monitor.py` for a good example)
- test files should have an opening module docstring, class-level intent
  statements, and one-sentence method-level purpose statements; nested closures
  inside test methods need at most a one-liner, not full Args/Returns sections
- shell scripts, R files, notebooks, C/C++ sources, and other code assets
  should use the equivalent language-native documentation mechanism or comment
  conventions to capture purpose, scope, inputs, outputs, assumptions, and
  boundary behavior
- when a file is touched, prefer bringing its documentation into the same
  structural pattern as nearby files instead of leaving a one-off style behind

**Watch for copy-paste docstring drift.** Several dataclasses in `spec_executor.py`
share an identical boilerplate docstring body that does not describe the actual
class. When touching any of those classes, replace the boilerplate with a
description of that class's specific purpose and fields.

If implementation or documentation relies on an ambiguous shortcut, include a
short inline comment near the shortcut explaining why it is intentional. This
is especially important for:

- path handling
- biological assumptions
- manifest shaping
- data filtering or normalization shortcuts
- fallback behavior that would not be obvious from the code alone

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
