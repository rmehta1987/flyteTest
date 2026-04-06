# Workflows Guide

This file is a repo-specific guide for implementing FLyteTest workflow modules.
It complements `AGENTS.md` and `DESIGN.md`.

## Purpose

Use this guide when adding or modifying workflow entrypoints in `src/flytetest/workflows/` and the compatibility surface in `flyte_rnaseq_workflow.py`.

In FLyteTest, workflows represent biological intent.
Tasks hold tool-level detail.

## Read First

Before changing workflow code, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. the relevant task modules
4. `src/flytetest/registry.py`
5. `README.md`

## Repo Truths

- current workflow entrypoints are implemented as composed `@env.task` functions because the repo notes that the current Flyte SDK setup exposes `env.task` but not `env.workflow`
- workflows should preserve the actual pipeline order from the notes
- workflows should expose meaningful stage-level entrypoints that users can request directly
- compatibility exports in `flyte_rnaseq_workflow.py` must stay intact

## What A Good Workflow Looks Like

A good FLyteTest workflow:

- maps to a real biological stage
- composes pre-existing tasks instead of generating code
- keeps stage boundaries visible
- exposes explicit inputs
- collects outputs into a stable results bundle
- leaves downstream stages for later if they are not part of the current milestone

Examples:

- `rnaseq_qc_quant`
- `transcript_evidence_generation`
- `pasa_transcript_alignment`
- `transdecoder_from_pasa`
- `protein_evidence_alignment`

## Implementation Pattern

When implementing a workflow:

1. Define the biological intent clearly.
   Example: “protein evidence alignment” or “consensus annotation with EVM”.

2. Keep the order explicit.
   Follow the dependency structure in `AGENTS.md`.

3. Reuse narrow tasks.
   If you need a new biological operation, add a task first instead of burying the logic in the workflow.

4. Preserve collector stages.
   Workflows should usually end in a stable results bundle with a manifest.

5. Keep simplifications visible.
   If the workflow is local-input only, single-sample only, or stops before downstream steps, state that in manifests and docs.

## Workflow Pseudocode

Use this as the default FLyteTest workflow shape:

```python
from flyte.io import Dir, File

from flytetest.config import family_env
from flytetest.tasks.family import (
    collector_task,
    first_stage_task,
    second_stage_task,
    third_stage_task,
)


@family_env.task
def biological_stage_workflow(
    primary_input: File,
    secondary_input: Dir,
    runtime_flag: int = 4,
    tool_sif: str = "",
) -> Dir:
    first_output = first_stage_task(
        primary_input=primary_input,
        tool_sif=tool_sif,
        runtime_flag=runtime_flag,
    )
    second_output = second_stage_task(
        upstream=first_output,
        tool_sif=tool_sif,
    )
    third_output = third_stage_task(
        upstream=second_output,
    )

    return collector_task(
        primary_input=primary_input,
        stage_one=first_output,
        stage_two=second_output,
        stage_three=third_output,
    )
```

For a workflow that fans out by chunk or partition, keep the boundaries explicit:

```python
@family_env.task
def chunked_biological_stage(
    genome: File,
    evidence_inputs: list[File],
    chunk_size: int = 500,
    tool_sif: str = "",
) -> Dir:
    staged_inputs = stage_inputs(evidence_inputs=evidence_inputs)
    chunks = chunk_inputs(staged_inputs=staged_inputs, chunk_size=chunk_size)

    raw_results = []
    converted_results = []
    for chunk in resolve_chunks(chunks):
        raw_chunk = align_chunk(genome=genome, chunk=chunk, tool_sif=tool_sif)
        converted_chunk = convert_chunk(raw_chunk=raw_chunk)
        raw_results.append(raw_chunk)
        converted_results.append(converted_chunk)

    return collect_results(
        genome=genome,
        staged_inputs=staged_inputs,
        chunks=chunks,
        raw_results=raw_results,
        converted_results=converted_results,
    )
```

Keep the FLyteTest design philosophy visible in the pseudocode:

- workflows express biological intent, not tool internals
- workflows compose pre-registered narrow tasks
- pipeline order stays explicit and reviewable
- stage boundaries remain visible
- collection happens at the end in a deterministic manifest-bearing bundle
- unsupported downstream stages remain out of scope until their own milestone

## Registry and Compatibility

Workflow work is incomplete until these stay aligned:

- `src/flytetest/workflows/...`
- `src/flytetest/workflows/__init__.py`
- `flyte_rnaseq_workflow.py`
- `src/flytetest/registry.py`
- `README.md`

The registry entry should match the real workflow signature exactly:

- names
- input types
- output types
- descriptions

## Design Rules

- choose biological intent names, not generic pipeline names
- do not collapse multiple major annotation stages into one milestone unless the milestone explicitly calls for it
- avoid adding runtime code generation or autonomous graph rewriting
- prefer deterministic local-first behavior over generalized orchestration cleverness

## Assumptions

If a workflow includes inferred behavior, surface it:

- in the collector manifest
- in `README.md`
- in registry descriptions when useful

Do not present inferred BRAKER3, EVM, or protein preprocessing details as if they came directly from the notes.

## Validation Expectations

Workflow authors should verify:

- the module compiles
- registry wiring matches the code
- exports are intact
- docs reflect the actual workflow parameters and outputs
- synthetic path/result handling works if real tool execution is not available

## Don’t

- don’t hide new task logic inside a workflow body if it should be a reusable task
- don’t break the existing entrypoints while adding a new one
- don’t let README and registry drift from the actual implementation
- don’t claim end-to-end support for stages that are still future milestones

## Handoff

When finishing workflow work, communicate:

- the workflow task graph
- what existing workflows were intentionally left unchanged
- what registry and compatibility surfaces were updated
- what was verified
- what the next stage in the pipeline should be
