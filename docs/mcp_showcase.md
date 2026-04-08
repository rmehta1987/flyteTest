# MCP Recipe Surface

This page documents the current MCP stdio tool surface for FLyteTest. It is a
tool-provider interface, not a chat agent and not the full workflow catalog.

The MCP-capable client owns the conversation. FLyteTest exposes tools that let
the client inspect supported targets, prepare a frozen recipe from a prompt, or
run a saved recipe locally or submit a frozen Slurm-profile recipe.

## Runnable Targets

Current local recipe execution is intentionally limited to:

- workflow: `ab_initio_annotation_braker3`
- workflow: `protein_evidence_alignment`
- task: `exonerate_align_chunk`
- workflow: `annotation_qc_busco`
- workflow: `annotation_functional_eggnog`
- workflow: `annotation_postprocess_agat`
- workflow: `annotation_postprocess_agat_conversion`
- workflow: `annotation_postprocess_agat_cleanup`

Other registered workflows may still be visible in the registry and typed
planner, but they need explicit local node handlers before they become runnable
MCP targets.

## Tools

- `list_entries`
- `plan_request`
- `prepare_run_recipe`
- `run_local_recipe`
- `run_slurm_recipe`
- `monitor_slurm_job`
- `cancel_slurm_job`
- `prompt_and_run`

Read-only resources:

- `flytetest://scope`
- `flytetest://supported-targets`
- `flytetest://example-prompts`
- `flytetest://prompt-and-run-contract`

## Launch

```bash
env PYTHONPATH=src .venv/bin/python -m flytetest.server
```

Example client configuration:

- command: `python3`
- args: `-m flytetest.server`
- env: `PYTHONPATH=src`

Checked-in example:

- [docs/mcp_client_config.example.json](/home/rmeht/Projects/flyteTest/docs/mcp_client_config.example.json)

## Prompt Requirements

Runnable prompts can still include explicit local file paths, but the recipe
preparation tools now also accept explicit manifest sources, serialized planner
bindings, and runtime bindings. The current MCP surface does not perform
automatic path discovery, remote lookup, generic orchestration, or Slurm
lifecycle management.

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
Annotate the genome sequence of a small eukaryote using BRAKER3 with genome data/genome.fa, RNA-seq evidence data/RNAseq.bam, and protein evidence data/proteins.fa
```

Example protein-evidence workflow prompt:

```text
Run protein evidence alignment with genome data/genome.fa and protein evidence data/proteins.fa
```

Example Exonerate task prompt:

```text
Experiment with Exonerate protein-to-genome alignment using genome data/genome.fa and protein chunk data/proteins.fa
```

## Recipe Flow

`prepare_run_recipe(prompt, manifest_sources=[], explicit_bindings={}, runtime_bindings={}, resource_request={}, execution_profile="local", runtime_image={})`
returns the typed plan plus the absolute path to a saved recipe artifact under
`.runtime/specs/`. The saved `BindingPlan` records the selected execution
profile, structured `ResourceSpec`, optional `RuntimeImageSpec`, and ordinary
runtime bindings before any local execution starts.

`run_local_recipe(artifact_path)` loads that artifact and executes it through
`LocalWorkflowSpecExecutor` with the server's explicit handler map.

`run_slurm_recipe(artifact_path)` loads a saved artifact whose execution profile
is `slurm`, renders a deterministic `sbatch` script under `.runtime/runs/`,
submits it with `sbatch`, and records the accepted Slurm job ID in
`slurm_run_record.json`.

`monitor_slurm_job(run_record_path)` reloads that durable record and reconciles
it with `squeue`, `scontrol show job`, and `sacct`. When Slurm returns concrete
state, the record is updated with scheduler state, stdout/stderr paths, exit
code, and final state when terminal.

`cancel_slurm_job(run_record_path)` reloads the same durable record, requests
`scancel <job-id>`, and records that cancellation was requested. Final cancelled
state is confirmed by a later `monitor_slurm_job` reconciliation.

`prompt_and_run(prompt, manifest_sources=[], explicit_bindings={}, runtime_bindings={}, resource_request={}, execution_profile="local", runtime_image={})`
remains available for existing clients. It performs the same prepare-then-run
sequence and returns the artifact path alongside the execution summary.

Resource policy is frozen before execution. CPU, memory, queue, walltime, and
runtime image choices are recorded for review and replay; local execution uses
the explicit handler map, while Slurm execution uses the saved profile and
resource spec to render `sbatch` directives.

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
[src/flytetest/mcp_contract.py](/home/rmeht/Projects/flyteTest/src/flytetest/mcp_contract.py).

## Scope Boundary

The MCP server only executes targets that have explicit local node handlers.
The handler map covers the original three runnable targets, BUSCO QC, EggNOG,
and the three individual AGAT post-processing slices.
Broader registered stages such as EVM, PASA refinement, repeat filtering,
`table2asn`, Slurm retry/resubmission, and composed downstream pipelines should be
enabled only after their recipe inputs, runtime bindings, and local handlers
are made explicit.

## Planned Next Slice

Milestone 11 enabled the individual EggNOG and AGAT recipe targets using the
same explicit input-binding pattern that BUSCO demonstrated. A composed
EggNOG-plus-AGAT pipeline, `table2asn`, Slurm, and database-backed discovery
remain future work.

Milestone 16 added lifecycle reconciliation and cancellation from the durable
run record without reworking submission. Milestone 18 should build retry and
resubmission policy on top of that run history.
