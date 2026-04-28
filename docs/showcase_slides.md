# FLyteTest Showcase — Slide Deck
<!-- 20-minute talk. Slides 1–5 are presented. Slide 6 onward is live terminal. -->

---

## Slide 1 — Title

# Agentic AI for Bioinformatics
### From plain-language intent to an auditable, submittable Slurm job

_[Your name] · [Date] · RCC Midway3_

---

## Slide 2 — The Setup

# What if you could just describe what you want?

_Today's reality in most labs:_

- Which input file did we use for that run?
- Was that VCF before or after filtering?
- Did the job use the GATK container or the cluster module?
- Did the compute node actually have access to the SIF image?
- What failed — and can we retry without changing the analysis?
- Can a new student rerun this without reverse-engineering the original user?

**The answers live in someone's memory, a Slack thread, or a half-updated README.**

&nbsp;

_What we built:_

> You describe the analysis you want in plain language.
> An AI agent translates it into a registered, validated workflow,
> freezes it into an auditable recipe, checks that the cluster can run it,
> and submits the job — leaving a durable record you can show a reviewer years later.

---

## Slide 3 — How the Agent Works

# Four steps. No DSL. No config tree.

```
1. INTENT       "Run germline variant calling on this NA12878 sample"
                      ↓
2. MATCH        Agent selects from a catalogue of registered, validated workflows
                      ↓
3. FREEZE       Recipe written to disk — resolved inputs, containers,
                resources, staging findings — before Slurm sees anything
                      ↓
4. SUBMIT       Frozen recipe submitted; run record captures everything
```

&nbsp;

**The agent cannot invent biology.**
It selects from a catalogue of registered, validated analyses.
That constraint is what makes it trustworthy.

---

## Slide 4 — The Catalogue

# 45 registered workflows and tasks across five biological families

| Family | What it covers |
|---|---|
| `variant_calling` | GATK4 germline calling — reference prep through SnpEff annotation |
| `annotation` | BRAKER3 eukaryotic genome annotation |
| `postprocessing` | EggNOG functional annotation, AGAT, repeat filtering |
| `protein_evidence` | Exonerate protein alignment evidence |
| `rnaseq` | STAR transcript evidence generation |

&nbsp;

Each entry in the catalogue declares:
- **what biological objects it consumes** (reference genome, read pair, variant call set…)
- **what it produces** (aligned BAM, joint VCF, annotated GFF3…)
- **what resources and containers it needs**

The agent reasons over this catalogue — not over arbitrary shell commands.

---

## Slide 5 — Why This Matters: Biological Types

# The agent knows the difference between these

```
raw VCF
  ↓  joint genotyping
joint-called VCF
  ↓  VQSR recalibration
VQSR-filtered VCF
  ↓  SnpEff
SnpEff-annotated VCF
```

**Same file extension. Completely different scientific meaning.**

The agent won't connect the output of one stage to the wrong input of the next.
It enforces biological ordering — not because it's clever, but because the catalogue
makes the connections explicit and type-checked.

> The agent makes computational outputs behave like labelled samples.
> The label says what the object **is**, not just where it sits on disk.

---

## Slide 6 — [SWITCH TO TERMINAL]

# Live demo — the agent in action

_Switch to terminal now. Five scenes, ~10 minutes._

| Scene | What the agent does | Time |
|---|---|---|
| 1 | Discovers the catalogue, loads a starter bundle | 1.5 min |
| 2 | Creates a frozen recipe from your intent | 2.5 min |
| 3 | Checks cluster readiness before submitting | 2 min |
| 4 | Submits, monitors, shows the durable receipt | 2 min |
| 5 | Retries a resource failure without changing the science | 2 min |

---

## Slide 7 — Scene 1 talking points

# Scene 1 — The catalogue

_[On screen: agent calls `list_entries()`, `list_bundles()`, `load_bundle()`]_

**Say:**

> The agent doesn't guess what to run. It asks the catalogue.
> Every entry is a registered, validated biological analysis —
> not a string it hopes is correct.
>
> **The catalogue is the safety boundary.**
> The agent can only propose analyses that are in it.

---

## Slide 8 — Scene 2 talking points

# Scene 2 — The agent creates a frozen recipe

_[On screen: agent calls `run_workflow(..., dry_run=True)`, then opens the artifact JSON]_

**Say:**

> The agent translates your intent into a frozen recipe —
> a plain JSON file on disk that records exactly what will run:
> resolved input paths, containers, resource request, bound biological types.
>
> Nothing has been submitted yet. You can read it, email it, or commit it.
>
> **This is the written protocol for the computational experiment.**

---

## Slide 9 — Scene 3 talking points

# Scene 3 — The agent checks the cluster

_[On screen: agent calls `validate_run_recipe(..., execution_profile="slurm")`]_

**Say:**

> A job that fails four hours in because a container wasn't visible
> from compute nodes is a preventable failure.
>
> The agent runs a preflight check on the frozen recipe — before sbatch.
> It verifies that every container, database, and input path
> is reachable from the compute nodes you're targeting.
>
> **Staging failures are caught in under a second on the login node.**

---

## Slide 10 — Scene 4 talking points

# Scene 4 — Submit and the durable receipt

_[On screen: `run_slurm_recipe` → job_id, then `monitor_slurm_job` → COMPLETED, then pre-staged germline record]_

**Say:**

> The agent submits the frozen recipe and records the run:
> job ID, submit time, scheduler state, exit code, log paths.
>
> [Show pre-staged germline record]
>
> Six months from now, when a reviewer asks what parameters you used,
> you open the run record and show them.
> The agent didn't just run the job — it kept the receipt.

---

## Slide 11 — Scene 5 talking points

# Scene 5 — Resource failure, not science failure

_[On screen: `retry_slurm_job(resource_overrides={"memory": "48Gi"})`]_

**Say:**

> If the job fails because it ran out of memory,
> the agent retries with more resources —
> without touching the biological recipe.
>
> The retry links back to the original run.
> The chain of evidence is complete.
>
> **Resource failures and scientific decisions stay separate.**

---

## Slide 12 — How this fits with Nextflow

# The agent and your existing pipelines

_Not a replacement. An earlier step._

**The Nextflow / Snakemake pattern:**
```
Write the pipeline → encode it in DSL → run it repeatedly → trust it
```

**The agentic pattern:**
```
Describe what you want → agent selects from catalogue →
freeze recipe → validate → submit → audit
```

Both are useful. They work at different moments:

> Nextflow is excellent for pipelines you've already written and trust.
> **The agent is for the moment before that** — prototyping, validation,
> onboarding a new student, auditing a result, running a supported analysis
> without touching DSL.

> If Nextflow is the production assembly line,
> the agent is the labelled work order and inspection counter in front of it.

---

## Slide 13 — Honest scope

# What the agent can and cannot do

| The agent **can** | The agent **cannot** |
|---|---|
| Select from 45 registered, validated analyses | Invent new biological pipelines |
| Freeze a recipe and check cluster readiness before submission | Run analyses not in the catalogue |
| Submit, monitor, retry, and cancel Slurm jobs | Replace production Nextflow for 100-sample cohorts today |
| Keep a durable, reviewable run record | Send your data off-cluster (everything runs locally) |
| Help a new student run correctly-parameterised GATK without DSL knowledge | Guarantee results without human review of the frozen recipe |

&nbsp;

**The constraint is the feature.**
The agent works through registered biology, typed inputs, and frozen recipes —
not through generated shell scripts it hopes are correct.

---

## Slide 14 — Close

# The shift

_From this:_
> "Run the script and hope the parameters were right."

_To this:_
> "Describe the analysis. Inspect the frozen plan. Submit when satisfied.
> Explain the result years later."

&nbsp;

> The value is not automation by itself.
> The value is automation with **biological labels, cluster preflight,
> durable records, and restraint.**

&nbsp;

_We are asking for 30 minutes on a login node._
_A new student. A correctly-parameterised GATK run. An inspectable receipt._
_No DSL. No data off-cluster._

_If that is useful, we can talk about what analyses you actually need to run._

---

## Appendix A — Q&A cheat sheet

**"How is this different from just asking ChatGPT to write a bash script?"**
> ChatGPT generates a script it hopes is correct. This agent selects from a catalogue
> of registered, validated analyses and freezes the plan into an auditable recipe
> before anything runs. The output is inspectable and replayable — not a one-shot script.

**"Are you replacing Nextflow or Snakemake?"**
> No. Keep them for hardened, cohort-scale pipelines. The agent is most useful
> before a pipeline has been hardened — prototyping, validation, onboarding,
> auditing — and for analyses you want to run without editing workflow code.

**"What stops the agent from doing something wrong?"**
> The catalogue. The agent can only propose analyses that are registered and
> validated. Every run is frozen into a reviewable recipe before submission.
> You inspect it before anything runs on the cluster.

**"Does data leave the cluster?"**
> No. The agent calls tools on a server running in your cluster session.
> Nothing is uploaded to Anthropic or any external service.

**"Who maintains this when you leave?"**
> The codebase is documented in AGENTS.md, DESIGN.md, and .codex/.
> A scaffold agent can produce a new registered task from a short intent description.
> New students can add biology without understanding the Slurm or MCP layers.

**"How do I know the GATK parameters are correct?"**
> Each task enforces the documented GATK4 Best Practices command shape.
> The test suite (885+ tests) verifies parameter passing for every task.
> The biological choices are in code and in the registry — not in someone's memory.

**"What's next?"**
> Job-array scatter for 100-sample fan-out (Milestone K), VEP annotation,
> and additional biology families. The scaffold agent makes adding new
> registered analyses a one-session task.
