# HPC Scientist & MCP User Review Prompt

You are a coding agent performing a structured usability review of the FLyteTest
bioinformatics platform. Read the files listed below, then produce a critique from
two distinct perspectives. Do not implement fixes — only report findings.

---

## Files to read before reviewing

**Platform surface:**
- `AGENTS.md` — agent and MCP client guidance
- `src/flytetest/mcp_contract.py` — MCP tool names, descriptions, policy constants
- `src/flytetest/bundles.py` — curated resource bundles (what a scientist loads first)
- `src/flytetest/planning.py` — how prompts are classified and declined
- `src/flytetest/server.py` — `run_task`, `run_workflow`, `load_bundle`, `run_slurm_recipe`
  tool implementations; `TASK_PARAMETERS`; `_execute_run_tool`

**Pipeline specifics:**
- `src/flytetest/registry/_variant_calling.py` — all 21 tasks and 11 workflows,
  their `execution_defaults`, `module_loads` hints, `slurm_resource_hints`,
  `InterfaceField` descriptions
- `src/flytetest/tasks/variant_calling.py` — task signatures and `_sif` parameters
- `src/flytetest/workflows/variant_calling.py` — workflow signatures

**Staging and HPC:**
- `scripts/rcc/stage_gatk_local.sh` — data staging script
- `scripts/rcc/check_gatk_fixtures.sh` — fixture verifier
- `scripts/rcc/pull_gatk_image.sh` — GATK SIF pull
- `scripts/rcc/build_bwa_mem2_sif.sh` — bwa-mem2 SIF build
- `scripts/rcc/pull_bcftools_sif.sh`, `pull_multiqc_sif.sh`, `pull_snpeff_sif.sh`
- `src/flytetest/staging.py` — `check_offline_staging` preflight
- `src/flytetest/spec_executor.py` — `DEFAULT_SLURM_MODULE_LOADS`,
  `_slurm_module_load_lines`, Slurm script generation

**Documentation:**
- `docs/gatk_pipeline_overview.md`
- `SCIENTIST_GUIDE.md`
- `README.md`

---

## Perspective 1 — Bioinformatics Scientist on HPC

You are a dry-lab bioinformatician who runs GATK germline variant calling pipelines
on a university HPC cluster (Slurm scheduler, environment modules, shared filesystem,
2FA login — no direct internet from compute nodes). You are comfortable with GATK
Best Practices, bwa-mem2, BQSR, VQSR, and reading Slurm logs. You have never used
this platform before. Your goals:

1. Stage data and reference files for a chr20 NA12878 smoke test
2. Run `prepare_reference → preprocess_sample → germline_short_variant_discovery`
3. Monitor the jobs and retrieve results

**Examine and critique:**
- How discoverable is the end-to-end setup sequence? Can you figure out what to
  do from `README.md` and `SCIENTIST_GUIDE.md` alone, or do you need to read source?
- Are the staging scripts (`stage_gatk_local.sh`, `check_gatk_fixtures.sh`) clear
  about what they do and what order to run them in?
- Is the SIF strategy coherent? Are the relationships between `gatk4.sif`,
  `bwa_mem2.sif`, and HPC modules (`gatk/4.5.0`, `samtools/1.22.1`) explained
  anywhere a scientist would actually read?
- Do the `InterfaceField` descriptions in the registry give enough context to know
  what to pass without reading source code?
- Are `slurm_resource_hints` realistic for a WGS chr20 run? Are walltime and memory
  estimates sensible?
- Is the `module_loads` full-replacement semantics documented in a place a scientist
  would find before hitting a broken Slurm job?
- Are error messages and `PlanDecline` responses actionable (do they tell you what
  to do next, not just what went wrong)?
- What would cause a first-time user to get stuck? List specific friction points.

**Also note what works well** — patterns, defaults, or messages that are clear and
would build confidence in a new user.

---

## Perspective 2 — Scientific MCP User (experiment loop)

You are using an AI agent (OpenCode, Claude Code, or similar) connected to this
project's MCP server to drive variant calling experiments programmatically. You
interact via the MCP tools: `list_entries`, `list_bundles`, `load_bundle`,
`run_task`, `run_workflow`, `run_slurm_recipe`, `monitor_slurm_job`,
`retry_slurm_job`. You want to run an experiment, inspect the recipe before
submitting, monitor the job, and retrieve outputs.

**Examine and critique:**
- Does the experiment loop (`list_entries → list_bundles → load_bundle → run_task /
  run_workflow`) feel natural? Are there unnecessary steps or missing guardrails?
- Is `load_bundle` output self-explanatory enough to spread into `run_workflow`
  without confusion? What fields would puzzle a scientist-level user?
- Are `PlanDecline` responses specific enough to be actionable without a developer
  reading the source? Do `suggested_bundles` and `next_steps` actually help?
- Is the dry_run mode clearly surfaced and easy to use for inspecting a recipe
  before committing to Slurm submission?
- Is the handoff between `run_workflow` (freeze recipe) and `run_slurm_recipe`
  (submit) explained clearly enough that a user won't accidentally skip the
  inspect step?
- Does `monitor_slurm_job` return enough information to diagnose a failure without
  needing to SSH to the cluster?
- Is `retry_slurm_job` with `resource_overrides` discoverable enough that a user
  would find it after an OOM failure, rather than re-submitting from scratch?
- Are the MCP tool descriptions in `mcp_contract.py` (what the agent sees) accurate
  and concise, or do they contain stale references or misleading defaults?

**Also note what works well.**

---

## Output format

Structure your report as follows:

### Perspective 1: Bioinformatics Scientist
#### Friction points (ranked by severity)
#### What works well

### Perspective 2: MCP Experiment User
#### Friction points (ranked by severity)
#### What works well

### Cross-cutting observations
Issues or strengths that apply to both perspectives.

### Suggested priority fixes
A short ranked list (top 5) of the highest-impact changes, with a one-line
description of what to change and why.

Be specific — cite file names, function names, or line content where relevant.
Do not propose implementation; only identify the problems.
