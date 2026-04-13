# MCP Tool Guide

This page explains the MCP tools FLyteTest exposes over standard input and
standard output. It is a tool interface, not a chat bot, and it only covers
the workflow targets that are available today.

Your MCP client controls the conversation. FLyteTest gives the client tools to
check what can run, turn a prompt into a saved recipe, run that recipe locally,
or submit a frozen Slurm recipe.

Use this page as the general user guide for the MCP surface. It explains what
the tools do, how to start the server from a client, what the read-only
resources mean, and how to use the local and Slurm paths without guesswork.

## Contents

- [What This Doc Is For](#what-this-doc-is-for)
- [Runnable Targets](#runnable-targets)
- [Tools And Resources](#tools-and-resources)
- [Server And Client Setup](#server-and-client-setup)
- [Key Concepts](#key-concepts)
- [First Successful Session](#first-successful-session)
- [Prompt And Input Rules](#prompt-and-input-rules)
- [Recipe Flow](#recipe-flow)
- [Local Walkthrough](#local-walkthrough)
- [Validated Slurm Walkthrough](#validated-slurm-walkthrough)
  - [Slurm Prerequisites](#slurm-prerequisites)
  - [Phase 1: Prepare](#phase-1-prepare-a-slurm-recipe)
  - [Phase 2: Submit](#phase-2-submit-the-saved-artifact)
  - [Phase 3: Monitor](#phase-3-monitor-the-job)
  - [Phase 4: On completion](#phase-4-on-successful-completion)
  - [Phase 5: On failure](#phase-5-on-failure--retry-or-re-prepare)
  - [Phase 6: Cancel](#phase-6-cancel-a-running-or-pending-job)
- [Common Failure Modes](#common-failure-modes)
- [Result Summary](#result-summary)
- [Scope Boundary](#scope-boundary)

## What This Doc Is For

Use this page when you want to:

- see what FLyteTest can run right now
- connect a client such as Codex CLI or OpenCode
- choose between a local run and a Slurm run
- copy a known-good prompt or recipe call
- spot common client setup issues before assuming the workflow broke

This page is not the architecture source of truth. For architecture and longer
term design direction, use [DESIGN.md](../DESIGN.md).
For the machine-readable contract, use
[mcp_contract.py](../src/flytetest/mcp_contract.py).

## Runnable Targets

The local recipe runner can currently handle:

- workflow: `ab_initio_annotation_braker3`
- workflow: `protein_evidence_alignment`
- task: `exonerate_align_chunk`
- task: `busco_assess_proteins`
- workflow: `annotation_qc_busco`
- workflow: `annotation_functional_eggnog`
- workflow: `annotation_postprocess_agat`
- workflow: `annotation_postprocess_agat_conversion`
- workflow: `annotation_postprocess_agat_cleanup`

Other registered workflows may still show up in the registry and typed planner,
but they need explicit local node handlers before they can be run through this
MCP surface.

## Tools And Resources

- `list_entries`
- `plan_request`
- `prepare_run_recipe`
- `run_local_recipe`
- `run_slurm_recipe`
- `monitor_slurm_job`
- `retry_slurm_job`
- `cancel_slurm_job`
- `prompt_and_run`

Read-only resources:

- `flytetest://scope`
- `flytetest://supported-targets`
- `flytetest://example-prompts`
- `flytetest://prompt-and-run-contract`

What the tools do:

- `list_entries`
  - shows the currently runnable targets and their inputs and outputs
  - includes `supported_execution_profiles` so clients can distinguish
    local-only targets from targets that can be frozen and submitted through
    Slurm
- `plan_request`
  - makes a plan without saving it yet
- `prepare_run_recipe`
  - turns a supported plan into a saved recipe under `.runtime/specs/`
- `run_local_recipe`
  - runs a previously saved local recipe
- `run_slurm_recipe`
  - submits a previously saved Slurm recipe and writes a run record
- `monitor_slurm_job`
  - checks a Slurm run record against the live scheduler state
- `retry_slurm_job`
  - resubmits a terminal Slurm run record from its original frozen recipe unchanged; if the failure was resource-related, prepare a new recipe with updated `resource_request` instead
- `cancel_slurm_job`
  - records that a scheduler cancellation was requested
- `prompt_and_run`
  - shortcut for older clients that prepares and then runs locally in one step

What the resources are for:

- `flytetest://scope`
  - a plain-language summary of the MCP boundary
- `flytetest://supported-targets`
  - the exact runnable targets and their shape
- `flytetest://example-prompts`
  - small known-good prompt examples
- `flytetest://prompt-and-run-contract`
  - stable fields, result codes, and client-facing contract details

When to read the resources:

- read `flytetest://scope` when you are starting a new client session
- read `flytetest://supported-targets` before choosing a workflow or task
- read `flytetest://example-prompts` if you want a prompt to adapt
- read `flytetest://prompt-and-run-contract` if you are building a client or
  need to inspect returned fields in code

## Server And Client Setup

This section covers both pieces of the MCP connection:

- start the FLyteTest server so it can listen over standard input and standard
  output
- point your MCP client at that server so the client can send tool requests

### Start the server

Run this when a client needs to talk to FLyteTest over standard input and
standard output.

```bash
env PYTHONPATH=src .venv/bin/python -m flytetest.server
```

Minimal generic client configuration:

- command: `python3`
- args: `-m flytetest.server`
- env: `PYTHONPATH=src`

### Connect a client

This is how to connect your MCP client to FLyteTest. A client setup tells the
client where the server is, which config file to use, and what environment
variables it needs.

Checked-in example:

- [docs/mcp_client_config.example.json](docs/mcp_client_config.example.json)
- [docs/opencode.config.example.json](docs/opencode.config.example.json)

### OpenCode

Install OpenCode as a user-local binary:

```bash
mkdir -p "$HOME/.local/bin"
export OPENCODE_INSTALL_DIR="$HOME/.local/bin"
curl -fsSL https://opencode.ai/install | bash
export PATH="$HOME/.local/bin:$PATH"
opencode --version
```

Default config location:

- `~/.config/opencode/opencode.json`

Optional repo-local config location:

- `/path/to/flyteTest/.config/opencode/opencode.json`

If you keep an OpenCode config in a non-default location, launch it with:

```bash
export OPENCODE_CONFIG=/path/to/flyteTest/.config/opencode/opencode.json
opencode
```

Example HPC shell setup:

```bash
export PATH="$HOME/.local/bin:$PATH"
export OPENCODE_CONFIG=/scratch/midway3/$USER/flyteTest/.config/opencode/opencode.json
opencode
```

### Codex CLI

Example Codex CLI registration:

```bash
# Tell Codex where this repo lives.
export FLYTETEST_REPO_ROOT=/path/to/flyteTest
# Let Python import the local package code.
export PYTHONPATH=/path/to/flyteTest/src
# Register the FLyteTest MCP server with Codex.
codex mcp add flytetest \
  --env FLYTETEST_REPO_ROOT="$FLYTETEST_REPO_ROOT" \
  --env PYTHONPATH="$PYTHONPATH" \
  -- bash -lc 'cd /path/to/flyteTest && module load python/3.11.9 && source .venv/bin/activate && python -m flytetest.server'
```

## Key Concepts

These terms show up often in the tool responses:

- artifact
  - the saved recipe JSON under `.runtime/specs/`
- binding plan
  - the saved execution plan, including inputs, runtime settings, execution
    profile, and resource choices
- manifest source
  - either a `run_manifest.json` file or a result directory that contains one
- runtime bindings
  - explicit runtime values such as `exonerate_sif` or `busco_lineages_text`
- resource request / resource spec
  - structured CPU, memory, queue, account, and walltime settings
- run record
  - the durable Slurm run record under `.runtime/runs/`

## First Successful Session

For your first session with a new MCP client, this order is the safest:

1. Read `flytetest://scope`.
2. Call `list_entries`.
3. Read `flytetest://example-prompts`.
4. Run `prepare_run_recipe` for one supported target.
5. Inspect the returned `typed_plan` before executing anything.
6. Use `run_local_recipe` for local profile artifacts or `run_slurm_recipe` for
   verified Slurm profile artifacts.

Example resource reads:

```text
Use the flytetest MCP server and read the resource flytetest://scope.
```

```text
Use the flytetest MCP server and read the resource flytetest://supported-targets.
```

```text
Use the flytetest MCP server and read the resource flytetest://example-prompts.
```

## Prompt And Input Rules

Prompts can include explicit local file paths. The recipe tools also accept
manifest sources, saved planner bindings, and runtime bindings. The current MCP
surface does not guess paths, search remote storage, orchestrate arbitrary
workflows, or manage the Slurm job lifecycle end to end.

Manifest sources must be either:

- a `run_manifest.json` path
- a result directory containing `run_manifest.json`

For BUSCO and EggNOG recipe preparation, the caller can either supply a
serialized `QualityAssessmentTarget` directly or point the resolver at a
repeat-filtering or compatible QC result manifest. BUSCO and EggNOG runtime
bindings stay explicit and are frozen into the saved recipe.

For AGAT statistics and conversion, the caller supplies an EggNOG result
manifest or serialized `QualityAssessmentTarget`. For AGAT cleanup, the caller
supplies an AGAT conversion result manifest or serialized
`QualityAssessmentTarget`. The resolver refuses to choose when more than one
compatible manifest source is supplied.

Example BRAKER3 workflow prompt:

```text
Annotate the genome sequence of a small eukaryote using BRAKER3 with genome data/braker3/reference/genome.fa, RNA-seq evidence data/braker3/rnaseq/RNAseq.bam, and protein evidence data/braker3/protein_data/fastas/proteins.fa
```

Example protein-evidence workflow prompt:

```text
Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa
```

Example Exonerate task prompt:

```text
Experiment with Exonerate protein-to-genome alignment using genome data/braker3/reference/genome.fa and protein chunk data/braker3/protein_data/fastas/proteins.fa
```

Example M18 BUSCO fixture prompt:

```text
Run the Milestone 18 BUSCO eukaryota fixture using execution profile slurm with BUSCO_SIF data/images/busco_v6.0.0_cv1.sif, busco_cpu 2, 2 CPUs, memory 8Gi, queue caslake, account rcc-staff, and walltime 00:10:00.
```

## Recipe Flow

`prepare_run_recipe(prompt, manifest_sources=[], explicit_bindings={}, runtime_bindings={}, resource_request={}, execution_profile="local", runtime_image={})`
returns the typed plan plus the absolute path to a saved recipe artifact under
`.runtime/specs/`. The saved `BindingPlan` records the execution profile,
structured `ResourceSpec`, optional `RuntimeImageSpec`, and runtime bindings
before any execution starts.

Plain-English input guide:

- `prompt`
  - the natural-language request that says what you want to run
- `manifest_sources`
  - one or more existing result folders or `run_manifest.json` files to reuse
    as inputs
- `explicit_bindings`
  - direct input values for the planner when you already know exactly what to
    pass
  - example:

    ```json
    {
      "ReferenceGenome": {
        "fasta_path": "data/braker3/reference/genome.fa"
      }
    }
    ```
  - use this when the prompt alone is not enough and you already have the exact
    planner input object
- `runtime_bindings`
  - runtime settings for the chosen workflow, such as input file paths or tool
    options like `exonerate_sif`
  - example:

    ```json
    {
      "exonerate_sif": "data/images/exonerate_2.2.0--1.sif"
    }
    ```
  - use this for runtime inputs that point to files, including Apptainer
    container images stored as `.sif` files
- `resource_request`
  - compute settings such as CPU, memory, queue, account, and walltime
  - example:

    ```json
    {
      "cpu": 8,
      "memory": "32Gi",
      "queue": "caslake",
      "account": "rcc-staff",
      "walltime": "02:00:00"
    }
    ```
  - when unsure what to use, call `list_entries` and read
    `compatibility.execution_defaults.slurm_resource_hints` for the target
    workflow — it provides advisory cpu, memory, and walltime sized for a
    typical small-to-medium eukaryote genome; queue and account are
    cluster-specific and must always be supplied by the caller
  - these fields can also be embedded in the prompt text as a fallback for LLM
    clients that drop optional tool arguments
- `execution_profile`
  - where the recipe should run, usually `local` or `slurm`
- `runtime_image`
  - container or image metadata to freeze into the saved recipe when needed

When a client calls `prepare_run_recipe` or `prompt_and_run` directly, the
structured arguments must be real JSON/object mappings. For example, pass
`{"exonerate_sif":"data/images/exonerate_2.2.0--1.sif"}` rather than a
stringified pseudo-dict such as `{exonerate_sif:data/images/exonerate_2.2.0--1.sif}`.
For Slurm preparation, also verify that the returned `typed_plan.execution_profile`
and `typed_plan.binding_plan.execution_profile` are both `slurm` before passing
the saved artifact to `run_slurm_recipe`.
For the M18 BUSCO fixture, verify that
`typed_plan.binding_plan.runtime_bindings` contains
`proteins_fasta=data/busco/test_data/eukaryota/genome.fna`,
`lineage_dataset=auto-lineage`, `busco_mode=geno`, and the intended
`busco_sif` before submission.
If an LLM-driven client does not preserve optional tool arguments reliably,
encode the execution profile and resource choices directly in the prompt text,
then verify the frozen recipe before submission.

`run_local_recipe(artifact_path)` loads that artifact and executes it through
`LocalWorkflowSpecExecutor` with the server's explicit handler map.

`run_slurm_recipe(artifact_path)` loads a saved artifact whose execution profile
is `slurm`, renders a deterministic `sbatch` script under `.runtime/runs/`,
submits it with `sbatch`, and records the accepted Slurm job ID in
`slurm_run_record.json`. The generated `sbatch` script is saved alongside the
run record under `.runtime/runs/<run_id>/` and can be inspected before or after
submission to verify directives. On the RCC cluster the frozen recipe also
carries the Slurm account setting into the generated script so manual
`sbatch --account=...` overrides are not required for submission. This path is
supported only when the MCP server is running inside an already-authenticated
scheduler-capable environment where `sbatch` is available on `PATH`.

`monitor_slurm_job(run_record_path)` reloads that durable record and reconciles
it with `squeue`, `scontrol show job`, and `sacct`. When Slurm returns concrete
state, the record is updated with scheduler state, stdout/stderr paths, exit
code, and final state when terminal. If the server is started outside that
scheduler boundary, monitoring returns an explicit unsupported-environment
limitation instead of guessing.

`cancel_slurm_job(run_record_path)` reloads the same durable record, requests
`scancel <job-id>`, and records that cancellation was requested. Final cancelled
state is confirmed by a later `monitor_slurm_job` reconciliation. Cancellation
likewise requires the same already-authenticated scheduler environment.

`prompt_and_run(prompt, manifest_sources=[], explicit_bindings={}, runtime_bindings={}, resource_request={}, execution_profile="local", runtime_image={})`
remains available for existing clients. It performs the same prepare-then-run
sequence and returns the artifact path alongside the execution summary.

Resource choices are frozen before execution. CPU, memory, queue, walltime, and
runtime image settings are recorded for review and replay. Local execution uses
the explicit handler map, while Slurm execution uses the saved profile and
resource spec to render `sbatch` directives.

## Local Walkthrough

The local path is the simplest way to prove that prompt interpretation and
saved-recipe execution are both working before adding scheduler behavior.

Quick sanity check:

```text
Use the flytetest MCP server and call list_entries.
```

Prepare a local recipe:

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa."
- runtime_bindings: {"exonerate_sif":"data/images/exonerate_2.2.0--1.sif"}

Then print exactly:
- supported
- typed_plan.execution_profile
- typed_plan.binding_plan.execution_profile
- typed_plan.binding_plan.runtime_bindings
- artifact_path
- limitations
```

Run the saved local artifact:

```text
Use the flytetest MCP server.

Call run_local_recipe with the artifact_path from the last successful prepare_run_recipe call.

Then print exactly:
- supported
- execution_result.execution_profile
- execution_result.output_paths
- limitations
```

## Validated Slurm Walkthrough

The following prompt sequence was validated on the RCC cluster with an
authenticated scheduler session.

### Slurm Prerequisites

All Slurm tools require the MCP server to be running inside an
already-authenticated HPC login session. The RCC cluster uses 2FA and does not
allow SSH key pairing, so the server must run from within an interactive session
on a login node rather than connecting to the scheduler remotely.

Before using any Slurm tool, confirm:

- The MCP server process is running on a login node inside an active
  authenticated session (tmux, screen, or equivalent)
- `sbatch`, `squeue`, `scontrol`, `sacct`, and `scancel` are visible on `PATH`

If any of these commands are missing, `run_slurm_recipe`, `monitor_slurm_job`,
`retry_slurm_job`, and `cancel_slurm_job` will return an
`unsupported_environment` limitation.

Quick sanity check:

```text
Use the flytetest MCP server and call list_entries.
```

To list only targets that can be submitted through Slurm, ask the client:

```text
Use the flytetest MCP server and call list_entries.

Print only entries where supported_execution_profiles contains "slurm".
For each one, print:
- name
- category
- default_execution_profile
- supported_execution_profiles
```

### Phase 1: Prepare a Slurm recipe

Protein evidence alignment with explicit resource settings:

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run protein evidence alignment with genome data/braker3/reference/genome.fa and protein evidence data/braker3/protein_data/fastas/proteins.fa using execution profile slurm on account rcc-staff, queue caslake, with 8 CPUs, memory 32Gi, and walltime 02:00:00."
- runtime_bindings: {"exonerate_sif":"data/images/exonerate_2.2.0--1.sif"}

Then print exactly:
- supported
- typed_plan.execution_profile
- typed_plan.binding_plan.execution_profile
- typed_plan.binding_plan.runtime_bindings
- typed_plan.resource_spec
- typed_plan.binding_plan.resource_spec
- artifact_path
- limitations
```

BUSCO fixture with explicit resource settings:

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Run the Milestone 18 BUSCO eukaryota fixture using execution profile slurm with BUSCO_SIF data/images/busco_v6.0.0_cv1.sif, busco_cpu 2, 2 CPUs, memory 8Gi, queue caslake, account rcc-staff, and walltime 00:10:00."

Then print exactly:
- supported
- typed_plan.biological_goal
- typed_plan.candidate_outcome
- typed_plan.execution_profile
- typed_plan.binding_plan.execution_profile
- typed_plan.binding_plan.runtime_bindings
- typed_plan.binding_plan.resource_spec
- artifact_path
- limitations
```

Before submitting, verify that both `typed_plan.execution_profile` and
`typed_plan.binding_plan.execution_profile` are `slurm`. If either reads
`local`, the client dropped the execution profile argument — re-run with the
profile embedded in the prompt text.

### Phase 2: Submit the saved artifact

```text
Use the flytetest MCP server.

Call run_slurm_recipe with the artifact_path from the last successful prepare_run_recipe call.

Then print exactly:
- supported
- job_id
- run_record_path
- limitations
```

The `run_record_path` is the path to the durable run record. Save it — every
subsequent monitoring, retry, and cancel call needs it. The generated `sbatch`
script is also saved under `.runtime/runs/<run_id>/` and can be inspected to
verify the directives that were submitted.

For direct MCP submissions, the server also refreshes the generic latest-run
pointer files `.runtime/runs/latest_slurm_run_record.txt` and
`.runtime/runs/latest_slurm_artifact.txt`. Use those pointers when you need a
shell-side watcher to follow the newest accepted Slurm submission without
copy/pasting the returned path each time.

### Phase 3: Monitor the job

Call `monitor_slurm_job` with the `run_record_path` from Phase 2 and repeat
until `final_scheduler_state` is non-null. A non-null `final_scheduler_state`
means the job has reached a terminal state.

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the run_record_path from run_slurm_recipe.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state
- stdout_path
- stderr_path
- run_record_path
- limitations
```

Scheduler state reference:

| `scheduler_state` | Meaning | What to do |
|---|---|---|
| `PENDING` | Queued, not yet started | Poll again later |
| `RUNNING` | Active on compute node | Poll again; `stdout_path` available for live output |
| `COMPLETED` | Finished successfully | Retrieve outputs — see Phase 4 |
| `FAILED` | Non-zero exit code | Check `stderr_path`; see Phase 5 |
| `TIMEOUT` | Exceeded walltime | See Phase 5 — retry requires a new recipe with longer `walltime` |
| `OUT_OF_MEMORY` | OOM kill | See Phase 5 — retry requires a new recipe with more `memory` |
| `CANCELLED` | Cancelled by user or admin | No retry path |

### Phase 4: On successful completion

When `scheduler_state = COMPLETED` and `final_scheduler_state` is non-null,
the job finished successfully. The `stdout_path` and `stderr_path` fields point
to the job output files on the shared filesystem.

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the run_record_path.

Then print exactly:
- supported
- scheduler_state         (expect: COMPLETED)
- final_scheduler_state   (expect: COMPLETED)
- stdout_path
- stderr_path
- run_record_path
- limitations
```

### Phase 5: On failure — retry or re-prepare

If the job reached a terminal failure state (`FAILED`, `TIMEOUT`,
`OUT_OF_MEMORY`), decide whether to retry or re-prepare:

- **Transient failure (`FAILED`):** call `retry_slurm_job` to resubmit from
  the same frozen recipe.
- **Resource failure (`TIMEOUT` or `OUT_OF_MEMORY`):** the frozen recipe has
  the same resource limits that caused the failure. Call `prepare_run_recipe`
  again with a larger `resource_request` (e.g. more `memory` or longer
  `walltime`), then submit the new artifact.

Retry from a terminal failed run record:

```text
Use the flytetest MCP server.

Call retry_slurm_job with the run_record_path from the terminal run.

Then print exactly:
- supported
- job_id
- run_record_path
- limitations
```

The response returns a new `job_id` and a new `run_record_path` for the child
run. Use the new `run_record_path` for all subsequent monitoring calls.

### Phase 6: Cancel a running or pending job

```text
Use the flytetest MCP server.

Call cancel_slurm_job with the run_record_path from run_slurm_recipe.

Then print exactly:
- supported
- job_id
- run_record_path
- limitations
- run_record.scheduler_state
- run_record.final_scheduler_state
```

Cancellation is recorded immediately, but the final cancelled state is
confirmed by a subsequent `monitor_slurm_job` call:

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the same run_record_path after cancellation.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state
- run_record_path
- limitations
```

## Common Failure Modes

These are the most common ways a session can go wrong even when the workflow
code itself is fine.

### The client dropped optional tool arguments

Symptom:

- `prepare_run_recipe` returns `typed_plan.execution_profile = local` even
  though you intended `slurm`

What it usually means:

- the LLM-driven client did not preserve an optional tool argument such as
  `execution_profile` or `resource_request`

What to do:

- put `execution profile slurm` and resource choices directly in the prompt text
- then verify the returned `typed_plan.execution_profile` and
  `typed_plan.binding_plan.execution_profile` before submission

### Structured mappings were sent as pseudo-dicts

Symptom:

- tool validation rejects a field like `runtime_bindings`

What it usually means:

- the client sent a string that looks like a dict instead of a real JSON/object mapping

Use:

```json
{"exonerate_sif":"data/images/exonerate_2.2.0--1.sif"}
```

Do not use:

```text
{exonerate_sif:data/images/exonerate_2.2.0--1.sif}
```

### The server was started outside the scheduler boundary

Symptom:

- `run_slurm_recipe`, `monitor_slurm_job`, `retry_slurm_job`, or
  `cancel_slurm_job` return an `unsupported_environment` limitation

What to do:

- see [Slurm Prerequisites](#slurm-prerequisites) above for the full setup
  checklist
- confirm `sbatch`, `squeue`, `scontrol`, `sacct`, and `scancel` are visible
  on `PATH` inside the session where the server is running

### The artifact was prepared for the wrong execution profile

Symptom:

- `run_slurm_recipe` says the frozen recipe must have `execution_profile slurm`

What it means:

- the artifact you passed was frozen as `local`

What to do:

- re-run `prepare_run_recipe`
- verify the returned profile fields
- only then pass the new `artifact_path` to `run_slurm_recipe`

## Result Summary

`prompt_and_run` returns the planning and execution payload plus a compact
`result_summary` block for client display. Stable fields include:

- `status`
- `result_code`
- `reason_code`
- `target_name`
- `execution_attempted`
- `used_inputs`
- `output_paths`
- `typed_planning_available`
- `artifact_path`
- `execution_profile`
- `resource_spec`
- `runtime_image`
- `message`

Important result-code categories:

- `succeeded`
- `declined_missing_inputs`
- `declined_unsupported_request`
- `failed_execution`

For the exact machine-readable contract, see
[src/flytetest/mcp_contract.py](../src/flytetest/mcp_contract.py).

## Scope Boundary

The MCP server only executes targets that have explicit local node handlers.
The handler map covers the original three runnable targets, BUSCO QC, EggNOG,
and the three individual AGAT post-processing slices.
Broader registered stages such as EVM, PASA refinement, repeat filtering,
`table2asn`, Slurm retry/resubmission, and composed downstream pipelines should be
enabled only after their recipe inputs, runtime bindings, and local handlers
are made explicit.
