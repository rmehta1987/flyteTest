# Step 05 — Scientist onboarding pass

Two sub-steps, both editing `SCIENTIST_GUIDE.md`. No new files.

## 05a — Glossary block [SCI-01]

Add at the top of `SCIENTIST_GUIDE.md`, immediately after the document
title:

```markdown
## Glossary

- **Recipe** — a frozen, JSON-serializable plan describing exactly what
  will run. Once a recipe exists, nothing about the run is invented at
  submit time.
- **Bundle** — a curated set of inputs (reference, evidence, intervals,
  containers) that turns a registered task or workflow into a one-call
  starter kit. See `list_bundles`.
- **Manifest** — the per-stage record of inputs, outputs, and tool
  versions written by every task. Provenance lives here.
- **Run record** — the durable record of a Slurm submission: job ID,
  stdout / stderr paths, lifecycle state, exit code.
- **Execution profile** — `local` or `slurm`. Picks the executor and
  governs whether `check_offline_staging` enforces shared-filesystem
  reachability.
```

Each definition must be one line. Do not nest sub-bullets. Do not use
emoji.

## 05b — End-to-end FASTQ walkthrough [SCI-05]

Add a section "First run, end-to-end" that walks one bundle from
`load_bundle` through `monitor_slurm_job`. Use `variant_calling_germline_minimal`
as the worked example. Numbered steps. Include the actual MCP calls:

```text
1. list_entries(category="workflow", pipeline_family="variant_calling")
2. list_bundles(applies_to="germline_short_variant_discovery")
3. load_bundle("variant_calling_germline_minimal")
4. run_workflow(**bundle, dry_run=True)        # inspect frozen recipe
5. validate_run_recipe(recipe_id=...)          # preflight staging
6. run_slurm_recipe(recipe_id=..., partition=..., account=...)
7. monitor_slurm_job(job_id=...)
```

For each step, two-to-three lines explaining what the scientist sees and
what could go wrong. Cite `staging.py` for preflight failures.

Acceptance:
- `SCIENTIST_GUIDE.md` opens with the glossary block.
- A "First run, end-to-end" section exists with the seven-step flow above.
- A scientist who has never used the project can read the section linearly
  without needing other docs (verify by re-reading it cold).

Commit: `critique-followup: add scientist glossary and first-run walkthrough`
