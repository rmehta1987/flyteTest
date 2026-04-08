# FLyteTest: Full Design Specification

A prompt-driven biology workflow platform for composing, validating, and
executing curated bioinformatics pipelines through natural language and typed
run recipes.

## Table of Contents

1. Goals and Non-Goals
2. Landscape and Positioning
3. Architecture Overview
4. Core Design Examples
5. Biological Pipeline Scope
6. Prompting and MCP Interface
7. Execution Strategy
8. Validation and Testing
9. Implementation Roadmap
10. Repository Layout
11. Open Questions and Risks

## Related Documents

| Document | Purpose |
| --- | --- |
| `AGENTS.md` | Repository rules and biological pipeline constraints |
| `README.md` | Current user-facing scope and runnable entrypoints |
| `docs/braker3_evm_notes.md` | Biological source notes and pipeline order |
| `docs/mcp_showcase.md` | Current MCP surface and prompt behavior |
| `docs/capability_maturity.md` | Capability snapshot by area |
| `docs/realtime_refactor_checklist.md` | Architecture refactor status |
| `docs/tutorial_context.md` | Prompting and fixture context |
| `.codex/testing.md` | Validation and testing expectations |

## Overview

The primary objective of FLyteTest is to minimize the computational and
engineering burden on scientists by enabling dynamic composition of
bioinformatics pipelines from natural-language requests. The platform uses an
agent-assisted planning layer over a curated registry of established tools,
typed tasks, and reviewed workflow stages, allowing researchers to explore
biological questions without writing boilerplate workflow code.

Ultimately, a user should be able to prompt the system with requests such as:

> "Build an RNA-seq QC and quantification workflow that runs FastQC on paired-end
> reads and uses Salmon to build a transcriptome index and quantify the reads,
> allocating 6 CPU cores and 32 GB of memory."

For supported workflow families, the system should turn that request into a
biology-aware plan, resolve required inputs from explicit bindings or prior
manifests, select or compose registered workflow stages, and bind explicit
runtime resources. The result should be a saved, inspectable run recipe: a
record of what steps will run, what each step consumes and produces, which
containers and resources it will use, and how the outputs trace back to the
original prompt and input data. Dynamic planning happens before execution; once
the run recipe is created, execution follows that frozen record so the
resulting pipelines remain transparent and reproducible.

To achieve this, the architecture is built on three core pillars:

### 1. Dynamic, Strongly Typed Composition From Registered Building Blocks

The agent-assisted planner dynamically assembles the correct sequence of
bioinformatics tools by mapping user intent to ground-truth, pre-validated
workflow templates or by chaining registered tasks and reference workflows.
Every generated or selected workflow must declare strongly typed inputs and
outputs, preventing incompatible assets such as BAM files from being passed to
tools expecting FASTA inputs. Runtime requirements, including CPU, memory,
scheduler hints, and container images, are bound explicitly before execution.

### 2. Execution With Comprehensive Traceability

The platform bridges the planning layer with robust compute infrastructure
through explicit execution profiles, including local development runs,
containerized runs, and Slurm-oriented HPC deployments. Because workflows
may be dynamically composed, the system maintains an automated audit trail for
every run:

- **Prompt-to-result tracking:** The system records the pathway from the user's
  natural-language prompt to the final biological output, including the selected
  or generated workflow, resolved input files, and produced result bundle.
- **Version-locked environments:** Tools run inside explicitly defined
  containers when container paths are supplied. The platform records the exact
  container image used for each task, avoiding hidden local dependency drift.
- **Automated execution logs:** Each task records standard output and error logs,
  result paths, and, when running under an HPC profile, scheduler job IDs and
  actual compute resources used.

This allows researchers and reviewers to retrieve the reproducible execution
graph for a finding without relying on manual record-keeping.

### 3. Reproducibility And Scientific Grounding

Natural-language interpretation may be dynamic, but the executable plan must be
frozen before launch. Given the same saved spec, input assets, container images,
tool databases, and execution profile, the platform should produce the same
result bundle and manifest. The system must not introduce AI-generated
biological assumptions, hidden data modifications, or unreviewable workflow
steps to make results superficially match expectations. Scientific validation,
pipeline transparency, and reproducible execution remain paramount.

## 1. Goals and Non-Goals

### Goals

- Enable natural-language planning for supported bioinformatics workflow families.
- Compose pipelines from a curated registry of typed tasks and reviewed workflow stages.
- Preserve the current notes-faithful genome annotation baseline through BUSCO QC.
- Represent dynamically composed workflows as saved, inspectable run recipes rather than opaque generated code.
- Resolve inputs from explicit bindings, prior manifests, and registered result bundles.
- Treat Slurm HPC execution as a first-class project goal, including natural-language resource requests, explicit CPU and memory binding, queue or partition selection, and generated `sbatch` run artifacts.
- Support offline compute-node environments by staging containers, tool databases, input manifests, and runtime configuration before job execution.
- Produce traceable result bundles with machine-readable manifests that record prompt provenance, containers, resources, scheduler metadata, and outputs.

### Non-Goals

- Generating ungrounded workflows from arbitrary biology prompts. New workflows
  may be dynamically composed only when their steps can be mapped to established,
  registered tasks or reviewed workflow stages.
- Generating free-form Python task code as the default user-facing behavior.
- Replacing current `flyte run` compatibility entrypoints.
- Treating MCP as the planner itself rather than as an interface layer.
- Submitting or monitoring arbitrary cluster jobs without a frozen, inspectable run recipe.
- Assuming compute nodes have internet access.
- Using a database or remote asset index as a prerequisite for the current architecture.
- Inventing unsupported biological steps when source notes or tool references are incomplete.

## 2. Landscape and Positioning

Bioinformatics workflow users already have strong execution systems, including
Nextflow, Snakemake, and Flyte. FLyteTest is not trying to replace those systems
as a generic workflow language. Its goal is to add a biology-aware planning and
composition layer on top of curated, reproducible workflow building blocks.

| System | Strength | Limitation FLyteTest Addresses |
| --- | --- | --- |
| Nextflow | Mature workflow execution across local, cloud, and HPC environments | Users still generally work through workflow code, configuration files, and channel-level concepts rather than biology-facing prompt intent |
| Snakemake | Transparent file-oriented DAGs and strong local/HPC usability | Rules are powerful but still require users to encode analysis logic and file dependencies manually |
| Flyte | Typed workflow execution, task isolation, and containerized reproducibility | It does not by itself provide a biology-specific prompt planner, manifest-backed biological asset resolver, or curated annotation-stage registry |
| Ad hoc scripts and notebooks | Flexible and familiar for exploratory analysis | Hard to replay, audit, compose, or transfer across local and HPC environments |
| General AI agents | Flexible natural-language interaction | Without a curated registry and frozen run recipes, they can invent unsupported steps or produce unreproducible workflows |

FLyteTest fills the gap between workflow engines and natural-language
scientific intent. It uses AI-assisted planning to interpret a request, but it
grounds every runnable workflow in established tasks, approved workflow stages,
typed inputs and outputs, explicit containers, resource choices, and saved
records.

The intended user experience is:

```text
Natural-language request
  -> biology-aware plan
  -> registered task/workflow composition
  -> saved run recipe
  -> local or Slurm-oriented execution
  -> traceable result bundle
```

The project's differentiator is not that it can create arbitrary pipelines from
scratch. The differentiator is that it can dynamically compose supported
bioinformatics workflows while preserving the reproducibility expectations of
publication-grade computational biology.

## 3. Architecture Overview

FLyteTest is organized as a layered planning and execution system. Natural
language is accepted at the boundary, but execution is driven by strongly typed,
inspectable run records.

```text
Natural-language request
    |
    v
Intent planning
    - identify the biological goal
    - identify the requested workflow family
    - interpret requested runtime preferences
    |
    v
Strong datatypes
    - define what each step is allowed to consume and produce
    - prevent incompatible files or result bundles from being connected
    - allow new biological data categories to be added as the platform grows
    |
    v
Input and output resolution
    - use explicit user-provided paths
    - reuse outputs from prior run records
    - connect compatible outputs to downstream workflow inputs
    |
    v
Curated workflow catalog
    - registered tasks
    - reviewed workflow stages
    - supported input and output types
    - allowed composition rules
    |
    v
Run recipe
    - selected registered workflow, or
    - composed workflow from registered stages, or
    - generated inspectable DAG from established tasks
    |
    v
Execution binding
    - input paths
    - output locations
    - container images
    - CPU and memory
    - Slurm queue or partition
    - scheduler-specific settings
    |
    v
Execution
    - local Flyte run
    - local saved run recipe execution
    - containerized execution
    - Slurm job submission, scheduling, and monitoring
    |
    v
Result bundle
    - biological outputs
    - run_manifest.json
    - task logs
    - containers used
    - resources requested and used
    - scheduler job IDs when applicable
    - links back to the prompt, run recipe, and input data
```

The central invariant is:

> Dynamic interpretation happens before execution. Execution only consumes a
> frozen run recipe with explicit inputs, outputs, resources, containers,
> assumptions, and scheduler settings.

This separation lets the system support natural-language interaction without
turning execution into an unreviewable agent action. The planner may interpret a
request dynamically, but the executor should not improvise. It should run the
registered workflow, composed workflow, or generated DAG that was saved in the
run recipe.

## 4. Core Design Examples

This section shows the shape of the system in short examples. The examples are
not full implementations, but they should make the data flow easy to follow.

### 4.1 Strong Datatypes

Strong datatypes describe what a value means biologically, not just what file
it came from.

```python
@dataclass(frozen=True)
class ReferenceGenome:
    """A genome that downstream tools may index, align against, or annotate."""

    fasta_path: Path
    organism_name: str | None = None
    source_run_manifest: Path | None = None


@dataclass(frozen=True)
class ReadSet:
    """A paired RNA-seq read set with enough metadata for planning."""

    sample_id: str
    left_reads: Path
    right_reads: Path


@dataclass(frozen=True)
class TranscriptEvidenceSet:
    """Evidence produced from RNA-seq assembly and alignment steps."""

    reference_genome: ReferenceGenome
    read_sets: tuple[ReadSet, ...]
    merged_bam: Path | None = None
    stringtie_gtf: Path | None = None
    source_run_manifest: Path | None = None
```

The datatype catalog can grow over time, but only when a new type helps describe
a real biological boundary.

### 4.2 Tool-Level Task Example

A task should represent one biological tool invocation or one deterministic
transformation.

```python
@transcript_evidence_env.task
def star_align_sample(
    genome_index: Dir,
    left_reads: File,
    right_reads: File,
    sample_id: str,
    star_threads: int = 8,
    star_sif: str = "",
) -> Dir:
    """Align one paired-end RNA-seq sample to a prepared STAR genome index."""

    index_dir = require_path(Path(genome_index.download_sync()), "STAR genome index")
    left_path = require_path(Path(left_reads.download_sync()), "Left reads")
    right_path = require_path(Path(right_reads.download_sync()), "Right reads")
    out_dir = make_stage_output_dir("star_align_sample", sample_id=sample_id)
    run_tool(
        ["STAR", "--genomeDir", str(index_dir), "--readFilesIn", str(left_path), str(right_path), "--runThreadN", str(star_threads), "--outFileNamePrefix", str(out_dir / f"{sample_id}.")],
        sif=star_sif,
        bind_paths=[index_dir, left_path.parent, right_path.parent, out_dir],
    )
    return Dir.from_local_sync(str(out_dir))
```

### 4.3 Workflow Example

A workflow should show the biological steps in order by composing registered
tasks.

```python
@transcript_evidence_env.task
def transcript_evidence_generation(
    genome: File,
    left_reads: File,
    right_reads: File,
    sample_id: str,
    star_sif: str = "",
    samtools_sif: str = "",
    trinity_sif: str = "",
    stringtie_sif: str = "",
) -> Dir:
    """Generate transcript evidence from one paired-end RNA-seq sample."""

    de_novo_transcripts = trinity_denovo_assemble(
        left_reads=left_reads,
        right_reads=right_reads,
        sample_id=sample_id,
        trinity_sif=trinity_sif,
    )

    genome_index = star_genome_index(
        genome=genome,
        star_sif=star_sif,
    )

    aligned_bam = star_align_sample(
        genome_index=genome_index,
        left_reads=left_reads,
        right_reads=right_reads,
        sample_id=sample_id,
        star_sif=star_sif,
    )

    merged_bam = samtools_merge_bams(
        sample_bams=[aligned_bam],
        samtools_sif=samtools_sif,
    )

    genome_guided_transcripts = trinity_genome_guided_assemble(
        merged_bam=merged_bam,
        genome=genome,
        trinity_sif=trinity_sif,
    )

    stringtie_gtf = stringtie_assemble(
        merged_bam=merged_bam,
        stringtie_sif=stringtie_sif,
    )

    return collect_transcript_evidence_results(
        genome=genome,
        de_novo_transcripts=de_novo_transcripts,
        merged_bam=merged_bam,
        genome_guided_transcripts=genome_guided_transcripts,
        stringtie_gtf=stringtie_gtf,
    )
```

### 4.4 Saved Run Recipe Example

A run recipe is the frozen record created after dynamic planning and before
execution. It records the steps, inputs, outputs, containers, resources, and
links back to the prompt and input data.

```python
@dataclass(frozen=True)
class RunRecipe:
    """A saved, inspectable execution plan produced from a prompt."""

    recipe_id: str
    source_prompt: str
    workflow_name: str
    nodes: tuple[RunNode, ...]
    input_bindings: dict[str, Path]
    output_root: Path
    execution_profile: str
    resources: dict[str, ResourceRequest]
    containers: dict[str, Path]
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class RunNode:
    """One task or reviewed workflow stage in the planned run."""

    name: str
    registered_target: str
    inputs: dict[str, str]
    outputs: tuple[str, ...]


@dataclass(frozen=True)
class ResourceRequest:
    """The frozen resource request for one run node or workflow."""

    cpu: int
    memory_gb: int
    walltime: str | None = None
    partition: str | None = None
```

The planner may create this recipe dynamically, but execution should use the
saved recipe as-is.

### 4.5 Slurm Job Example

Slurm support should make FLyteTest feel closer to Nextflow or Snakemake on
HPC: the system should send jobs to the cluster, watch them, and cancel them
when needed from frozen run recipes. The target design should use the Flyte
Slurm plugin rather than inventing a separate Slurm runner. In that model,
Flyte owns the task graph and the Slurm agent handles the scheduler
interaction.

The Flyte Slurm plugin exposes two useful shapes for FLyteTest:

- `SlurmFunction` for running a Python Flyte task function through Slurm.
- `SlurmTask` / `SlurmRemoteScript` or `SlurmShellTask` for a prepared shell
  script when that is the better boundary.

The job settings still come from the saved run recipe. Natural-language
resource requests are interpreted before execution and then frozen into
`sbatch_conf`.

```python
from flytekit import task, workflow
from flytekitplugins.slurm import SlurmFunction


@dataclass(frozen=True)
class SlurmExecutionProfile:
    """Cluster settings chosen before the run starts."""

    partition: str
    cpus_per_task: int
    memory_gb: int
    walltime: str
    log_path: Path


def sbatch_conf_for_recipe(recipe: RunRecipe, profile: SlurmExecutionProfile) -> dict[str, str]:
    """Convert the frozen run recipe and profile into Slurm sbatch options."""

    return {
        "partition": profile.partition,
        "job-name": f"flytetest-{recipe.recipe_id}",
        "cpus-per-task": str(profile.cpus_per_task),
        "mem": f"{profile.memory_gb}G",
        "time": profile.walltime,
        "output": str(profile.log_path),
    }


@task(
    task_config=SlurmFunction(
        ssh_config={
            "host": "hpc-login.example.edu",
            "username": "researcher",
            "client_keys": ["~/.ssh/flytetest_slurm"],
        },
        sbatch_conf={
            "partition": "highmem",
            "job-name": "flytetest-transcript-evidence",
            "cpus-per-task": "16",
            "mem": "64G",
            "time": "08:00:00",
            "output": "/shared/flytetest/logs/transcript-evidence-%j.out",
        },
        script="""#!/usr/bin/env bash
set -euo pipefail

# The Flyte Slurm plugin inserts the task function at this placeholder.
# Do not reinterpret the original prompt inside the Slurm job.
{task.fn}
""",
    )
)
def run_registered_stage_on_slurm(recipe_path: str) -> str:
    """Execute one saved run recipe stage on a Slurm compute node."""

    recipe = load_run_recipe(recipe_path)
    verify_offline_inputs(recipe)
    result_dir = execute_registered_stage(recipe)
    return str(result_dir)


@workflow
def slurm_backed_workflow(recipe_path: str) -> str:
    """Submit the selected stage through the Flyte Slurm plugin."""

    return run_registered_stage_on_slurm(recipe_path=recipe_path)
```

The design should preserve Flyte's scheduler lifecycle: the Slurm agent submits
jobs with `srun` or `sbatch`, checks state with `scontrol show job <job-id>`,
and cancels jobs with `scancel`. FLyteTest should record those job IDs and
state changes in the run record alongside the prompt, inputs, containers, logs,
and outputs.

For offline compute-node environments, the Slurm task must verify that
containers, databases, input files, and the saved run recipe are staged on
filesystems visible to compute nodes before submission.

## 5. Biological Pipeline Scope

FLyteTest starts from a concrete genome-annotation pipeline rather than a
generic workflow abstraction. The current biological scope follows the order
captured in `docs/braker3_evm_notes.md`.

The platform should keep this order:

```text
Raw RNA-seq reads and genome setup
  -> transcript evidence generation
  -> PASA transcript alignment and assembly
  -> TransDecoder coding prediction
  -> protein evidence alignment
  -> BRAKER3 ab initio annotation
  -> EVM input preparation
  -> EVM consensus annotation
  -> PASA gene model updates
  -> repeat and transposable-element filtering
  -> BUSCO quality assessment
  -> functional annotation and statistics
  -> optional submission preparation
```

### 5.1 Transcript Evidence

Transcript evidence workflows should produce RNA-seq-derived evidence that can
feed PASA, TransDecoder, and consensus annotation.

Representative tools and tasks include Trinity de novo assembly, STAR genome
indexing and alignment, samtools BAM merge/sort/index, Trinity genome-guided
assembly, and StringTie transcript assembly. The workflow should keep raw-read
handling, alignment, assembly, and result collection visible as separate steps.

### 5.2 PASA and TransDecoder

PASA workflows should prepare transcript assemblies, align them to the genome,
and produce transcript models that can support later gene-model refinement.

Representative tools and tasks include PASA accession extraction, SeqClean,
PASA alignment and assembly, and TransDecoder coding prediction from PASA
assemblies.

These stages should record assumptions about PASA configuration, local database
setup, and runtime-specific dependencies.

### 5.3 Protein and Ab Initio Evidence

Protein and ab initio workflows should prepare independent evidence sources for
consensus annotation.

Representative tools and tasks include protein FASTA staging, Exonerate
chunked protein-to-genome alignment, conversion of Exonerate output to
EVM-ready GFF3, BRAKER3 ab initio prediction, and normalization of
`braker.gff3` for downstream review.

BRAKER3 should remain documented as a required upstream source for EVM while
avoiding unsupported claims about unimplemented BRAKER3 substeps.

### 5.4 Consensus Annotation and Refinement

Consensus annotation workflows should combine transcript, protein, and ab initio
evidence into a reviewed gene-model boundary.

Representative tools and tasks include EVM input preparation, EVM partitioning,
EVM command generation, EVM execution and recombination, and PASA gene model
update rounds.

The corrected pre-EVM inputs should stay explicit:

- `transcripts.gff3` from PASA assemblies
- `predictions.gff3` from BRAKER3 and PASA-derived TransDecoder predictions
- `proteins.gff3` from Exonerate-derived protein evidence

### 5.5 Repeat Filtering, QC, and Submission

Post-consensus workflows should clean, assess, annotate, and prepare the final
annotation for downstream use.

Representative tools and tasks include RepeatMasker output conversion,
funannotate repeat filtering, gffread protein extraction, BUSCO quality
assessment, EggNOG-mapper functional annotation, AGAT statistics and format
conversion, and optional `table2asn` submission preparation.

These stages should remain composable so users can request only the part of the
post-processing path they need.

## 6. Prompting and MCP Interface

FLyteTest treats natural language as the primary user-facing entrypoint, but not
as the execution mechanism. A prompt should be converted into a structured plan
that can be inspected, saved, executed, and replayed.

The MCP server is the main interface for conversational clients. It should expose
small, typed tools for planning, previewing, generating run recipes, launching
approved executions, and inspecting results. The client owns the conversation;
FLyteTest owns the workflow catalog, input/output resolution, run recipe
generation, and execution records.

### 6.1 Prompt Interpretation

A user prompt may describe:

- the biological goal
- the desired workflow family
- input datasets or prior result bundles
- desired outputs
- runtime preferences such as CPUs, memory, walltime, partition, or container
  choices
- execution mode, such as local, containerized, or Slurm-backed

Example:

```text
Build an RNA-seq QC and quantification workflow that runs FastQC on paired-end
reads and uses Salmon to build a transcriptome index and quantify the reads.
Use 6 CPU cores, 32 GB of memory, and run it on the normal Slurm partition.
```

The prompt interpreter should produce a structured planning result:

```python
@dataclass(frozen=True)
class PromptPlan:
    """The structured interpretation of one natural-language request."""

    original_prompt: str
    biological_goal: str
    workflow_family: str
    selected_targets: tuple[str, ...]
    resolved_inputs: dict[str, Path]
    missing_inputs: tuple[str, ...]
    resource_request: ResourceRequest | None
    execution_mode: str
    assumptions: tuple[str, ...]
    supported: bool
```

If the prompt asks for unsupported biology or missing resources, the planner
should return a clear decline or missing-input report instead of inventing steps.

### 6.2 MCP Tool Surface

The MCP interface should expose the system in small steps rather than one opaque
"do everything" call.

Target tools:

- `list_entries`: list registered tasks and workflows.
- `plan_request`: convert natural language into a structured plan.
- `prepare_run_recipe`: save an inspectable run recipe from a supported plan.
- `validate_run_recipe`: check inputs, outputs, containers, resources, and
  offline-compute assumptions.
- `run_local_recipe`: execute a saved run recipe locally when supported.
- `prepare_slurm_recipe`: convert a saved run recipe into a Slurm-backed Flyte
  execution plan.
- `submit_slurm_recipe`: submit a Slurm-backed recipe through the Flyte Slurm
  plugin after validation.
- `monitor_slurm_job`: inspect scheduler state, logs, and job IDs.
- `inspect_result`: read result manifests and summarize produced outputs.

The tool surface should remain stable and machine-readable. New tools should be
additive unless an intentional compatibility migration is documented.

### 6.3 MCP Resources

MCP resources should provide small, inspectable reference data for clients:

- `flytetest://scope`
- `flytetest://registered-workflows`
- `flytetest://example-prompts`
- `flytetest://execution-profiles`
- `flytetest://slurm-profile`
- `flytetest://run-recipes/<recipe_id>`
- `flytetest://result-manifests/<run_id>`

Resources should describe capabilities and saved records. They should not become
large logs, full datasets, or a substitute for result directories.

### 6.4 Prompt Safety Rules

The prompt layer must follow these rules:

- It may dynamically interpret intent and resource preferences.
- It may compose new workflows only from established, registered tasks or
  reviewed workflow stages.
- It must freeze execution into a saved run recipe before launching work.
- It must report missing inputs, unsupported stages, ambiguous matches, and
  offline-compute violations explicitly.
- It must not modify biological data to satisfy expected outcomes.
- It must not submit Slurm jobs from vague or unresolved resource requests.

## 7. Execution Strategy

FLyteTest separates planning from execution. Planning may be dynamic and
prompt-driven, but execution should be controlled by a saved run recipe with
explicit inputs, outputs, containers, resource requests, and scheduler settings.

The execution layer should support several modes without changing the biological
meaning of the workflow.

### 7.1 Local Execution

Local execution is the development and smoke-test path. It should remain useful
for small examples, fixture-backed tests, and workflows that can run on a single
machine.

Local execution should:

- run registered workflows through the Flyte entrypoint when possible
- support saved run recipes for composed workflows
- write the same result bundle and manifest structure expected from other
  execution modes
- use explicit `.venv/bin/...` commands in examples and generated scripts

### 7.2 Containerized Execution

Bioinformatics tools should not depend on whatever binaries happen to be
installed on a user's machine. Each task should be able to run natively for
local development or inside an explicitly supplied container image.

Containerized execution should:

- support Apptainer or Singularity image paths for cluster portability
- record the exact container path or image identifier used for each task
- bind only the needed input and output directories
- fail clearly when a required container or runtime is missing

### 7.3 Flyte-Managed Execution

Flyte should own the workflow graph and task-level execution semantics. FLyteTest
adds the biology-aware planning layer, but it should not bypass Flyte when a
Flyte-native task or workflow execution path is available.

Flyte-managed execution should:

- preserve typed task and workflow boundaries
- keep task isolation and result passing explicit
- allow task-level resource and runtime settings
- keep compatibility with existing `flyte run` entrypoints

### 7.4 Slurm-Backed Execution

Slurm is a first-class execution goal. FLyteTest should support Slurm through the
Flyte Slurm plugin so that scheduling, monitoring, and cancellation are handled
as part of the Flyte execution model rather than as hidden ad hoc shell
behavior.

Slurm-backed execution should:

- translate a saved run recipe and resource request into Flyte Slurm plugin
  settings
- use `SlurmFunction` when a Python task function should run on the cluster
- use `SlurmTask` with `SlurmRemoteScript` or `SlurmShellTask` when a prepared
  cluster-side script is the right boundary
- submit jobs through the Slurm agent
- track scheduler job IDs
- monitor job state through the Slurm agent
- support cancellation through the Slurm agent
- collect task logs and connect completed outputs back to the run record

The goal is a user experience similar to Nextflow or Snakemake on HPC: the user
asks for the analysis and resources, FLyteTest builds the run record, and the
execution system handles submission, scheduling, monitoring, logs, and outputs.

### 7.5 Offline Compute Nodes

Many HPC systems allow internet access on login nodes but not compute nodes.
FLyteTest should treat this as a normal deployment shape rather than an
exception.

Before a Slurm-backed run is submitted, the system should verify that the
compute job can run offline:

- input files are on filesystems visible to compute nodes
- container images are staged and readable
- tool databases such as BUSCO lineages or EggNOG databases are staged locally
- the saved run recipe is visible to the job
- output and log directories are writable
- no task expects to download data during compute-node execution

If a required dependency is missing, the system should fail before submission
with a clear report of what must be staged.

### 7.6 Execution Records

Every execution mode should produce a result record that can be used later for
inspection, reruns, or downstream workflow composition.

The record should include:

- the original prompt
- the saved run recipe identifier
- input files and prior result bundles used
- workflow stages executed
- task logs and output paths
- container images used
- requested resources and observed resources when available
- Slurm job IDs and scheduler states when applicable
- assumptions and warnings that affected the run

The execution record is what lets dynamic workflow planning remain reproducible.

## 8. Validation and Testing

FLyteTest must test both biological workflow behavior and orchestration
behavior. Dynamic planning is only acceptable when the generated run recipe,
resolved inputs, workflow graph, resource bindings, and execution records can be
tested independently.

Validation should stay useful on a developer machine, even when real tools,
containers, Slurm access, or large reference databases are not available.

### 8.1 Small Local Test Datasets

FLyteTest should maintain small, representative datasets that allow fast local
testing without requiring full production-scale genomes, read sets, or protein
databases.

These datasets should be small enough to run on a developer laptop or a single
local workstation, but structured enough to exercise the same file contracts as
real runs.

Small test datasets should include:

- a tiny reference genome FASTA
- paired-end RNA-seq read fixtures
- a small transcriptome FASTA for QC and quantification
- a small protein FASTA for Exonerate-backed protein evidence tests
- minimal PASA-style or EVM-style fixture outputs when the real tools are too heavy for local tests
- a tiny RepeatMasker `.out` fixture
- small BUSCO-like or lineage-path fixtures for path handling without a full BUSCO database
- saved `run_manifest.json` examples from representative stage boundaries

Local test datasets should be used for:

- fast smoke tests of workflow wiring
- manifest shape tests
- input/output resolution tests
- prompt-to-run-recipe tests
- container path validation tests
- Slurm run-recipe generation tests that do not require a real scheduler

Full biological validation on real datasets remains separate from fast local
testing. The local fixtures prove that contracts, paths, manifests, and DAG
composition behave correctly; they do not replace scientific validation of tool
performance on production data.

### 8.2 Static and Import Checks

Every milestone should keep the Python source importable and compile cleanly.

Checks should include:

- Python compilation for touched modules
- import checks for task and workflow modules
- compatibility checks for `flyte_rnaseq_workflow.py`
- registry lookups for new tasks and workflows
- MCP tool and resource name checks

### 8.3 Strong Datatype and Wiring Tests

Strong datatype tests should prove that workflow composition cannot connect
incompatible biological objects.

Tests should cover:

- serialization and reload of strong datatypes
- conversion from result manifests into typed biological objects
- valid wiring between compatible workflow stages
- rejection of invalid wiring, such as passing BAM-only evidence where a genome FASTA is required

### 8.4 Prompt Planning Tests

Prompt planning tests should prove that natural-language requests become stable,
reviewable plans.

Tests should cover:

- supported prompts resolving to the expected workflow family
- prompts with resource requests producing explicit CPU, memory, walltime, and partition bindings
- prompts that require Slurm producing a Slurm execution profile
- ambiguous prompts reporting ambiguity instead of guessing
- unsupported biology being declined instead of invented
- generated workflows being grounded only in registered tasks or reviewed stages

### 8.5 Run Recipe Tests

Run recipe tests should prove that dynamic planning freezes into a stable record
before execution.

Tests should cover:

- run recipe creation from a supported prompt plan
- saving and reloading a run recipe without re-parsing the original prompt
- stable steps and their connections
- explicit input and output bindings
- explicit container and resource bindings
- recorded assumptions and warnings
- deterministic replay from the saved record

### 8.6 Workflow and Manifest Tests

Workflow tests should verify stage boundaries without requiring full-scale
biological runs for every change.

Tests should cover:

- fixture-backed workflow smoke tests when tool dependencies are available
- synthetic tests for collector tasks and result bundle shape
- `run_manifest.json` keys and expected output paths
- downstream reuse of prior result bundles
- preservation of the notes-faithful annotation stage order

### 8.7 MCP Interface Tests

MCP tests should ensure the tool interface remains stable for conversational
clients.

Tests should cover:

- stable tool names
- stable resource URIs
- structured `plan_request` responses
- run recipe preparation responses
- clear decline messages for unsupported prompts
- result inspection responses
- additive changes that do not break existing clients unless an intentional migration is documented

### 8.8 Slurm and HPC Tests

Slurm validation should start with synthetic and dry-run coverage, then progress
to real cluster integration tests when a configured Slurm environment is
available.

Tests should cover:

- translation from run recipe resources to Flyte Slurm plugin `sbatch_conf`
- validation of required SSH configuration
- validation that containers, databases, inputs, and run recipes are staged on compute-visible filesystems
- scheduler job ID capture, polling, cancellation, and log path recording

Real Slurm tests should be optional and clearly marked because they depend on
cluster access, scheduler policy, and local deployment configuration.

### 8.9 Representative Test Examples

A few representative tests are enough to show the testing style. The suite does
not need to spell out every tool-specific check in the design document.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from flytetest.planner_types import ReferenceGenome, ReadSet
from flytetest.planning import plan_typed_request
from flytetest.spec_artifacts import (
    artifact_from_typed_plan,
    load_workflow_spec_artifact,
    save_workflow_spec_artifact,
)


class PromptPlanningTests(TestCase):
    def test_prompt_planning_resolves_supported_rnaseq_request(self) -> None:
        genome = ReferenceGenome(fasta_path=Path("data/genome.fa"))
        reads = ReadSet(
            sample_id="sample-1",
            left_reads_path=Path("data/reads_1.fq.gz"),
            right_reads_path=Path("data/reads_2.fq.gz"),
        )

        plan = plan_typed_request(
            "Build transcript evidence from RNA-seq reads.",
            explicit_bindings={
                "ReferenceGenome": genome,
                "ReadSet": reads,
            },
        )

        self.assertTrue(plan["supported"])
        self.assertEqual(plan["biological_goal"], "transcript_evidence_generation")
        self.assertIn("transcript_evidence_generation", plan["matched_entry_names"])


class RunRecipeTests(TestCase):
    def test_saved_run_recipe_round_trips_without_reprompting(self) -> None:
        genome = ReferenceGenome(fasta_path=Path("data/genome.fa"))
        reads = ReadSet(
            sample_id="sample-1",
            left_reads_path=Path("data/reads_1.fq.gz"),
            right_reads_path=Path("data/reads_2.fq.gz"),
        )

        typed_plan = plan_typed_request(
            "Build transcript evidence from RNA-seq reads.",
            explicit_bindings={
                "ReferenceGenome": genome,
                "ReadSet": reads,
            },
        )

        artifact = artifact_from_typed_plan(typed_plan, created_at="2026-04-07T12:00:00Z")

        with TemporaryDirectory() as tmpdir:
            saved_path = save_workflow_spec_artifact(artifact, Path(tmpdir))
            loaded = load_workflow_spec_artifact(saved_path)

        self.assertEqual(loaded.source_prompt, "Build transcript evidence from RNA-seq reads.")
        self.assertEqual(loaded.workflow_spec.name, artifact.workflow_spec.name)
```

A Slurm dry-run test should fail before submission if inputs, containers, or
databases are not staged for the compute nodes.

## 9. Implementation Roadmap

This roadmap describes how FLyteTest should evolve toward the target design.
It is not limited to the current workflow structure. Existing workflows,
registry entries, planner behavior, and MCP surfaces may be refactored as needed
when the design calls for a clearer or more correct architecture.

### 9.1 Ground the Design in the Current Biological Baseline

The first priority is to preserve the notes-faithful genome-annotation pipeline
as the scientific baseline while making room for the broader prompt-driven
architecture.

This phase should keep the biological intent visible while allowing refactors of:

- workflow composition
- task boundaries
- planner behavior
- run record structure
- execution profile handling
- Slurm-oriented job generation and monitoring

### 9.2 Refactor Toward Strong Datatypes and Run Recipes

The current workflow code should be reshaped so that biological data is
described through strong datatypes and selected runs are represented as saved
run recipes.

This phase should:

- expand biological datatypes where the pipeline needs clearer boundaries
- make prompt planning produce structured plans instead of ad hoc execution
- make result directories and manifests easier to reuse downstream
- make composed workflows easier to save, inspect, and replay
- refactor existing workflow implementations if they are too narrow for the
  target design

### 9.3 Make Resources and SLURM First-Class

Resource handling should move from incidental task flags to explicit planning
and execution decisions.

This phase should:

- interpret CPU, memory, walltime, and partition requests from prompts
- freeze resource choices into the saved run recipe
- generate Slurm-ready execution records and `sbatch`-aligned settings
- use the Flyte Slurm plugin for submission, scheduling, monitoring, and
  cancellation
- validate offline compute-node assumptions before submission
- refactor workflow or execution code if current shapes cannot support these
  resource decisions cleanly

### 9.4 Broaden the Biological Scope

Once the core planning and execution path is stable, the biological coverage can
expand downstream of the current annotation baseline.

This phase should add or refine:

- EggNOG-mapper support
- AGAT statistics and conversion
- optional `table2asn` submission preparation
- broader transcript evidence handling when needed
- additional evidence or annotation families only when they can be grounded in
  established tasks and reviewed workflow stages

### 9.5 Mature the MCP Interface

The MCP layer should become a practical entrypoint for planning, recipe
generation, execution launching, and result inspection.

This phase should:

- expose prompt planning, run recipe preparation, validation, and inspection
- surface Slurm-ready run records and job status
- keep the tool surface small, typed, and machine-readable
- preserve compatibility where possible, but allow deliberate migrations when
  the architecture demands them

## 10. Repository Layout

FLyteTest should evolve toward a layout that keeps biological stages, planning
logic, execution logic, and interface code separate. The goal is to make the
codebase easy to navigate for both humans and agents.

A target layout could look like this:

```text
src/flytetest/
  config.py
  planner_types.py
  planner_adapters.py
  planning.py
  resolver.py
  registry.py
  specs.py
  spec_artifacts.py
  spec_executor.py
  server.py
  mcp_contract.py
  tasks/
    qc.py
    transcript_evidence.py
    protein_evidence.py
    annotation.py
    consensus.py
    filtering.py
    functional.py
    submission.py
  workflows/
    rnaseq_qc_quant.py
    transcript_evidence.py
    pasa.py
    transdecoder.py
    protein_evidence.py
    annotation.py
    consensus.py
    filtering.py
    functional.py
```

### Layout Principles

- keep task code in task modules, not in planners or workflows
- keep workflow composition in workflow modules, not in the MCP layer
- keep planning and input resolution separate from execution code
- keep run recipe and manifest logic separate from runtime orchestration
- keep Slurm-specific code in its own execution layer once that layer grows
- keep compatibility entrypoints stable for users who still rely on `flyte run`

### Supporting Files

The repository should also keep a small number of top-level docs and handoff
files that explain the design and current scope:

- `README.md`
- `DESIGN.md`
- `CHANGELOG.md`
- `docs/mcp_showcase.md`
- `docs/tutorial_context.md`
- `docs/capability_maturity.md`
- `docs/realtime_refactor_checklist.md`

## 11. Open Questions and Risks

This design is intentionally opinionated, but a few questions still matter
because they affect how the system should evolve and how much flexibility it
should leave for future workflow families.

### 11.1 Open Questions

- How much of the natural-language planning should be interpreted by the prompt
  layer versus by explicit user-selected execution profiles?
- Which resource phrases should map to fixed cluster settings, and which should
  require confirmation before submission?
- How should the system represent multiple valid ways to resolve the same
  input, such as a genome available from both a direct path and a prior run
  manifest?
- How far should the curated workflow catalog grow before the design needs a
  more formal compatibility model?
- Should the first Slurm integration focus on submitting Flyte-backed tasks, or
  should it also support prepared cluster scripts from the start?
- Which biological stage families should be added next after the current
  annotation pipeline, and which should remain outside the design until a
  concrete user need appears?

### 11.2 Risks

- The planner could become too permissive and start inventing workflows that
  are not grounded in established tasks or reviewed workflow stages.
- Resource interpretation could become inconsistent if vague phrases like
  "high memory" or "short queue" are not tied to a cluster profile.
- Slurm support could become fragmented if script generation, submission,
  scheduling, and monitoring are implemented as disconnected pieces.
- Offline compute-node support could fail if containers, databases, or input
  files are not staged as a first-class part of the run recipe.
- The design could drift back toward file-plumbing language if strong datatypes
  are not kept central in planning and execution.
- The repository could accumulate too many partial execution paths if local,
  Flyte-managed, and Slurm-backed modes are not kept clearly separated.
- MCP could become too broad if every planning and execution action is exposed
  as a separate tool without a clear user flow.

### 11.3 Design Rules To Keep

- New workflows may be dynamically composed only when grounded in established
  tasks or reviewed workflow stages.
- Execution must consume a frozen run recipe, not reinterpret the original
  prompt.
- Slurm support should behave like a real HPC interface, including submission,
  scheduling, monitoring, cancellation, and logging.
- Result bundles and manifests should remain the main source of truth for
  downstream reuse.
- The biological pipeline should remain the anchor for all architecture
  changes.
