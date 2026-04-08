# MCP Recipe Surface

This page documents the current MCP stdio tool surface for FLyteTest. It is a
tool-provider interface, not a chat agent and not the full workflow catalog.

The MCP-capable client owns the conversation. FLyteTest exposes tools that let
the client inspect supported targets, prepare a frozen recipe from a prompt, or
run a saved recipe locally.

## Runnable Targets

Day-one local recipe execution is intentionally limited to:

- workflow: `ab_initio_annotation_braker3`
- workflow: `protein_evidence_alignment`
- task: `exonerate_align_chunk`

Other registered workflows may still be visible in the registry and typed
planner, but they need explicit local node handlers before they become runnable
MCP targets.

## Tools

- `list_entries`
- `plan_request`
- `prepare_run_recipe`
- `run_local_recipe`
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

Day-one runnable prompts must include explicit local file paths. The current
MCP surface does not perform automatic path discovery, remote lookup, generic
orchestration, or Slurm submission.

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

`prepare_run_recipe(prompt)` returns the typed plan plus the absolute path to a
saved recipe artifact under `.runtime/specs/`.

`run_local_recipe(artifact_path)` loads that artifact and executes it through
`LocalWorkflowSpecExecutor` with the server's day-one handler map.

`prompt_and_run(prompt)` remains available for existing clients. It performs
the same prepare-then-run sequence and returns the artifact path alongside the
execution summary.

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
The day-one handler map covers the original three runnable targets. Broader
registered stages such as EVM, PASA refinement, repeat filtering, BUSCO,
EggNOG, AGAT, and `table2asn` should be enabled only after their recipe inputs,
runtime bindings, and local handlers are made explicit.

## Planned Next Slice

The next planned MCP expansion is BUSCO recipe enablement. That work should add
an explicit recipe-preparation input contract for prior manifest sources,
serialized planner bindings, and runtime bindings before adding
`annotation_qc_busco` to the local handler map.

Until that slice lands, BUSCO may be recognized by typed planning, but it is not
part of the runnable MCP handler set.
