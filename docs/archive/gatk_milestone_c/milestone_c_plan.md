# GATK4 Germline Variant Calling — Milestone C

Cluster validation prompt set for the variant_calling family, plus a refresh
of `docs/mcp_full_pipeline_prompt_tests.md` so the raw-reads → joint-VCF path
is exercised end-to-end through the live MCP server on RCC.

Source-of-truth references:

- `AGENTS.md` — hard constraints, efficiency notes, core rules.
- `DESIGN.md` — biological pipeline boundaries, planner types.
- Milestone A plan: `docs/gatk_milestone_a/milestone_a_plan.md`.
- Milestone B plan: `docs/gatk_milestone_b/milestone_b_plan.md`.
- Existing cluster prompt file: `docs/mcp_cluster_prompt_tests.md`.
- Existing full-pipeline prompt file: `docs/mcp_full_pipeline_prompt_tests.md`.

## §1 Context

Milestone A delivered the seven GATK4 tasks (BQSR → HaplotypeCaller →
CombineGVCFs → joint calling) and the `variant_calling` registry family.
Milestone B added the upstream preprocessing tasks (`bwa_mem2_index`,
`bwa_mem2_mem`, `sort_sam`, `mark_duplicates`) and the three workflow
compositions (`prepare_reference`, `preprocess_sample`,
`germline_short_variant_discovery`), plus the
`variant_calling_germline_minimal` fixture bundle and
`scripts/rcc/pull_gatk_image.sh`.

Milestone C is **documentation-only** — no new Python, no new registry
entries, no new planner types. It produces the prompt artifacts that a
scientist pastes into OpenCode (or any MCP client) to exercise the live
cluster surface for the variant_calling family.

- **Milestone A** (complete) — seven GATK4 tasks + registry family.
- **Milestone B** (complete) — four preprocessing tasks, three workflows,
  fixture bundle, container-pull script.
- **Milestone C** (this plan) — cluster prompt tests doc,
  full-pipeline prompt tests refresh, agent-context sweep, submission
  prompt.

## §2 Pillars / Invariants (carried from Milestones A and B)

1. **Freeze before execute.** Every prompt drives the MCP server through
   `run_task` / `run_workflow` / `prepare_run_recipe`, which freeze a
   `WorkflowSpec` before any `sbatch`.
2. **Typed surfaces everywhere.** Prompts pass typed bindings
   (`ReferenceGenome`, `ReadPair`, `KnownSites`) and typed inputs; no ad
   hoc string dicts outside the documented shape.
3. **Manifest envelope per task.** Scenarios verify `run_manifest.json`
   exists in the result bundle and carries the registry's documented
   output keys.
4. **No Stargazer-pattern bleed-in.** No `await`, `.cid`, IPFS, TinyDB,
   or Pinata wording appears in any Milestone C doc.

## §3 Deliverables

### New files

- `docs/mcp_variant_calling_cluster_prompt_tests.md` — the live-cluster
  scenario set (sanity → happy path → workflow → cancel → retry →
  escalation) for the variant_calling family.
- `docs/gatk_milestone_c_submission_prompt.md` — ≤100-line milestone
  submission prompt (mirrors the A/B submission prompt format).

### Refreshed files

- `docs/mcp_full_pipeline_prompt_tests.md` — adds a companion
  **Variant Calling Pipeline** section (raw reads → joint-called VCF) that
  runs alongside the existing annotation pipeline. Existing annotation
  stages are preserved verbatim.
- `AGENTS.md` — documents the new prompt file in the Project Structure
  section.
- `DESIGN.md` — §5.6 picks up a Milestone C note pointing at the new
  cluster prompt file.
- `CHANGELOG.md` — milestone-level closing entry under `## Unreleased`.

## §4 Out of Scope (this milestone)

- No new Python, tasks, workflows, registry entries, or planner types.
- No change to `classify_slurm_failure()` semantics.
- No new smoke scripts under `scripts/rcc/`. Reuse
  `pull_gatk_image.sh` and `make_m18_retry_smoke_record.sh` verbatim.
- `merge_bam_alignment` and VQSR remain deferred.
- Actual fixture data on the cluster is still staged out-of-repo; the
  prompts assume `variant_calling_germline_minimal` paths resolve.

## §5 Steps

### Foundation

| # | Step | Prompt |
|---|------|--------|
| 01 | Plan + checklist skeleton | `prompts/step_01_plan_and_checklist.md` |

### Cluster Prompt Tests

| # | Step | Prompt |
|---|------|--------|
| 02 | Cluster prompt doc skeleton + sanity + single-task happy path | `prompts/step_02_cluster_prompt_sanity_and_single_task.md` |
| 03 | Workflow happy-path scenarios (prepare_reference, preprocess_sample, germline_short_variant_discovery) | `prompts/step_03_cluster_prompt_workflow_scenarios.md` |
| 04 | Cancel, retry, and escalation scenarios | `prompts/step_04_cluster_prompt_lifecycle_scenarios.md` |

### Full Pipeline Refresh

| # | Step | Prompt |
|---|------|--------|
| 05 | Add Variant Calling Pipeline section to `docs/mcp_full_pipeline_prompt_tests.md` | `prompts/step_05_full_pipeline_refresh.md` |

### Closure

| # | Step | Prompt |
|---|------|--------|
| 06 | Agent-context sweep, CHANGELOG, submission prompt, verification | `prompts/step_06_closure.md` |

## §6 Verification Gates

All must pass before marking Milestone C complete:

- `python -m compileall src/flytetest/` clean (sanity — no Python changed).
- `pytest` full suite green (sanity — no tests changed).
- `rg "variant_calling" docs/mcp_variant_calling_cluster_prompt_tests.md` → matches.
- `rg "germline_short_variant_discovery" docs/mcp_full_pipeline_prompt_tests.md` → matches.
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" docs/mcp_variant_calling_cluster_prompt_tests.md docs/mcp_full_pipeline_prompt_tests.md` → zero hits.
- `rg "mcp_variant_calling_cluster_prompt_tests" AGENTS.md DESIGN.md` → matches.
- Submission prompt at `docs/gatk_milestone_c_submission_prompt.md` present and ≤100 lines.

## §7 Hard Constraints

- No frozen-artifact mutation at retry/replay time.
- No Slurm submit without a frozen run record (all prompts drive through
  MCP tools that freeze before submit).
- No change to `classify_slurm_failure()` semantics.
- Milestone C adds no Python. If a step prompt appears to require code
  changes, stop and escalate — the scope is documentation-only.
- No invented task or workflow names. Every `task_name` / `workflow_name`
  in a prompt must resolve to an entry in `VARIANT_CALLING_ENTRIES`.
