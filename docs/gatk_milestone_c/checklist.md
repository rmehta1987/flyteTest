# GATK4 Germline Variant Calling — Milestone C Checklist

Tracks Milestone C of the Phase 3 GATK port described in
`docs/gatk_milestone_c/milestone_c_plan.md`.

Master plan: `docs/gatk_milestone_c/milestone_c_plan.md`
Per-step submission prompts: `docs/gatk_milestone_c/prompts/`

Use this file as the canonical shared tracker for Milestone C. Future
sessions mark steps Complete, record partial progress, and note blockers
here.

## Branch

Create a new branch `gatkport-c` before starting:
`git checkout -b gatkport-c`

Merge into `main` after all steps are complete and verification gates pass.

## Status Labels

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

## Steps

### Foundation

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 01 | Plan + checklist skeleton | `prompts/step_01_plan_and_checklist.md` | Complete |

### Cluster Prompt Tests (each: new scenarios in `docs/mcp_variant_calling_cluster_prompt_tests.md` + CHANGELOG line)

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 02 | Cluster prompt doc skeleton + sanity + single-task happy path | `prompts/step_02_cluster_prompt_sanity_and_single_task.md` | Not started |
| 03 | Workflow happy-path scenarios | `prompts/step_03_cluster_prompt_workflow_scenarios.md` | Not started |
| 04 | Cancel, retry, escalation scenarios | `prompts/step_04_cluster_prompt_lifecycle_scenarios.md` | Not started |

### Full Pipeline Refresh

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 05 | Add Variant Calling Pipeline section to `docs/mcp_full_pipeline_prompt_tests.md` | `prompts/step_05_full_pipeline_refresh.md` | Not started |

### Closure

| # | Step | Prompt | Status |
|---|------|--------|--------|
| 06 | Agent-context sweep, CHANGELOG, submission prompt, verification | `prompts/step_06_closure.md` | Not started |

## Verification Gates

Before marking Milestone C Complete, all gates in the plan's §6 must pass:

- `python -m compileall src/flytetest/`
- `pytest` full suite green
- `rg "variant_calling" docs/mcp_variant_calling_cluster_prompt_tests.md` → matches
- `rg "germline_short_variant_discovery" docs/mcp_full_pipeline_prompt_tests.md` → matches
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" docs/mcp_variant_calling_cluster_prompt_tests.md docs/mcp_full_pipeline_prompt_tests.md` → zero hits
- `rg "mcp_variant_calling_cluster_prompt_tests" AGENTS.md DESIGN.md` → matches
- Submission prompt at `docs/gatk_milestone_c_submission_prompt.md` present and ≤100 lines

## Hard Constraints

- Documentation-only milestone; no new Python, tasks, workflows, registry
  entries, or planner types.
- Do not invent task or workflow names; every `task_name` /
  `workflow_name` in a prompt must resolve to an entry in
  `VARIANT_CALLING_ENTRIES`.
- Do not copy Stargazer async/IPFS patterns.
- Do not modify frozen saved artifacts at retry/replay time.

## Out of Scope (this milestone)

- `merge_bam_alignment` — deferred.
- VQSR — deferred.
- Interval-scoped HaplotypeCaller — deferred.
- Actual fixture data in the repo — cluster-staged only.
- New smoke scripts — reuse existing `scripts/rcc/` helpers.
