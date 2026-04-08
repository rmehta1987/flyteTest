# FLyteTest

FLyteTest is a prompt-driven Flyte v2 project for turning bioinformatics
pipelines into reusable biology-facing tasks and workflows. The long-term goal
is for users to describe an analysis in natural language, have the system select
or generate a replayable workflow from registered biological stages, and run it
locally or in HPC environments, including Slurm-oriented deployments when the
required runtime context is available.

Current implementation is narrower and intentionally reproducible: the repo
implements genome-annotation workflows through EggNOG functional annotation
after BUSCO-based QC, PASA-based post-EVM gene-model refinement, and repeat
filtering, plus the AGAT statistics, conversion, and cleanup slices around the
EggNOG-annotated and AGAT-converted GFF3 bundles. `table2asn` submission
preparation and broad Slurm orchestration remain deferred.

## Current Status

- Active biological milestone: `AGAT post-processing after EggNOG`
- Active architecture milestone: `realtime` refactor Milestones 0 through 14
  and Milestone 16 are complete; Milestone 18 Slurm retry/resubmission is next
  on the Slurm lane
- Implemented biological scope: transcript evidence, PASA align/assemble,
  TransDecoder, protein evidence, tutorial-backed BRAKER3, corrected pre-EVM
  contract assembly, deterministic EVM execution, PASA post-EVM refinement,
  repeat filtering cleanup, BUSCO-based annotation QC, EggNOG functional
  annotation, and the AGAT statistics, conversion, and cleanup slices
- Deferred biological scope: optional `table2asn` submission preparation
- Deferred execution scope: Slurm retry, resumability, remote/indexed
  discovery, and arbitrary Python task-code generation

Important terminology:

- `Deterministic` means reproducible, typed, inspectable, and replayable.
- `Dynamic` workflow creation is still a project goal when the generated result
  is a saved `WorkflowSpec` / `BindingPlan` artifact or a composition from
  registered stages with explicit assumptions.

## How To Navigate

Use this README for the project story, current scope, and runnable entrypoints.
Use the more specific docs when you need detail:

- [AGENTS.md](/home/rmeht/Projects/flyteTest/AGENTS.md): repo rules, biological pipeline constraints, and agent behavior
- [DESIGN.md](/home/rmeht/Projects/flyteTest/DESIGN.md): architecture target and terminology
- [docs/braker3_evm_notes.md](/home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md): biological source notes and stage ordering
- [docs/capability_maturity.md](/home/rmeht/Projects/flyteTest/docs/capability_maturity.md): current platform capability snapshot
- [docs/refactor_completion_checklist.md](/home/rmeht/Projects/flyteTest/docs/refactor_completion_checklist.md): notes-faithful pipeline milestone gate
- [docs/realtime_refactor_checklist.md](/home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md): architecture-refactor completion gate
- [docs/realtime_refactor_submission_prompt.md](/home/rmeht/Projects/flyteTest/docs/realtime_refactor_submission_prompt.md): handoff prompt for future architecture work
- [docs/realtime_refactor_plans/README.md](/home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md): plan-history workspace, not current implementation status
- [docs/tool_refs/README.md](/home/rmeht/Projects/flyteTest/docs/tool_refs/README.md): tool-stage context for implementation and prompt planning
- [docs/tool_refs/stage_index.md](/home/rmeht/Projects/flyteTest/docs/tool_refs/stage_index.md): stage-oriented entrypoint into tool references
- [docs/tutorial_context.md](/home/rmeht/Projects/flyteTest/docs/tutorial_context.md): Galaxy-backed fixture and smoke-test context
- [src/flytetest/registry.py](/home/rmeht/Projects/flyteTest/src/flytetest/registry.py): exact supported task and workflow names

Reading rule for agents: the notes define biological order and command context;
the registry and current code define what is actually implemented and runnable.

## Pipeline Story

The working biological source notes describe this genome-annotation path:

```mermaid
flowchart TD
    A[Transcript evidence<br/>Trinity de novo<br/>STAR alignment<br/>BAM merge<br/>Genome-guided Trinity<br/>StringTie]
    B[PASA transcript prep<br/>seqclean<br/>SQLite config<br/>PASA align/assemble]
    C[TransDecoder<br/>coding prediction from PASA]
    D[Protein evidence<br/>local FASTA staging<br/>Exonerate chunks<br/>EVM-ready GFF3]
    E[BRAKER3<br/>ab initio prediction<br/>braker.gff3 normalization]
    F[EVM input prep<br/>transcripts.gff3<br/>predictions.gff3<br/>proteins.gff3]
    G[EVidenceModeler<br/>consensus annotation]
    H[PASA post-EVM refinement<br/>annotation-update rounds]
    I[Repeat filtering<br/>RepeatMasker conversion<br/>gffread proteins<br/>funannotate cleanup]
    J[BUSCO QC<br/>repeat-filtered proteins]
    K[EggNOG functional annotation<br/>tx2gene bridge<br/>annotated GFF3]
    L[AGAT post-processing<br/>statistics, conversion, cleanup]
    M[Deferred stage<br/>table2asn]

    A --> B --> C --> F
    D --> F
    E --> F
    F --> G --> H --> I --> J --> K --> L --> M
```

The corrected pre-EVM contract is a key boundary:

- `transcripts.gff3` comes from PASA assemblies GFF3
- `predictions.gff3` comes from `braker.gff3` plus the PASA-derived
  TransDecoder genome GFF3
- `proteins.gff3` comes from Exonerate-derived protein evidence GFF3

The repo currently implements through EggNOG functional annotation after
repeat filtering and the AGAT statistics, conversion, and cleanup slices around
the EggNOG-annotated and AGAT-converted GFF3 bundles. `table2asn` remains
intentionally out of scope.

## Current Workflows

The original [flyte_rnaseq_workflow.py](/home/rmeht/Projects/flyteTest/flyte_rnaseq_workflow.py)
file remains the compatibility entrypoint for `flyte run`. The implementation
now lives under [src/flytetest/](/home/rmeht/Projects/flyteTest/src/flytetest).

| Workflow | Biological role | Current boundary |
| --- | --- | --- |
| `rnaseq_qc_quant` | Legacy FastQC + Salmon baseline | Separate from the active annotation pipeline |
| `transcript_evidence_generation` | Trinity, STAR, BAM merge, genome-guided Trinity, StringTie | Single paired-end sample, not full multi-sample notes path |
| `pasa_transcript_alignment` | PASA transcript preparation and align/assemble | Consumes transcript-evidence bundle |
| `transdecoder_from_pasa` | Coding prediction from PASA assemblies | Inferred TransDecoder command shape |
| `protein_evidence_alignment` | Local protein evidence with Exonerate | Local protein FASTAs only, no automatic UniProt/RefSeq download |
| `ab_initio_annotation_braker3` | BRAKER3 ab initio prediction | Tutorial-backed local BRAKER3 runtime model |
| `consensus_annotation_evm_prep` | Assemble `transcripts.gff3`, `predictions.gff3`, and `proteins.gff3` | Stops before EVM execution |
| `consensus_annotation_evm` | Deterministic EVM execution and recombination | Consumes existing pre-EVM bundle |
| `annotation_refinement_pasa` | PASA post-EVM update rounds | Consumes PASA and EVM result bundles |
| `annotation_repeat_filtering` | RepeatMasker/funannotate cleanup | Consumes PASA update bundle plus explicit RepeatMasker `.out` |
| `annotation_qc_busco` | BUSCO QC on repeat-filtered proteins | Final implemented QC boundary |
| `annotation_functional_eggnog` | EggNOG functional annotation on repeat-filtered proteins | Consumes BUSCO-ready protein boundary and a local EggNOG data directory |
| `annotation_postprocess_agat` | AGAT statistics on the EggNOG-annotated GFF3 bundle | Consumes the EggNOG-annotated GFF3 boundary |
| `annotation_postprocess_agat_conversion` | AGAT conversion on the EggNOG-annotated GFF3 bundle | Consumes the EggNOG-annotated GFF3 boundary |
| `annotation_postprocess_agat_cleanup` | Notes-backed AGAT cleanup on the converted GFF3 bundle | Consumes the AGAT conversion results; `table2asn` stays deferred |

## Quick Start

Use the repo-local virtualenv commands when possible:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-cluster.txt
```

Legacy QC and quantification baseline:

```bash
.venv/bin/flyte run --local flyte_rnaseq_workflow.py rnaseq_qc_quant \
  --ref data/transcriptomics/ref-based/transcriptome.fa \
  --left data/transcriptomics/ref-based/reads_1.fq.gz \
  --right data/transcriptomics/ref-based/reads_2.fq.gz
```

BRAKER3 tutorial-backed smoke shape:

```bash
.venv/bin/flyte run --local flyte_rnaseq_workflow.py ab_initio_annotation_braker3 \
  --genome data/braker3/reference/genome.fa \
  --rnaseq_bam_path data/braker3/rnaseq/RNAseq.bam \
  --protein_fasta_path data/braker3/protein_data/fastas/proteins.fa
```

Protein-evidence smoke shape:

```bash
.venv/bin/flyte run --local flyte_rnaseq_workflow.py protein_evidence_alignment \
  --genome data/braker3/reference/genome.fa \
  --protein_fastas data/braker3/protein_data/fastas/proteins.fa
```

BUSCO QC after repeat filtering:

```bash
.venv/bin/flyte run --local flyte_rnaseq_workflow.py annotation_qc_busco \
  --repeat_filter_results /path/to/results/repeat_filter_results_YYYYMMDD_HHMMSS \
  --busco_lineages_text eukaryota_odb10,metazoa_odb10,insecta_odb10,arthropoda_odb10,diptera_odb10
```

EggNOG functional annotation:

```bash
.venv/bin/flyte run --local flyte_rnaseq_workflow.py annotation_functional_eggnog \
  --repeat_filter_results /path/to/results/repeat_filter_results_YYYYMMDD_HHMMSS \
  --eggnog_data_dir /path/to/eggnog_data \
  --eggnog_database Diptera \
  --eggnog_cpu 24
```

AGAT statistics:

```bash
.venv/bin/flyte run --local flyte_rnaseq_workflow.py annotation_postprocess_agat \
  --eggnog_results /path/to/results/eggnog_results_YYYYMMDD_HHMMSS \
  --annotation_fasta_path /path/to/repeatmasked.fa
```

AGAT conversion:

```bash
.venv/bin/flyte run --local flyte_rnaseq_workflow.py annotation_postprocess_agat_conversion \
  --eggnog_results /path/to/results/eggnog_results_YYYYMMDD_HHMMSS
```

AGAT cleanup:

```bash
.venv/bin/flyte run --local flyte_rnaseq_workflow.py annotation_postprocess_agat_cleanup \
  --agat_conversion_results /path/to/results/agat_conversion_results_YYYYMMDD_HHMMSS
```

Most workflows require external bioinformatics tools or `*_sif` container image
paths. Synthetic tests remain the normal validation path when those binaries are
not installed.

## Architecture Status

The `realtime` refactor keeps the project resolver-first and manifest-first,
not database-first. The implemented planning path is:

```text
natural-language prompt
  -> biology-level goal
  -> planner-facing types
  -> local manifest-backed resolver
  -> registry compatibility metadata
  -> WorkflowSpec / BindingPlan preview or saved artifact
  -> controlled local saved-spec execution through explicit handlers
```

Implemented architecture layers:

- [planner_types.py](/home/rmeht/Projects/flyteTest/src/flytetest/planner_types.py): biology-facing planner dataclasses
- [planner_adapters.py](/home/rmeht/Projects/flyteTest/src/flytetest/planner_adapters.py): adapters from current assets and manifests into planner-facing types
- [types/assets.py](/home/rmeht/Projects/flyteTest/src/flytetest/types/assets.py): local asset dataclasses with generic compatibility names and legacy aliases for replay
- [specs.py](/home/rmeht/Projects/flyteTest/src/flytetest/specs.py): `TaskSpec`, `WorkflowSpec`, `BindingPlan`, runtime, resource, and generated-entity metadata
- [resolver.py](/home/rmeht/Projects/flyteTest/src/flytetest/resolver.py): local manifest-backed resolution from explicit bindings, result directories, and result bundles
- [registry.py](/home/rmeht/Projects/flyteTest/src/flytetest/registry.py): static registry plus additive compatibility metadata for current workflows
- [planning.py](/home/rmeht/Projects/flyteTest/src/flytetest/planning.py): typed prompt planning plus explicit-path and explicit recipe input bindings
- [spec_artifacts.py](/home/rmeht/Projects/flyteTest/src/flytetest/spec_artifacts.py): saved replayable `WorkflowSpec` plus `BindingPlan` JSON artifacts
- [spec_executor.py](/home/rmeht/Projects/flyteTest/src/flytetest/spec_executor.py): local saved-spec execution through caller-provided registered handlers

Current architecture limits:

- the runnable MCP surface executes only its explicit local handler targets
- dynamic workflow creation currently stops at typed spec previews, saved spec
  artifacts, and controlled local saved-spec execution
- the resolver is local and file-based; remote or indexed discovery remains
  future work
- saved-spec execution is local and handler-based; it does not auto-load every
  checked-in Flyte workflow
- Slurm/HPC support now has a deterministic `sbatch` submission path for frozen
  Slurm-profile recipes, with lifecycle reconciliation and cancellation
  recorded under `.runtime/runs/`. Retry and resumability remain future work.

## MCP Recipe Surface

The MCP server is a stdio tool provider, not a chat agent. It now prepares
saved `WorkflowSpec` recipes before local execution or Slurm submission.
Current local MCP execution is intentionally limited to these individual
targets:

- workflow: `ab_initio_annotation_braker3`
- workflow: `protein_evidence_alignment`
- task: `exonerate_align_chunk`
- workflow: `annotation_qc_busco`
- workflow: `annotation_functional_eggnog`
- workflow: `annotation_postprocess_agat`
- workflow: `annotation_postprocess_agat_conversion`
- workflow: `annotation_postprocess_agat_cleanup`

Supported tools:

- `list_entries`
- `plan_request`
- `prepare_run_recipe`
- `run_local_recipe`
- `run_slurm_recipe`
- `monitor_slurm_job`
- `cancel_slurm_job`
- `prompt_and_run`

Launch command:

```bash
env PYTHONPATH=src .venv/bin/python -m flytetest.server
```

Current MCP behavior:

- `plan_request` returns the typed planning payload used for recipe preparation
- `prepare_run_recipe` saves a frozen recipe under `.runtime/specs/`
- `run_local_recipe` executes a previously saved recipe through explicit local
  handlers
- `run_slurm_recipe` submits a previously saved Slurm-profile recipe with
  `sbatch`, writes the generated script and a durable run record under
  `.runtime/runs/`, and records the accepted Slurm job ID
- `monitor_slurm_job` reconciles the durable Slurm run record with `squeue`,
  `scontrol show job`, and `sacct`, then persists observed scheduler state,
  stdout/stderr paths, exit code, and final state when available
- `cancel_slurm_job` requests cancellation with `scancel` from the durable run
  record and records the cancellation request for later reconciliation
- `prompt_and_run` remains available as a compatibility alias over prepare then
  run
- `prepare_run_recipe` and `prompt_and_run` accept optional `manifest_sources`,
  `explicit_bindings`, `runtime_bindings`, `resource_request`,
  `execution_profile`, and `runtime_image` arguments
- `manifest_sources` must be `run_manifest.json` paths or result directories
  containing one
- BUSCO and EggNOG recipe preparation can resolve a
  `QualityAssessmentTarget` from a repeat-filtering or compatible QC manifest,
  or accept one directly as a serialized planner binding
- AGAT statistics and conversion recipe preparation can resolve a
  `QualityAssessmentTarget` from an EggNOG result manifest
- AGAT cleanup recipe preparation can resolve a `QualityAssessmentTarget` from
  an AGAT conversion result manifest
- BUSCO runtime settings such as `busco_lineages_text`, `busco_sif`, and
  `busco_cpu`, EggNOG settings such as `eggnog_data_dir`, `eggnog_sif`,
  `eggnog_cpu`, and `eggnog_database`, and AGAT settings such as
  `annotation_fasta_path` and `agat_sif` are frozen into the saved recipe
  rather than inferred from prompt text
- resource settings such as `cpu`, `memory`, `queue`, and `walltime`, the
  selected execution profile, and optional runtime image policy are frozen into
  the saved recipe as structured metadata; `local` recipes run through local
  handlers, and `slurm` recipes can be submitted through `run_slurm_recipe`
- the runnable MCP surface currently includes
  `ab_initio_annotation_braker3`, `protein_evidence_alignment`,
  `exonerate_align_chunk`, `annotation_qc_busco`,
  `annotation_functional_eggnog`, `annotation_postprocess_agat`,
  `annotation_postprocess_agat_conversion`, and
  `annotation_postprocess_agat_cleanup`
- EggNOG and AGAT remain individual MCP recipe targets in this slice; a
  composed EggNOG-plus-AGAT pipeline, `table2asn`, Slurm retry/resubmission,
  resumability, and database-backed asset discovery remain deferred
- additional registered workflows require explicit local handlers before they
  are exposed as runnable MCP targets

For the machine-readable server contract, see
[mcp_contract.py](/home/rmeht/Projects/flyteTest/src/flytetest/mcp_contract.py)
and [docs/mcp_showcase.md](/home/rmeht/Projects/flyteTest/docs/mcp_showcase.md).

## Fixtures And Tests

Canonical lightweight fixture roots:

- `data/transcriptomics/ref-based/reads_1.fq.gz`
- `data/transcriptomics/ref-based/reads_2.fq.gz`
- `data/transcriptomics/ref-based/transcriptome.fa`
- `data/braker3/reference/genome.fa`
- `data/braker3/rnaseq/RNAseq.bam`
- `data/braker3/protein_data/fastas/proteins.fa`
- `data/braker3/protein_data/fastas/proteins_extra.fa`

Use [scripts/rcc/download_minimal_fixtures.sh](/home/rmeht/Projects/flyteTest/scripts/rcc/download_minimal_fixtures.sh)
to restore the lightweight tutorial-backed smoke files on a cluster checkout.
Use [scripts/rcc/run_minimal_pasa_smoke.sh](/home/rmeht/Projects/flyteTest/scripts/rcc/run_minimal_pasa_smoke.sh)
to reuse the Trinity smoke FASTA for the PASA prep smoke path on the cluster.
Use [scripts/rcc/check_minimal_pasa_smoke.sh](/home/rmeht/Projects/flyteTest/scripts/rcc/check_minimal_pasa_smoke.sh)
to verify the PASA prep smoke artifacts after the job finishes.
Use [docs/tutorial_context.md](/home/rmeht/Projects/flyteTest/docs/tutorial_context.md)
for Galaxy tutorial mappings, fixture provenance, and smoke-test planning.
Use synthetic tests when external binaries or lineage datasets are unavailable.

## HPC And Containers

Implemented workflows support optional Apptainer/Singularity execution through
stage-specific `*_sif` arguments such as:

- `fastqc_sif`
- `salmon_sif`
- `star_sif`
- `samtools_sif`
- `trinity_sif`
- `stringtie_sif`
- `pasa_sif`
- `repeat_filter_sif`
- `transdecoder_sif`
- `exonerate_sif`
- `braker3_sif`
- `evm_sif`
- `busco_sif`
- `eggnog_sif`
- `agat_sif`

If a `*_sif` path is empty, tasks use native binaries. If provided, tasks use
`apptainer exec` or `singularity exec` with deterministic bind mounts for the
relevant input and output parent directories.

Slurm support now starts with a filesystem-backed `sbatch` submission path:
prepare a recipe with execution profile `slurm`, then call `run_slurm_recipe`
on the saved artifact. The submission record captures the Slurm job ID,
generated script path, stdout and stderr log patterns, selected execution
profile, and resource spec under `.runtime/runs/`. `monitor_slurm_job`
reconciles the record with `squeue`, `scontrol show job`, and `sacct`, while
`cancel_slurm_job` records explicit `scancel` requests. Retry and resumability
remain later milestones.

## Assumptions

- The current SDK in this repo is `flyte==2.0.10`, and `TaskEnvironment`
  exposes `@env.task` but not `@env.workflow`.
- `flyte_rnaseq_workflow.py` remains a thin compatibility module for
  `flyte run`.
- `src/flytetest/types/` is a local modeling layer, not a full remote asset
  platform. It now exposes generic compatibility names such as
  `AbInitioResultBundle`, `RnaSeqAlignmentResult`, and
  `CleanedTranscriptDataset` while keeping legacy names readable.
- The planner-facing public contract starts in
  `src/flytetest/planner_types.py`.
- Tool references are concise repo-local planning references, not replacements
  for official tool manuals.
- The next biological milestone should stay downstream of AGAT cleanup, keep
  `table2asn` separate from post-processing, and avoid reopening the validated
  transcript-to-PASA-to-EVM-to-post-EVM-to-repeat-filter contracts.
