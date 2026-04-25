# Explaining Why Flyte Helps This Biosciences Pipeline

This is a companion to `docs/showcase_biosciences.md`. The showcase file is the
demo script. This file is the plain-language story around the demo: how to explain
why Flyte is useful for this project to professors, scientists, research staff,
and computing partners who may not care about workflow-engine jargon.

The goal is not to sell Flyte as a brand. The goal is to explain why this way of
organizing the pipeline makes the science easier to run, inspect, trust, and hand
off.

## The Short Version

FLyteTest uses Flyte because this project is not just trying to launch jobs. It is
trying to make bioinformatics work behave more like an auditable scientific
protocol.

A scientist should be able to say what analysis they want, inspect exactly what
will happen, confirm the right data and containers are available on the cluster,
submit the run, and later explain exactly what was done. Flyte is useful because
it gives the project a disciplined way to describe each computational step: what
it needs, what it produces, what resources it asks for, and how it connects to the
next step.

In less technical words:

> Flyte helps turn a pile of scripts, files, cluster commands, and assumptions
> into a labelled, checkable, repeatable analysis plan.

That is the point to keep coming back to.

## The Audience Problem

Most biology groups already have some combination of scripts, notebooks, old
pipeline fragments, shared cluster instructions, and people who remember how the
analysis is supposed to work. That can be enough for one expert user. It becomes
fragile when a new student joins, a collaborator asks for the same analysis, a PI
wants to review the parameters, or a reviewer asks how a result was produced.

The pain is rarely just "we need a scheduler." Labs already have Slurm. The pain
is usually more like this:

- Which input file did we use?
- Was that VCF before or after filtering?
- Which reference genome did the BAM align to?
- Did the job use the GATK container or the cluster module?
- Did the compute node actually have access to the SIF image?
- What memory and walltime did we request?
- What failed, and can we retry without changing the analysis itself?
- Can another scientist rerun this without reverse-engineering the original user?

Flyte is useful here because it helps move those answers out of memory and into
the workflow structure itself.

## The Central Message

When presenting this project, avoid starting with "Flyte is a workflow
orchestrator." That is true, but it is not the strongest message for this
audience.

Start here instead:

> The system makes each biological analysis step declare what it consumes, what it
> produces, and how it should run. Then it freezes those choices into a recipe
> before anything is submitted to Slurm.

That sentence explains why Flyte matters without asking the listener to know Flyte
internals.

The useful ideas are:

- **Labels on scientific materials.** A file is not just a file. It may be a
  reference genome, read pair, BAM, VCF, GFF3 annotation, SnpEff database, BUSCO
  result, or final report bundle.
- **Checkable connections.** A step that expects a VCF should not accidentally get
  a FASTA. A step that expects known-sites resources should not run with the wrong
  input silently.
- **Inspect-before-run.** The system writes down what will run before it spends
  cluster time.
- **Durable evidence.** After the job runs, the record remains: inputs, outputs,
  commands, containers, resources, logs, scheduler state.
- **Safer handoff.** A new user can run a supported analysis without learning the
  whole infrastructure stack first.

## A Simple Analogy

Use the lab-protocol analogy.

In a wet lab, you do not want a protocol that says:

```text
Use the tube from yesterday and run the machine.
```

You want something more like:

```text
Input: extracted DNA from sample NA12878
Instrument: sequencer X with settings Y
Reagent kit: version Z
Output: FASTQ files labelled with sample, date, and run ID
Quality check: record pass/fail metrics
```

FLyteTest is doing the computational version of that. It asks each step to be
clear about its inputs, outputs, software environment, and record-keeping.

That is what Flyte is giving the project: a structure for computational protocols.

## What Flyte Adds Over A Script

A bash script can run GATK. A good script can even run it reliably. The reason to
use Flyte here is not that scripts are bad. It is that a research platform needs
more than the command line.

A script usually answers:

```text
What commands should run?
```

This project also needs to answer:

```text
What kind of scientific object does each command consume?
What kind of scientific object does it produce?
Are the stages connected in a biologically sensible order?
Which exact files were resolved for this run?
Which containers, modules, and databases are required?
Can the compute node see those files before we submit?
What run record can we show later?
Can we retry resource failures without changing the scientific recipe?
```

Flyte gives the project a natural way to organize those questions around tasks,
typed inputs, outputs, and workflow stages.

For a non-technical audience, describe this as:

> Scripts run commands. Flyte helps package commands as reusable, labelled,
> inspectable scientific steps.

## What Flyte Adds Compared With Other Workflow Tools

You do not need to criticize other tools. A fair explanation is more persuasive.

Many scientists already know Nextflow or Snakemake, and many research computing
groups also know Airflow or Prefect. The important point is not that Flyte is
"better" in every situation. The important point is that Flyte is useful for this
particular project because the project is centered on typed scientific objects,
inspectable run recipes, and controlled execution from a registered catalogue.

Here is the plain comparison:

| Tool | What it is especially good at | How to explain the difference here |
| --- | --- | --- |
| Nextflow | Large production bioinformatics pipelines, portable execution, mature scatter/gather patterns, strong community pipeline ecosystem such as nf-core | Keep it for hardened cohort-scale pipelines. FLyteTest is more useful when the goal is interactive request, inspection, typed catalogue selection, and frozen run recipes before submission. |
| Snakemake | Transparent file-driven pipelines, rule-based reproducibility, local/HPC usability, workflows that are easy to reason about from inputs and outputs | Keep it when the lab wants explicit rules over files. FLyteTest adds a scientist-facing catalogue and typed biological objects so a user can request a supported analysis without editing workflow rules. |
| Airflow | Operational scheduling: recurring jobs, data warehouse loads, dashboards, production automation | Airflow asks "when should this operational DAG run?" FLyteTest asks "what scientific objects does this analysis consume and produce, and is it safe to submit?" |
| Prefect | Python-friendly orchestration, quick iteration, flexible flow authoring | Prefect is pleasant for Python automation. FLyteTest needs stricter scientific contracts, run recipes, and registered biological stages. |
| Flyte | Typed computational tasks, explicit inputs and outputs, reusable workflow components, container/resource-aware execution | Useful here because each bioinformatics stage can be treated as a labelled scientific step that can be inspected, composed, and replayed. |

The diplomatic way to say it:

> Nextflow and Snakemake are excellent ways to encode known pipelines. FlyteTest is
> aimed at the moment when a scientist wants to request a supported analysis,
> inspect the exact plan, and submit it safely without editing workflow code.

That is why the comparison is not "Flyte versus Nextflow" in a winner-takes-all
sense. It is more like this:

```text
Nextflow / Snakemake:
  Best when the workflow is already written, reviewed, and run repeatedly.

FLyteTest on Flyte:
  Best when the scientist needs a catalogue of supported analyses, typed inputs,
  inspectable recipes, cluster preflight, and a durable run record.
```

For a PI, the most useful distinction is:

> Nextflow and Snakemake are often how a computational expert writes the pipeline.
> FLyteTest is how a scientist can safely request and audit a supported pipeline.

That does not remove the need for expert-maintained pipelines. It gives the lab a
safer front door for common analyses, smoke tests, teaching, review, and
prototype steps.

### Nextflow Comparison

Nextflow is probably the most familiar comparison for modern bioinformatics. It
is very strong for large, portable, production workflows. If a group already has
an nf-core workflow or a local Nextflow pipeline that runs hundreds of samples,
that pipeline should usually stay in place.

What FlyteTest adds is a different interaction model.

With a mature Nextflow workflow, the usual pattern is:

```text
Choose a pipeline
prepare samplesheet and config
set profiles and parameters
run nextflow
inspect outputs
```

With FLyteTest, the pattern is:

```text
ask for a supported analysis
load a curated bundle
dry-run to freeze a recipe
validate cluster staging
submit the frozen recipe
inspect the run record
```

The second pattern is useful when the user does not want to edit a DSL or config
tree just to run a supported analysis. It is also useful when the PI or
collaborator wants to inspect what will happen before the job starts.

Good line to use:

> Nextflow is excellent for running a pipeline you already trust. FLyteTest is
> useful for making the choice, inputs, resources, and execution record visible
> before the run happens.

Another good line:

> If Nextflow is the production assembly line, FLyteTest is the labelled work
> order and inspection counter in front of it.

Be careful with that analogy, though. FLyteTest currently runs its own registered
tasks and workflows; it is not claiming to wrap arbitrary Nextflow pipelines as a
general feature.

### Snakemake Comparison

Snakemake is often loved because it is explicit and file-oriented. A rule says
what files it needs, what files it creates, and what command connects them. That
is a very good mental model for many bioinformatics projects.

FlyteTest is aiming one level higher in the user experience. It still cares about
files, but it also wants the system to know the biological role of those files.

Snakemake might say:

```text
input:  "sample.bam", "reference.fa"
output: "sample.g.vcf.gz"
shell:  "gatk HaplotypeCaller ..."
```

FLyteTest wants to say:

```text
input:  aligned sample + reference genome
stage:  HaplotypeCaller from the registered GATK family
output: variant call set
record: manifest + frozen run recipe + scheduler state
```

Both are valuable. The FlyteTest version is useful when the analysis needs to be
selected from a catalogue, checked for typed compatibility, staged for a cluster,
and reviewed by someone who may not want to read workflow rules.

Good line to use:

> Snakemake makes file dependencies explicit. FlyteTest tries to make the
> scientific meaning of those dependencies explicit too.

Another good line:

> Snakemake is excellent when you want to write the rules. FLyteTest is useful
> when you want a scientist to choose a registered analysis and inspect the frozen
> plan without editing the rules.

### Airflow And Prefect Comparison

Airflow is excellent for operational scheduling: nightly jobs, data warehouse
loads, recurring reports, dashboards, and production automation. Prefect is
excellent for Python-friendly orchestration with quick iteration and a pleasant
developer experience.

FLyteTest needs something slightly different. It needs a way to make scientific
task boundaries explicit.

The project cares about questions like:

- Does this step consume a `ReferenceGenome`, `ReadSet`, or `VariantCallSet`?
- Does this output represent an aligned sample, a filtered VCF, or an annotation
  result?
- Can this output safely connect to the next biological stage?
- What container, module, and resource request belongs to this exact task?
- Can we freeze the complete analysis before execution?

Flyte is a better fit because typed computational tasks are close to its center.
That does not make Airflow, Prefect, Nextflow, or Snakemake bad. It means the
scientific contract is more central in this Flyte-based design than in a general
scheduler, a general Python automation tool, or a file-rule workflow alone.

Plain-language version:

> Airflow is very good at asking "when should this job run?" Prefect is very good
> at asking "how can we orchestrate this Python flow easily?" Flyte is especially
> useful here because it asks "what are the exact inputs and outputs of each
> computational step, and can we safely connect them?"

For this pipeline, that last question is the one that protects the science.

## A Simple Decision Guide

If someone asks which tool they should use, answer by use case instead of by
brand loyalty.

Use **Nextflow** when:

- the lab already has a tested production pipeline
- the main run pattern is many samples or cohorts
- the team wants mature scatter/gather and portable execution profiles
- an nf-core pipeline already does the job well

Use **Snakemake** when:

- the analysis is naturally file-rule driven
- the team wants transparent file dependencies
- the workflow is maintained by people comfortable editing rules
- local/HPC execution from explicit inputs and outputs is the main need

Use **Airflow** when:

- the job is recurring operational automation
- the workflow is more data-platform than scientific-analysis protocol
- dashboards, scheduled DAGs, and production operations are the center

Use **Prefect** when:

- the team wants ergonomic Python orchestration
- the workflow is application automation or flexible scripting
- strict biological type contracts are less important than iteration speed

Use **FLyteTest on Flyte** when:

- the scientist needs to request a supported analysis without editing workflow
  code
- the lab wants the analysis frozen into an inspectable recipe before Slurm
  submission
- inputs and outputs need biological labels, not just filenames
- cluster staging should be checked before queue time is spent
- run records, manifests, and retries need to preserve a reviewable chain of
  evidence

The simplest summary:

> Use Nextflow or Snakemake to encode mature pipelines. Use FLyteTest when you
> want a safer scientist-facing front door to registered analyses, with inspection
> and provenance built in.

## How To Explain Types Without Jargon

Flyte's type ideas are one of the most important parts, but the word "type" can
sound abstract. Translate it into scientific labels.

Say this:

> A type is a formal label for what kind of scientific object is moving through
> the workflow.

Then give examples:

```text
ReferenceGenome
ReadSet
AlignedBam
VariantCallSet
AnnotationBundle
SnpEffDatabase
```

Those labels matter because many things are physically just files on disk, but
they are not scientifically interchangeable. A FASTA, BAM, VCF, GFF3, and SIF
image are all files. They should not be mixed up.

Even files with the same extension may not mean the same thing:

```text
raw VCF
joint-called VCF
hard-filtered VCF
VQSR-filtered VCF
SnpEff-annotated VCF
```

The extension alone cannot tell the whole story. The workflow needs to know where
the file came from and what stage it represents.

Good line for professors:

> Flyte types make computational outputs behave more like labelled samples. The
> label says what the object is, not just where it sits on disk.

## The Pipeline Story To Tell

The current showcase focuses on two real biological areas:

- GATK4 germline variant calling
- eukaryotic genome annotation through stages such as BRAKER3, EVM, PASA, BUSCO,
  EggNOG, repeat filtering, and AGAT

Do not present this as a generic demo app. Present it as a concrete research
workflow problem:

> We have multi-stage bioinformatics analyses that depend on exact tools, exact
> inputs, exact databases, exact containers, and cluster-specific resource choices.
> FlyteTest wraps those stages so they can be requested, inspected, submitted, and
> audited through a consistent interface.

For GATK, the story is especially easy to follow:

```text
Prepare reference
  -> align reads
  -> sort and mark duplicates
  -> recalibrate base qualities
  -> call variants
  -> combine and genotype
  -> refine or filter calls
  -> run QC
  -> annotate variants
```

What Flyte helps with is not inventing those biological steps. The steps come from
known practice and registered task definitions. Flyte helps make the steps
explicit, ordered, inspectable, and reusable.

## How To Talk Through The Demo

The demo should feel like a scientist controlling an analysis, not like an
engineer showing an API.

### Scene 1: Discover What Is Available

What happens:

```text
The user asks what analyses and starter bundles are available.
The system lists registered tasks, workflows, and bundles.
The scientist chooses a GATK starter bundle.
```

What to say:

> We are not asking the model to invent a pipeline. We are asking it to choose
> from registered analyses. The catalogue is the safety boundary.

Avoid saying first:

```text
MCP target registry with generated showcase targets.
```

Say instead:

> This is the lab menu. These are the analyses the system actually knows how to
> run.

### Scene 2: Freeze A Run Before Submitting

What happens:

```text
The user asks for a dry run.
The system writes a run recipe.
Nothing is submitted yet.
The recipe shows resolved inputs, containers, resources, and staging findings.
```

What to say:

> This is the key point. Before Slurm sees anything, we can open the recipe and
> inspect what will happen. That protects cluster time and protects the analysis.

Avoid saying first:

```text
WorkflowSpec artifact with BindingPlan serialization.
```

Say instead:

> This is the written protocol for this computational run.

### Scene 3: Validate Cluster Readiness

What happens:

```text
The system checks that input data, containers, databases, and the recipe are on
paths visible to compute nodes.
```

What to say:

> A job that fails after four hours because a container was only visible on the
> login node is a preventable failure. This preflight catches that before the job
> enters the queue.

Avoid saying first:

```text
shared_fs_roots staging enforcement.
```

Say instead:

> The system checks whether the cluster workers can actually see the files they
> will need.

### Scene 4: Submit And Monitor

What happens:

```text
The frozen recipe is submitted to Slurm.
The system records job ID, log paths, scheduler state, exit code, and run record.
```

What to say:

> The job is not just launched and forgotten. The run record is the receipt. It
> tells us what was submitted, where the logs are, and what happened.

Avoid saying first:

```text
Durable scheduler reconciliation.
```

Say instead:

> We keep a durable receipt for the computational experiment.

### Scene 5: Retry Without Changing The Science

What happens:

```text
If the job fails because it ran out of memory or time, the user can retry with
larger resources while keeping the original recipe linked.
```

What to say:

> If the failure is operational, like not enough memory, we can increase memory
> without quietly changing the biological analysis. The retry links back to the
> original run.

Avoid saying first:

```text
resource_overrides on retry_slurm_job.
```

Say instead:

> We can fix the cluster request while preserving the scientific plan.

## Phrases That Work Well

Use phrases like these:

- "Inspect before execution."
- "A computational protocol, not just a command."
- "The recipe is frozen before the job is submitted."
- "Every stage declares what it consumes and produces."
- "The system refuses unclear or unsupported requests instead of guessing."
- "The run record is the receipt for the analysis."
- "The catalogue is the safety boundary."
- "Files are labelled by scientific role, not just by pathname."
- "The goal is to protect cluster time and scientific trust."

## Phrases To Use Carefully

These words are accurate, but explain them the first time:

- **Task**: one computational step, such as marking duplicates or running BUSCO.
- **Workflow**: a set of steps connected in a biological order.
- **Type**: a label for what kind of scientific object a step expects or produces.
- **Registry**: the approved catalogue of tasks and workflows.
- **Manifest**: the output record that says what files were produced.
- **Run recipe**: the frozen plan for one analysis run.
- **Container**: the packaged software environment for a tool.
- **Slurm**: the cluster scheduler that actually runs the job.
- **MCP**: the connection that lets an assistant call local project tools.

When possible, say the plain version first and the technical term second:

```text
The written protocol for this run, which the project calls a run recipe.
The approved analysis catalogue, which the code calls the registry.
The output receipt, which the project calls a manifest.
```

## What Not To Overclaim

Be careful not to imply more than the repo supports.

Say:

> This supports registered analyses in the current catalogue.

Do not say:

> This can run any bioinformatics analysis from natural language.

Say:

> The current GATK scatter path is useful for smoke tests and controlled runs, but
> large production fan-out is still future work.

Do not say:

> This replaces production Nextflow pipelines for every cohort size.

Say:

> The system can help author new registered tasks within existing families.

Do not say:

> The AI can invent new scientifically valid pipelines.

Say:

> Slurm submission works when the server is running in an authenticated cluster
> session with staged inputs and images.

Do not say:

> It magically runs on any cluster.

## A Plain-Language Walkthrough Script

Here is a longer narration you can use in a meeting.

> The reason we are using Flyte here is that these analyses are not just a list of
> commands. They are scientific protocols with inputs, outputs, assumptions,
> software environments, and cluster requirements. If those are implicit, the
> analysis may still run, but it is hard to audit and hard to hand to someone
> else.

> In this project, each step is registered. That means the system knows what the
> step is for, what it expects, and what it produces. For example, a variant
> calling step does not just take some random file path. It takes a reference
> genome, read data, known-sites resources, or variant-call objects with known
> roles in the pipeline.

> When a scientist asks for an analysis, the system does not simply generate a
> shell script and hope it is right. It matches the request to supported entries
> in the catalogue. Then it resolves the actual files, containers, databases, and
> resource settings. Before submitting anything, it writes a frozen recipe. That
> recipe can be opened and reviewed.

> This matters on an HPC cluster because failures are expensive. If a container or
> database is not visible from compute nodes, the preflight can catch that before
> the job is submitted. If the run fails because it needs more memory, the retry
> can change the resource request while preserving the original scientific plan.

> So the point is not that Flyte is a fancier way to call GATK. The point is that
> Flyte gives us a framework for making the computational protocol explicit. It
> helps us know what was requested, what was resolved, what will run, what did run,
> and how to repeat it.

> That is why this is useful for a lab. A new student can start from a registered
> analysis instead of a blank shell script. A PI can inspect the recipe instead of
> trusting a hidden configuration. A collaborator can receive a run record instead
> of an email saying "I think these were the parameters." The science becomes
> easier to review.

## Questions You Are Likely To Get

### Are You Replacing Nextflow Or Snakemake?

No. If a lab already has a production Nextflow or Snakemake workflow that runs
well, keep it. This project is most useful when someone needs to request a
supported analysis, prototype a new step, inspect a frozen run, or give a new
user a safer starting point.

Nextflow and Snakemake are usually strongest once the pipeline is already encoded
as workflow code. FLyteTest is strongest at the front door: helping a scientist
choose from registered analyses, bind the right data, inspect the exact plan,
check cluster readiness, and keep a durable run record. Those are adjacent jobs,
not enemies.

For Nextflow:

> Keep using it for hardened, cohort-scale, portable pipelines. FLyteTest is
> useful when the scientist needs an inspectable request-and-submit path before a
> workflow has become a production pipeline, or when the PI wants to audit the run
> recipe without reading Nextflow configuration.

For Snakemake:

> Keep using it when explicit file rules are the right abstraction. FLyteTest is
> useful when the lab wants biological labels, registered task metadata, cluster
> preflight, and run receipts around those file-based steps.

Good answer:

> We are not asking you to throw away working pipelines. We are showing a way to
> make supported analyses easier to request, inspect, and replay, especially
> before a lab has hardened a production workflow.

### Is This Just An AI Wrapper Around Shell Commands?

No. The AI-facing layer can request work, but the runnable work comes from the
registered catalogue. That catalogue is what keeps the system grounded.

Good answer:

> The model does not get to invent arbitrary commands at execution time. It has to
> work through supported tasks, workflows, typed inputs, and frozen recipes.

### Why Not Just Use Bash?

Bash is still useful, and many tasks eventually call command-line tools. The
difference is the envelope around those commands: typed inputs, explicit outputs,
manifest records, cluster preflight, and replayable run records.

Good answer:

> Bash can run the command. This system records the scientific context around the
> command.

### What Happens If The Request Is Unsupported?

The system should decline with structured next steps instead of guessing. That is
important. A refusal is better than a plausible but unsupported biological
pipeline.

Good answer:

> If the request cannot be mapped to registered biology, the safe behavior is to
> say what is missing and suggest supported next steps.

### Does Data Leave The Cluster?

For the intended deployment, no. The server runs in the user's environment, and
Slurm submission happens from an authenticated cluster session. Be precise here:
the security behavior depends on how the MCP client and server are deployed.

Good answer:

> The workflow server runs locally in the research computing environment. The
> cluster files stay on the cluster. The assistant is calling local tools rather
> than uploading data to a separate workflow service.

## The Best Closing Line

End with the scientific value, not the software category.

> Flyte is useful here because it makes the computational analysis explicit enough
> to inspect before it runs and trustworthy enough to explain after it runs.

Or, even shorter:

> The value is not automation by itself. The value is automation with labels,
> checks, records, and restraint.
