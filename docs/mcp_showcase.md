# MCP Tool Guide

This page is the end-user walkthrough for the FLyteTest MCP surface.  The
primary path is the scientist's **experiment loop**:

```
list_entries  →  list_bundles  →  load_bundle  →  run_task / run_workflow
```

Pick a registered target, load a curated starter bundle (bindings + scalar
inputs + container images + tool databases), and hand it straight to
`run_task` or `run_workflow`.  Every run is frozen into a replayable
recipe under `.runtime/specs/` before execution, so the returned
`recipe_id` is a permanent handle to the experiment.

Your MCP client controls the conversation.  FLyteTest provides the tools;
the client composes them into experiments.

## Contents

- [What This Doc Is For](#what-this-doc-is-for)
- [Runnable Targets](#runnable-targets)
- [Tools And Resources](#tools-and-resources)
- [Server And Client Setup](#server-and-client-setup)
- [Key Concepts](#key-concepts)
- [The Experiment Loop](#the-experiment-loop)
  - [Worked example 1: BRAKER3 end to end](#worked-example-1-braker3-end-to-end)
  - [Worked example 2: one task from list_entries](#worked-example-2-one-task-from-list_entries)
  - [Worked example 3: $ref cross-run reuse](#worked-example-3-ref-cross-run-reuse)
- [Binding Grammar](#binding-grammar)
- [Adding a Pipeline Family](#adding-a-pipeline-family)
- [Appendix: Inspect-Before-Execute](#appendix-inspect-before-execute)
  - [prepare_run_recipe](#prepare_run_recipe)
  - [validate_run_recipe](#validate_run_recipe)
  - [run_local_recipe / run_slurm_recipe](#run_local_recipe--run_slurm_recipe)
  - [Slurm lifecycle: monitor / retry / cancel](#slurm-lifecycle-monitor--retry--cancel)
- [Common Failure Modes](#common-failure-modes)
- [Scope Boundary](#scope-boundary)

## What This Doc Is For

Use this page when you want to:

- see what FLyteTest can run right now
- connect a client such as Codex CLI or OpenCode
- run your first workflow end-to-end from a curated bundle
- chain two runs together by referring to a prior run's output
- understand when to reach for `prepare_run_recipe` and friends instead
  of the direct run tools

This page is not the architecture source of truth.  For architecture and
longer-term design direction, see [DESIGN.md](../DESIGN.md).  For the
machine-readable contract, see
[mcp_contract.py](../src/flytetest/mcp_contract.py).

## Runnable Targets

The local recipe runner can currently handle:

- workflow: `ab_initio_annotation_braker3`
- workflow: `protein_evidence_alignment`
- workflow: `annotation_qc_busco`
- workflow: `annotation_functional_eggnog`
- workflow: `annotation_postprocess_agat`
- workflow: `annotation_postprocess_agat_conversion`
- workflow: `annotation_postprocess_agat_cleanup`
- workflow: `annotation_postprocess_table2asn`
- task: `exonerate_align_chunk`
- task: `busco_assess_proteins`
- task: `fastqc`
- task: `gffread_proteins`

Other registered entries still show up in the registry and typed planner,
but they need explicit local node handlers before they can be run through
this MCP surface.  Call `list_entries` or `list_entries(pipeline_family=
"annotation")` to see the exact runnable set at any time.

## Tools And Resources

The tools are grouped by the role they play in the experiment loop.

**Experiment loop (primary path):**

- `list_entries` — registered tasks and workflows, with their accepted
  planner-type bindings, scalar parameters, and supported execution
  profiles.  Filter by `pipeline_family=...` to scope to one family.
- `list_bundles` — curated `ResourceBundle` catalog.  Each entry is
  reported with an `available` flag plus a `reasons` list; missing
  bundles are surfaced, never hidden.
- `load_bundle` — materialize one bundle into `bindings`, `inputs`,
  `runtime_images`, and `tool_databases` dicts ready to spread into a
  run tool.
- `run_task` — run one registered task against typed bindings; returns
  a `RunReply` with `recipe_id`, `run_record_path`, `artifact_path`,
  `execution_status`, and an `outputs` dict.
- `run_workflow` — same shape as `run_task` for a registered workflow.
  A bundle dict spreads identically into either tool.
- `list_available_bindings` — discover candidate input paths for one
  task (extension-based scan with a `typed_bindings` hint for planner
  types).

**Inspect-before-execute (power tools):**

- `prepare_run_recipe` — freeze a plan into a `.runtime/specs/` artifact
  without dispatching.  Use when you want to review the fully-resolved
  state before running.
- `validate_run_recipe` — re-run the same preflight checks a real
  execution would, against a frozen artifact.  Never submits, never
  mutates.
- `run_local_recipe` — execute a previously frozen local artifact.
- `run_slurm_recipe` — submit a previously frozen Slurm artifact.

**Slurm lifecycle:**

- `monitor_slurm_job` — reconcile a durable run record against
  `squeue` / `scontrol` / `sacct`.
- `wait_for_slurm_job` — poll `monitor_slurm_job` until terminal.
- `fetch_job_log` — tail the `slurm-<jobid>.out` / `.err` files.
- `retry_slurm_job` — resubmit from the original frozen recipe; accepts
  `resource_overrides` for OOM/TIMEOUT escalation.
- `cancel_slurm_job` — record a `scancel` request.
- `list_slurm_run_history` — durable run records from `.runtime/runs/`
  without contacting the scheduler.
- `get_run_summary` / `inspect_run_result` — offline dashboard views.

**Read-only resources:**

- `flytetest://scope` — plain-language MCP boundary summary
- `flytetest://supported-targets` — runnable target shapes
- `flytetest://example-prompts` — small known-good prompt examples
- `flytetest://prompt-and-run-contract` — stable fields and result
  codes for client authors
- `flytetest://run-recipes/{path}` — raw JSON of a saved recipe
- `flytetest://result-manifests/{path}` — `run_manifest.json` from a
  result directory

## Server And Client Setup

Start the FLyteTest server over standard input/output:

```bash
env PYTHONPATH=src .venv/bin/python -m flytetest.server
```

Minimal generic client configuration:

- command: `python3`
- args: `-m flytetest.server`
- env: `PYTHONPATH=src`

Checked-in example configs:

- [docs/mcp_client_config.example.json](mcp_client_config.example.json)
- [docs/opencode.config.example.json](opencode.config.example.json)

### OpenCode

Install OpenCode as a user-local binary:

```bash
mkdir -p "$HOME/.local/bin"
export OPENCODE_INSTALL_DIR="$HOME/.local/bin"
curl -fsSL https://opencode.ai/install | bash
export PATH="$HOME/.local/bin:$PATH"
opencode --version
```

Default config location: `~/.config/opencode/opencode.json`.  Keep a
repo-local config at `/path/to/flyteTest/.config/opencode/opencode.json`
and launch with:

```bash
export OPENCODE_CONFIG=/path/to/flyteTest/.config/opencode/opencode.json
opencode
```

### Codex CLI

```bash
export FLYTETEST_REPO_ROOT=/path/to/flyteTest
export PYTHONPATH=/path/to/flyteTest/src
codex mcp add flytetest \
  --env FLYTETEST_REPO_ROOT="$FLYTETEST_REPO_ROOT" \
  --env PYTHONPATH="$PYTHONPATH" \
  -- bash -lc 'cd /path/to/flyteTest && module load python/3.11.9 && source .venv/bin/activate && python -m flytetest.server'
```

## Key Concepts

Terms that show up in every run reply:

- **bundle** — a named, typed snapshot of `bindings + inputs +
  runtime_images + tool_databases` pointing at existing fixtures under
  `data/`.  Loadable with `load_bundle(name)`; enumerated with
  `list_bundles()`.
- **binding** — a typed biological input mapped by planner-type name
  (`ReferenceGenome`, `ReadSet`, `ProteinEvidenceSet`, etc.).  Three
  forms: raw path, `$manifest`, `$ref` — see
  [Binding Grammar](#binding-grammar).
- **scalar input** — a non-asset parameter (thread count, lineage
  selector, container override).  Lives in the `inputs={...}` kwarg and
  corresponds to the task's `TASK_PARAMETERS` entries.
- **recipe_id** — a stable handle of the form
  `<YYYYMMDDThhmmss.mmm>Z-<target_name>`.  Every run reply includes one.
  Use it as the `run_id` in a later `$ref` binding.
- **artifact** — the frozen recipe JSON under `.runtime/specs/`.
  Recreated identically on every run, so the experiment is replayable.
- **run record** — the durable execution record under `.runtime/runs/`.
  Slurm monitoring, retry, and cancel all read from this file.

## The Experiment Loop

These three examples cover the same primary path from different angles:
load a bundle, run a task from the registry, and chain two runs via
`$ref`.

### Worked example 1: BRAKER3 end to end

One call reads the catalog; a second loads a bundle; a third runs the
workflow and returns a `recipe_id` plus an `outputs` dict.

```text
Use the flytetest MCP server.

Call list_bundles with exactly: pipeline_family: "annotation"
Then print each entry's name, available, and applies_to.
```

Pick `braker3_small_eukaryote` (the small-eukaryote starter kit) and
hand it to the workflow:

```text
Use the flytetest MCP server.

Call load_bundle with exactly: name: "braker3_small_eukaryote"
Then call run_workflow with:
  workflow_name: "ab_initio_annotation_braker3"
  bindings:        <bundle.bindings>
  inputs:          <bundle.inputs>
  runtime_images:  <bundle.runtime_images>
  tool_databases:  <bundle.tool_databases>
  source_prompt:   "Annotate the small-eukaryote starter kit with BRAKER3."

Then print exactly:
- supported
- recipe_id
- execution_status
- outputs
- run_record_path
- limitations
```

Equivalent Python pseudocode when the client has structured object
support:

```python
bundle = load_bundle(name="braker3_small_eukaryote")
reply = run_workflow(
    "ab_initio_annotation_braker3",
    **bundle,  # bindings, inputs, runtime_images, tool_databases
    source_prompt="Annotate the small-eukaryote starter kit with BRAKER3.",
)
# reply["recipe_id"] → "20260421T090000.000Z-ab_initio_annotation_braker3"
# reply["outputs"]   → {"annotation_gff": "results/.../braker.gff3", ...}
```

The `recipe_id` is the permanent handle to this experiment.  Save it —
you'll feed it into Example 3.

### Worked example 2: one task from list_entries

For stage-scoped experiments (e.g., tuning Exonerate on one chunk), use
`list_entries` to pick a task directly, then call `run_task`.

```text
Use the flytetest MCP server.

Call list_entries with exactly: pipeline_family: "annotation"
Pick a task entry (category == "task"), for example exonerate_align_chunk.
Read its accepted_planner_types and scalar parameters.
```

Call the task with explicit raw-path bindings and one scalar input:

```text
Call run_task with:
  task_name: "exonerate_align_chunk"
  bindings:
    ReferenceGenome:
      fasta_path: "data/braker3/reference/genome.fa"
    ProteinEvidenceSet:
      protein_fasta_path: "data/braker3/protein_data/fastas/proteins.fa"
  inputs:
    exonerate_sif: "data/images/exonerate_2.2.0--1.sif"
  source_prompt: "Experiment with Exonerate on the starter-kit fixture."

Then print exactly:
- supported
- recipe_id
- execution_status
- outputs
- limitations
```

Symmetry with Example 1: a bundle dict spreads identically into
`run_task`, so `run_task("exonerate_align_chunk",
**load_bundle("protein_evidence_demo"), source_prompt="...")` reads the
same way.

### Worked example 3: $ref cross-run reuse

Chain two experiments together without re-specifying any paths.  After
Example 1 returns a `recipe_id`, feed it into the next call's `$ref`
binding so the downstream workflow picks up the previous run's outputs
by name.

```text
Use the flytetest MCP server.

Call run_workflow with:
  workflow_name: "annotation_qc_busco"
  bindings:
    QualityAssessmentTarget:
      $ref:
        run_id: "20260421T090000.000Z-ab_initio_annotation_braker3"
        output_name: "annotation_gff"
  inputs:
    lineage_dataset: "eukaryota_odb10"
    busco_mode:      "proteins"
  source_prompt: "QC the BRAKER3 annotation against eukaryota_odb10."

Then print exactly:
- supported
- recipe_id
- outputs
- limitations
```

The resolver reads `.runtime/durable_asset_index.json`, looks up the
named output under the cited `run_id`, type-checks it against
`QualityAssessmentTarget`, and materializes it as the QC target.  If
the run ID is unknown, the output name is wrong, or the type doesn't
match, you get a structured `PlanDecline` with populated
`suggested_bundles`, `suggested_prior_runs`, and `next_steps` — never a
silent failure.

## Binding Grammar

Every typed binding follows one of three shapes.  Use the one that
matches how you know the input.

```text
bindings:
  ReferenceGenome:
    # Form 1 — raw path: you have a local file and know where it lives.
    fasta_path: "data/braker3/reference/genome.fa"

  ProteinEvidenceSet:
    # Form 2 — $manifest: point at a result folder's run_manifest.json
    # and let the resolver pick the right output file for this type.
    $manifest: "results/protein_evidence_results_20260420/run_manifest.json"
    output_name: "evm_ready_gff3"  # required when >1 output matches the type

  AnnotationEvidenceSet:
    # Form 3 — $ref: name a prior run's output by recipe_id.  This is
    # how you chain "BRAKER3 → EVM" without touching any paths.
    $ref:
      run_id: "20260421T090000.000Z-ab_initio_annotation_braker3"
      output_name: "annotation_gff"
```

Mixing forms inside one call is fine — one binding can be a raw path
while another is a `$ref`.  Durable chaining via `$ref` is the feature
that makes the experiment loop iterative: yesterday's `recipe_id`
becomes today's input.

For the authoritative grammar, see DESIGN §7.

## Adding a Pipeline Family

New pipeline families plug in without MCP-layer edits.  The recipe:

1. Planner types → `src/flytetest/planner_types.py`
2. Narrow Flyte tasks → `src/flytetest/tasks/<family>.py`
3. Biology-ordered workflows → `src/flytetest/workflows/<family>.py`
4. Registry entries → `src/flytetest/registry/_<family>.py`
5. Optional curated bundle → `src/flytetest/bundles.py`

No edits to `server.py`, `mcp_contract.py`, or `planning.py` are
required.  See [`.codex/registry.md`](../.codex/registry.md) for the
full walkthrough, including the queue/account handoff rule and the
worked GATK example.

## Appendix: Inspect-Before-Execute

The run tools freeze a recipe and execute it in the same call.  When
you want to review the fully-resolved state before dispatch — or
resubmit an existing artifact — use the inspect-before-execute tools
instead.

### prepare_run_recipe

```
prepare_run_recipe(prompt, manifest_sources=[], explicit_bindings={},
                   runtime_bindings={}, resource_request={},
                   execution_profile="local", runtime_image={})
```

Returns the typed plan plus an `artifact_path` under `.runtime/specs/`.
The saved `BindingPlan` records the execution profile, structured
`ResourceSpec`, optional `RuntimeImageSpec`, and runtime bindings
before any execution starts.

Example — prepare a Slurm-profile BRAKER3 recipe:

```text
Use the flytetest MCP server.

Call prepare_run_recipe with exactly these arguments:
- prompt: "Annotate the genome sequence of a small eukaryote using BRAKER3 with genome data/braker3/reference/genome.fa, RNA-seq evidence data/braker3/rnaseq/RNAseq.bam, and protein evidence data/braker3/protein_data/fastas/proteins.fa using execution profile slurm on account rcc-staff, queue caslake, with 8 CPUs, memory 32Gi, and walltime 02:00:00."

Then print exactly:
- supported
- typed_plan.execution_profile
- typed_plan.binding_plan.execution_profile
- typed_plan.binding_plan.runtime_bindings
- typed_plan.binding_plan.resource_spec
- artifact_path
- limitations
```

When `list_entries` shows `supported_execution_profiles` containing
`"slurm"`, the workflow's `compatibility.execution_defaults.slurm_resource_hints`
carries advisory CPU/memory/walltime defaults sized for a
small-to-medium eukaryote; `queue` and `account` are cluster-specific
and must always come from the caller (never seeded server-side).

### validate_run_recipe

Re-runs the same preflight checks a real execution would — inputs
resolve through the manifest + durable asset index, containers and
tool databases exist, and (for Slurm) every staged path sits on a
compute-visible root.  Never submits, never writes, never mutates.

```text
Call validate_run_recipe with:
  artifact_path: <path from prepare_run_recipe>
  execution_profile: "slurm"
  shared_fs_roots: ["/scratch/midway3", "/project/rcc"]

Then print exactly:
- supported
- recipe_id
- execution_profile
- findings
```

Each finding carries `kind` (`container` / `tool_database` /
`input_path` / `binding`), `key`, optional `path`, and a `reason`
(`not_found` / `not_readable` / `not_on_shared_fs` / free-form).

### run_local_recipe / run_slurm_recipe

```
run_local_recipe(artifact_path)
run_slurm_recipe(artifact_path)
```

Both load a previously frozen artifact and execute it with no
re-planning.  `run_slurm_recipe` runs the same preflight staging check
as `validate_run_recipe`; unreachable containers, tool databases, or
input paths short-circuit with `supported=False` rather than queuing a
job that will fail offline.

**Slurm prerequisites.**  All Slurm tools require the MCP server to be
running inside an already-authenticated HPC login session; the RCC
cluster uses 2FA and does not allow SSH key pairing.  Before using any
Slurm tool, confirm that `sbatch`, `squeue`, `scontrol`, `sacct`, and
`scancel` are visible on `PATH`.  If any are missing, the Slurm tools
return an `unsupported_environment` limitation instead of guessing.

### Slurm lifecycle: monitor / retry / cancel

After `run_slurm_recipe` returns a `run_record_path`:

```text
Call monitor_slurm_job with the run_record_path from run_slurm_recipe.
Repeat until final_scheduler_state is non-null.
```

| `scheduler_state` | Meaning | What to do |
|---|---|---|
| `PENDING` | Queued, not yet started | Poll again later |
| `RUNNING` | Active on compute node | Poll again; `stdout_path` available for live output |
| `COMPLETED` | Finished successfully | Retrieve outputs |
| `FAILED` | Non-zero exit code | Check `stderr_path`; retry or re-prepare |
| `TIMEOUT` | Exceeded walltime | Retry with `resource_overrides={"walltime": ...}` |
| `OUT_OF_MEMORY` | OOM kill | Retry with `resource_overrides={"memory": ...}` |
| `CANCELLED` | Cancelled by user or admin | No retry path |

Escalation retry for OOM:

```text
Call retry_slurm_job with:
  run_record_path: <path from the terminal run>
  resource_overrides: {"memory": "64Gi"}

Then print supported, job_id, retry_run_record_path, limitations.
```

`DEADLINE` is a scheduler-enforced policy rejection, not a soft
resource limit; `retry_slurm_job` with a `walltime` override is
declined.  Prepare a new recipe that fits within the scheduler's
policy limits.

Cancellation:

```text
Call cancel_slurm_job with the run_record_path from run_slurm_recipe.
Then re-call monitor_slurm_job to confirm final_scheduler_state.
```

## Common Failure Modes

### The client dropped optional tool arguments

Symptom: `run_task` / `run_workflow` ran with defaults, or
`prepare_run_recipe` returns `typed_plan.execution_profile = local`
when you asked for Slurm.

Cause: the LLM-driven client did not preserve an optional tool argument
such as `execution_profile` or `resource_request`.

Fix: put the profile and resource choices directly in the prompt text,
then verify the returned fields before submission.

### Structured mappings were sent as pseudo-dicts

Symptom: tool validation rejects a field like `bindings` or
`runtime_images`.

Cause: the client sent a string that looks like a dict instead of a
real JSON/object mapping.

Use:

```json
{"exonerate_sif":"data/images/exonerate_2.2.0--1.sif"}
```

Not:

```text
{exonerate_sif:data/images/exonerate_2.2.0--1.sif}
```

### The server was started outside the scheduler boundary

Symptom: `run_slurm_recipe`, `monitor_slurm_job`, `retry_slurm_job`, or
`cancel_slurm_job` return an `unsupported_environment` limitation.

Fix: start the MCP server from inside an authenticated HPC login
session (tmux / screen) where `sbatch`, `squeue`, `scontrol`, `sacct`,
and `scancel` are on `PATH`.

### A $ref binding can't be resolved

Symptom: a `PlanDecline` with `UnknownRunIdError`,
`UnknownOutputNameError`, or `BindingTypeMismatchError`.

Fix: the decline carries `suggested_bundles`, `suggested_prior_runs`,
and `next_steps` — read the `next_steps` list.  Typical recoveries:
call `list_available_bindings(<target>)` to confirm the `run_id`,
inspect `.runtime/durable_asset_index.json` for indexed runs, or
re-run the producing workflow to regenerate the output.

### A bundle says `available=False`

Symptom: `list_bundles` returns `available: false` with a `reasons`
list (`ReferenceGenome.fasta_path missing: ...`, `runtime_image
'busco_sif' missing: ...`).

Fix: resolve the missing paths under `data/` and retry, or choose a
different bundle that is available in your environment.  Server boot
never depends on bundle availability.

### The artifact was prepared for the wrong execution profile

Symptom: `run_slurm_recipe` says the frozen recipe must have
`execution_profile slurm`, but the artifact was frozen as `local`.

Fix: re-run `prepare_run_recipe` with the profile embedded in the
prompt text, verify the returned profile fields, then pass the new
`artifact_path` to `run_slurm_recipe`.

## Scope Boundary

The MCP server only executes targets that have explicit local node
handlers.  The handler map covers the original runnable targets, BUSCO
QC, EggNOG, the three individual AGAT post-processing slices, `fastqc`,
and `gffread_proteins`.  Broader registered stages (EVM, PASA
refinement, repeat filtering, `table2asn`, composed downstream
pipelines) are enabled only after their recipe inputs, runtime
bindings, and local handlers are made explicit.

Resource choices are frozen into the saved `BindingPlan` before any
execution starts: CPU, memory, queue, walltime, and runtime image
settings are recorded for review and replay.  Local execution uses the
explicit handler map; Slurm execution uses the saved profile and
resource spec to render `sbatch` directives.

For the machine-readable contract, see
[src/flytetest/mcp_contract.py](../src/flytetest/mcp_contract.py).
