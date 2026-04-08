# Tasks Guide

This file is a repo-specific guide for implementing FLyteTest task modules.
It is not a generic Flyte prompt and it should not override `AGENTS.md` or `DESIGN.md`.

## Purpose

Use this guide when adding or modifying individual task functions in `src/flytetest/tasks/`.

In FLyteTest, tasks should model one meaningful biological tool invocation or one deterministic transformation.
They should be narrow, inspectable, and faithful to the pipeline notes.
When a task represents a real biological object or stage boundary, give it a typed dataclass input or output when that improves clarity.

## Read First

Before changing task code, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. the relevant file under `docs/tool_refs/`
4. the nearest existing task module in `src/flytetest/tasks/`
5. the relevant workflow and registry entries if the task is already exposed

## Repo Truths

Follow the repo as it exists today, not a generic Flyte template:

- use Flyte v2 APIs
- prefer `flyte.TaskEnvironment`
- prefer `flyte.io.File` and `flyte.io.Dir` in task signatures
- use `Path` internally for filesystem handling
- use helpers from `src/flytetest/config.py`, especially `require_path` and `run_tool`
- keep the typed asset layer in `src/flytetest/types/assets.py` as a clarity/provenance layer, not a mandatory direct task-signature layer
- return deterministic output directories or files and write manifests when the task is a stage boundary or collection step
- prefer reusing an existing typed dataclass when it already matches the same biological meaning
- add a new typed dataclass only when the workflow family needs a genuinely new biological concept

## Default Hardware Choices

When adding a new task family, define sensible default hardware choices in the family `TaskEnvironment` in `src/flytetest/config.py`.
Treat these as stable defaults for scheduling and container/runtime setup, not as ad hoc values scattered through individual tasks.

Use this split:

- `TaskEnvironment.resources`: default CPU and memory for the task family
- task or workflow scalar inputs: tool flags such as thread count, chunk size, max intron length, or memory flags passed to the underlying tool
- manifests and registry entries: document both the default hardware expectation and the user-facing runtime knobs

Current repo-friendly starting points:

- QC and Salmon tasks:
  default to `cpu=4`, `memory="16Gi"`
- transcript evidence tasks:
  default to `cpu=8`, `memory="32Gi"`
- PASA and TransDecoder tasks:
  default to `cpu=8`, `memory="32Gi"`
- protein evidence and Exonerate tasks:
  default to `cpu=8`, `memory="32Gi"`
- future BRAKER3, EVM, BUSCO, and EggNOG families:
  start with `cpu=16`, `memory="64Gi"` unless the concrete tool notes justify something else

When in doubt:

- prefer conservative defaults that are likely to run locally or on a standard cluster queue
- expose tool-level controls like `star_threads`, `pasa_cpu`, or `proteins_per_chunk` as normal workflow inputs
- use named execution profiles later if the repo needs multiple hardware classes, rather than making resources completely free-form at runtime
- keep room for future workflow families by making task boundaries reusable instead of overly specialized

## What A Good Task Looks Like

A good FLyteTest task:

- does one biological step or one deterministic transformation
- has explicit typed inputs and outputs
- documents assumptions instead of hiding them
- preserves pipeline order instead of collapsing multiple stages
- stages outputs in predictable locations
- works for local execution first and leaves room for container or HPC execution

Examples already in the repo:

- `star_genome_index`
- `star_align_sample`
- `samtools_merge_bams`
- `pasa_seqclean`
- `transdecoder_train_from_pasa`
- `exonerate_align_chunk`

## Implementation Pattern

When implementing a task:

1. Confirm the biological boundary.
   One tool call or one deterministic transformation only.

2. Pick the right module.
   Use the biological family already established in the repo:
   `qc.py`, `quant.py`, `transcript_evidence.py`, `pasa.py`, `protein_evidence.py`, and future family modules like `annotation.py` or `functional.py`.

3. Use explicit Flyte I/O.
   Prefer `File`, `Dir`, `list[File]`, or `list[Dir]` in task signatures.

4. Resolve local paths immediately.
   Use `download_sync()` and then `require_path(...)` near the start of the task.

5. Create a deterministic output location.
   Use a temporary working directory for tool execution or a timestamped `results/` directory for collection steps.

6. Run tools through `run_tool(...)`.
   That keeps local and container execution patterns aligned.

7. Keep hardware defaults and tool knobs separate.
   Put default CPU and memory in the task family environment, and keep tool-specific flags like threads or chunk size in the task signature.

8. Collect only stable outputs.
   Do not rely on incidental scratch files unless they are part of the intended output contract.

9. Write a manifest when the task is a bundle/collector stage.
   Include assumptions, key outputs, and lightweight provenance.

## Task Pseudocode

Use this as the default FLyteTest task shape:

```python
from pathlib import Path

from flyte.io import Dir, File

from flytetest.config import family_env, require_path, run_tool


@family_env.task
def tool_level_task(
    upstream_input: File | Dir,
    tool_flag: int = 4,
    tool_sif: str = "",
) -> File | Dir:
    local_input = require_path(Path(upstream_input.download_sync()), "Upstream input")

    work_dir = Path(tempfile.mkdtemp(prefix="family_step_")) / "step_output"
    work_dir.mkdir(parents=True, exist_ok=True)

    run_tool(
        [
            "tool-binary",
            "--input",
            str(local_input),
            "--threads",
            str(tool_flag),
            "--output",
            str(work_dir),
        ],
        tool_sif,
        [local_input.parent, work_dir.parent],
    )

    stable_output = require_path(work_dir / "expected_output.ext", "Stable task output")
    return File.from_local_sync(str(stable_output))
```

For a deterministic transformation task rather than a direct tool call:

```python
@family_env.task
def deterministic_transform(input_dir: Dir) -> Dir:
    local_dir = require_path(Path(input_dir.download_sync()), "Input directory")

    out_dir = Path(tempfile.mkdtemp(prefix="family_transform_")) / "transformed"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve exact expected inputs.
    # Write exactly the stable derived outputs.
    # Avoid hidden side effects and incidental scratch dependencies.

    return Dir.from_local_sync(str(out_dir))
```

Keep the FLyteTest design philosophy visible in the pseudocode:

- one biological action or one deterministic transformation per task
- explicit `File` and `Dir` boundaries
- local path resolution up front
- `TaskEnvironment` for default hardware and runtime policy
- `run_tool(...)` for local/container parity
- stable outputs, not opaque scratch trees

## Typed Asset Guidance

Use the typed asset layer where it improves clarity or collected provenance.

Good uses:

- manifest summaries
- stage boundary bundles
- result collectors
- documenting relationships between files

Avoid forcing typed assets into a task signature just because the type exists.
The current repo still primarily uses `flyte.io.File` and `flyte.io.Dir` for runnable task interfaces.

## Assumptions

Be explicit when a step is inferred.

Especially important for:

- BRAKER3 invocation details
- protein database preprocessing
- environment-specific helper scripts
- output discovery heuristics

If the notes do not specify something exactly, write it down as an assumption in code comments only if truly needed, and in manifests or docs where users will actually see it.

## Naming

Name tasks by biological action and tool behavior, not generic wrapper verbs.

Good examples:

- `stringtie_assemble`
- `pasa_create_sqlite_db`
- `exonerate_to_evm_gff3`

Avoid:

- vague names like `process_data`
- giant names that combine multiple stages
- runtime-generated task names

## File and Subprocess Style

- use `Path` for all internal path handling
- convert to `str(...)` only at the subprocess boundary
- prefer small helper functions for output discovery and manifest shaping
- keep helpers deterministic and local to the module unless they are truly shared
- do not add async patterns just because a task is I/O heavy; follow the repo’s existing sync style unless the whole repo evolves

## Validation Expectations

Task authors should do feasible validation before handoff.

That usually includes:

- `python3 -m py_compile` on touched Python files
- path-handling checks
- manifest-shaping checks
- synthetic local tests when the external tool is unavailable
- shell syntax checks if helper scripts were touched

Do not stop at “the testing guide will handle it” if you can cheaply validate your own work.

## Don’t

- don’t use `flytekit` patterns when the repo uses `flyte`
- don’t invent unsupported biology to make the pipeline seem more complete
- don’t hide multiple pipeline stages in one opaque task
- don’t rewrite working workflows just to satisfy one user request
- don’t force a full typed-asset rewrite when `File` and `Dir` are still the runtime boundary
- don’t add remote download logic when the milestone is local-input only

## Handoff

When finishing task work, communicate:

- which task functions were added or changed
- whether any typed assets were added or updated
- what assumptions were introduced
- what was verified locally
- what still needs workflow wiring, docs, or code review
