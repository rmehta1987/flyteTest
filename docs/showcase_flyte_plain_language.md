# Explaining Why Flyte Helps This Biosciences Pipeline

Companion to `docs/showcase_biosciences.md`. The showcase file is the demo
script. This file is the 20-minute talk script for a mixed audience — a
research-computing partner who knows HPC and Slurm but not Flyte, and a PI
who knows the biology side but not the tooling.

The goal is not to sell Flyte as a brand. The goal is to explain why this way
of organizing the pipeline makes the science easier to run, inspect, trust,
and hand off.

The single sentence to keep coming back to:

> FLyteTest helps turn a pile of scripts, files, cluster commands, and
> assumptions into a labelled, checkable, repeatable analysis plan.

## Time Budget

| #   | Section                                | Time    |
| --- | -------------------------------------- | ------- |
| 1   | The pain                               | 2 min   |
| 2   | The central idea                       | 2 min   |
| 3   | Types as scientific labels             | 1.5 min |
| 4   | Demo (five scenes)                     | 10 min  |
| 5   | Where this fits next to Nextflow       | 2 min   |
| 6   | What we are not claiming               | 1.5 min |
| 7   | Close                                  | 30 sec  |

Total ~19.5 min, leaving 30 seconds for one clarifying question without going
over.

## 1. The Pain (2 min)

The pain is rarely "we need a scheduler." Labs already have Slurm. The pain
is more like:

- Which input file did we use?
- Was that VCF before or after filtering?
- Which reference genome did the BAM align to?
- Did the job use the GATK container or the cluster module?
- Did the compute node actually have access to the SIF image?
- What memory and walltime did we request?
- What failed, and can we retry without changing the analysis itself?
- Can another scientist rerun this without reverse-engineering the original
  user?

These answers usually live in someone's memory, a Slack thread, or a
half-updated README. FLyteTest is useful here because it helps move those
answers out of memory and into the workflow structure itself.

## 2. The Central Idea (2 min)

Avoid starting with "Flyte is a workflow orchestrator." That is true, but it
is not the strongest message for this audience.

Start here instead:

> The system makes each biological analysis step declare what it consumes,
> what it produces, and how it should run. Then it freezes those choices into
> a recipe before anything is submitted to Slurm.

Five practical consequences:

- **Labels on scientific materials.** A file is not just a file. It may be a
  reference genome, read pair, BAM, VCF, GFF3 annotation, SnpEff database,
  BUSCO result, or final report bundle.
- **Checkable connections.** A step that expects a VCF should not accidentally
  get a FASTA. A step that expects known-sites resources should not run with
  the wrong input silently.
- **Inspect-before-run.** The system writes down what will run before it
  spends cluster time.
- **Durable evidence.** After the job runs, the record remains: inputs,
  outputs, commands, containers, resources, logs, scheduler state.
- **Safer handoff.** A new user can run a supported analysis without learning
  the whole infrastructure stack first.

## 3. Types As Scientific Labels (1.5 min)

The word "type" can sound abstract. Translate it into scientific labels.

> A type is a formal label for what kind of scientific object is moving
> through the workflow.

Examples:

```text
ReferenceGenome
ReadSet
AlignedBam
VariantCallSet
AnnotationBundle
SnpEffDatabase
```

Many of these are physically just files on disk, but they are not
scientifically interchangeable. Even files with the same extension may not
mean the same thing:

```text
raw VCF
joint-called VCF
hard-filtered VCF
VQSR-filtered VCF
SnpEff-annotated VCF
```

The label is what says "joint-called VCF, not hard-filtered" — so the wrong
file cannot silently flow into the wrong stage.

Good line for professors:

> Flyte types make computational outputs behave more like labelled samples.
> The label says what the object is, not just where it sits on disk.

## 4. The Demo (10 min)

The demo should feel like a scientist controlling an analysis, not like an
engineer showing an API.

### Scene 1 — Discover what is available (1.5 min)

What happens:

```text
The user asks what analyses and starter bundles are available.
The system lists registered tasks, workflows, and bundles.
The scientist chooses a GATK starter bundle.
```

Say:

> This is the lab menu. These are the analyses the system actually knows
> how to run. We are not asking the model to invent a pipeline. We are asking
> it to choose from registered analyses. The catalogue is the safety
> boundary.

The catalogue is real: 45 registered showcase tasks and workflows across five
families (`variant_calling`, `annotation`, `postprocessing`, `protein_evidence`,
`rnaseq`). The names match the code exactly. Lean on this — it is the
strongest counter to the AI-skeptic objection from either side of the
audience.

### Scene 2 — Freeze a run before submitting (2.5 min)

What happens:

```text
The user asks for a dry run.
The system writes a run recipe artifact to disk.
Nothing is submitted yet.
The artifact records resolved inputs, containers, resources, and bound
planner types. The reply also returns staging findings.
```

Say:

> This is the key point. Before Slurm sees anything, we can open the recipe
> artifact and inspect what will happen. That protects cluster time and
> protects the analysis. This is the written protocol for this computational
> run.

Make it physical. Run `cat "$artifact_path" | jq` on the frozen JSON live
during the demo. Audit-driven note: the dry-run *reply* surfaces only
`recipe_id`, `artifact_path`, `staging_findings`, `resolved_bindings`,
`resolved_environment`, `limitations`, `workflow_name`, and the execution
profile. The full resolved inputs, runtime images, and resource spec live in
the artifact JSON on disk, not in the API reply. Talking about "the recipe"
and showing the artifact is honest; calling the API reply "the recipe" is
not.

### Scene 3 — Validate cluster readiness (2 min)

What happens:

```text
The system checks that containers, tool databases, and resolved input paths
exist and are readable. With execution_profile="slurm", it also checks that
they sit under shared-filesystem roots compute nodes can see.
```

Say:

> A job that fails after four hours because a container was only visible on
> the login node is a preventable failure. With the slurm profile, this
> preflight catches that before the job enters the queue.

Audit-driven note: the "compute-node-visible" claim is only honest when
`execution_profile="slurm"` is passed to `validate_run_recipe`. The default
is `"local"`, which only checks existence and readability — still useful, but
a smaller claim. The live demo command must include the slurm profile, or
the framing line must soften to "checks containers and databases exist."

### Scene 4 — Submit and monitor (2 min)

What happens:

```text
The frozen recipe is submitted to Slurm.
The system records job ID, log paths, scheduler state, exit code, and the
run record path.
```

Say:

> The job is not just launched and forgotten. The run record is the receipt.
> It tells us what was submitted, where the logs are, and what happened. We
> keep a durable receipt for the computational experiment.

### Scene 5 — Retry without changing the science (2 min)

What happens:

```text
If the job fails because it ran out of memory or time, the user can retry
with larger resources while keeping the original recipe linked.
```

Say:

> If the failure is operational, like not enough memory, we can change the
> resource request without quietly changing the biological analysis. The
> retry links back to the original. We can fix the cluster request while
> preserving the scientific plan.

`resource_request` is the real, stable kwarg used by `run_task`,
`run_workflow`, `prepare_run_recipe`, and `prompt_and_run`. Worth saying the
name aloud once — it removes a category of "is this hand-wavy?" suspicion.

## 5. Where This Fits Next To Nextflow (2 min)

Many in this audience know Nextflow and nf-core. Be fair, not competitive.

Nextflow is excellent for large, portable, production workflows. If a group
already has an nf-core workflow or a local Nextflow pipeline that runs
hundreds of samples, that pipeline should usually stay in place.

What FLyteTest adds is a different interaction model.

Nextflow pattern:

```text
Choose a pipeline -> prepare samplesheet and config -> set profiles and
parameters -> run nextflow -> inspect outputs
```

FLyteTest pattern:

```text
Ask for a supported analysis -> load a curated bundle -> dry-run to freeze
a recipe -> validate cluster staging -> submit the frozen recipe -> inspect
the run record
```

Two lines that land:

> Nextflow is excellent for running a pipeline you already trust. FLyteTest
> is useful for making the choice, inputs, resources, and execution record
> visible before the run happens.

> If Nextflow is the production assembly line, FLyteTest is the labelled work
> order and inspection counter in front of it.

The diplomatic frame, especially for a PI:

> Nextflow is often how a computational expert writes the pipeline. FLyteTest
> is how a scientist can safely request and audit a supported pipeline.
> Adjacent jobs, not enemies.

## 6. What We Are Not Claiming (1.5 min)

Three honesty beats before the close.

Say:

> This supports registered analyses in the current catalogue.

Do not say:

> This can run any bioinformatics analysis from natural language.

Say:

> The current GATK scatter path is useful for smoke tests and controlled runs,
> but large production fan-out is still future work.

Do not say:

> This replaces production Nextflow pipelines for every cohort size.

Say:

> Slurm submission works when the server is running in an authenticated
> cluster session with staged inputs and images.

Do not say:

> It magically runs on any cluster.

The catalogue is the boundary. The model does not get to invent arbitrary
commands at execution time — it has to work through supported tasks,
workflows, typed inputs, and frozen recipes.

## 7. Close (30 sec)

> Flyte is useful here because it makes the computational analysis explicit
> enough to inspect before it runs and trustworthy enough to explain after it
> runs.

Or, even shorter:

> The value is not automation by itself. The value is automation with labels,
> checks, records, and restraint.

---

## Q&A Prep (back-pocket — not part of the 20-min body)

### Are you replacing Nextflow or Snakemake?

No. If a lab already has a production Nextflow or Snakemake workflow that
runs well, keep it. This project is most useful when someone needs to request
a supported analysis, prototype a new step, inspect a frozen run, or give a
new user a safer starting point.

> We are not asking you to throw away working pipelines. We are showing a way
> to make supported analyses easier to request, inspect, and replay,
> especially before a lab has hardened a production workflow.

### Is this just an AI wrapper around shell commands?

No. The AI-facing layer can request work, but the runnable work comes from
the registered catalogue.

> The model does not get to invent arbitrary commands at execution time. It
> has to work through supported tasks, workflows, typed inputs, and frozen
> recipes.

### Why not just use bash?

Bash is still useful, and many tasks eventually call command-line tools. The
difference is the envelope around those commands.

> Bash can run the command. This system records the scientific context around
> the command — typed inputs, explicit outputs, manifest records, cluster
> preflight, and replayable run records.

### What happens if the request is unsupported?

The system declines with structured next steps instead of guessing. A refusal
is better than a plausible but unsupported biological pipeline.

> If the request cannot be mapped to registered biology, the safe behavior is
> to say what is missing and suggest supported next steps.

### Does data leave the cluster?

For the intended deployment, no. Be precise: the security behavior depends on
how the MCP client and server are deployed.

> The workflow server runs locally in the research computing environment. The
> cluster files stay on the cluster. The assistant is calling local tools
> rather than uploading data to a separate workflow service.

### How do I know the GATK parameters are correct?

> Each task enforces the documented GATK4 Best Practices command shape. The
> test suite (885+ tests) includes invocation tests that verify parameter
> passing for each task. The biological choices are documented in code, not
> in someone's memory.

### Who maintains this when you leave?

> The codebase is documented in `AGENTS.md`, `DESIGN.md`, and `.codex/`. The
> scaffold agent can produce a new registered task from a short intent
> description. New students can add biology without understanding the Slurm
> or MCP layers.
