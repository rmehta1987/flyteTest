# Critique follow-up — milestone plan

**Source review:** `CRITIQUE_REPORT.md` (repo root, branch `critique`).
**Scope of this milestone:** the top-5 ranked recommendations from the
synthesis section of the report. Findings 6–8 are tracked in `checklist.md`
but are not part of this milestone's primary execution.

## Goal

Reduce surface area and onboarding friction without touching biology, the
Slurm submission invariant, or `classify_slurm_failure` semantics. Every step
in this plan is documentation-shaped or a localized rename / delete; none
require changes to task or workflow modules under `src/flytetest/tasks/` or
`src/flytetest/workflows/`.

## Sequencing

The steps are independent except for step 02, which assumes step 01 has
chosen a winner between `prompt_and_run` and the experiment loop. Run them
in order:

1. **Step 01 — pick one entry point.** Decide whether `prompt_and_run` /
   `plan_request` stay registered or whether the experiment loop is the only
   start path. Based on usage telemetry or maintainer judgement; report
   answer before proceeding. See `prompts/step_01_choose_entry_point.md`.

2. **Step 02 — apply the entry-point decision.** Either un-register the
   redundant tools (preferred default) or update AGENTS.md to remove the
   experiment loop language. See `prompts/step_02_apply_entry_point.md`.

3. **Step 03 — collapse duplicate `ReferenceGenome`.** Delete one of the
   two definitions; update imports. See `prompts/step_03_dedupe_reference_genome.md`.

4. **Step 04 — strip boilerplate test docstrings + retention-prune
   `docs/archive/` and `CHANGELOG.md`.** Three small mechanical passes.
   See `prompts/step_04_prune_docs_and_tests.md`.

5. **Step 05 — scientist-onboarding glossary + end-to-end FASTQ walkthrough
   in `SCIENTIST_GUIDE.md`.** No new files. See
   `prompts/step_05_scientist_onboarding.md`.

6. **Step 06 — `format_finding(...)` helper for `StagingFinding`.** Additive;
   callers opt in. See `prompts/step_06_staging_finding_formatter.md`.

## Out of scope

- Refactoring `server.py` or `planning.py` into smaller modules.
- Splitting `spec_executor.py`. The report explicitly recommends leaving it
  alone (CRITIQUE_REPORT.md §4 "What I would NOT change").
- Adding new MCP tools, bundles, or biology coverage.
- Touching `classify_slurm_failure` or any frozen-recipe invariant.

## Acceptance

The milestone is done when:

- One of `prompt_and_run` / `plan_request` is no longer in `MCP_TOOL_NAMES`,
  *or* `AGENTS.md` no longer documents the experiment loop as the canonical
  flow (whichever the maintainer chooses in step 01).
- `rg 'class ReferenceGenome' src/flytetest/` returns one match.
- `rg -c 'This test keeps the current contract explicit' tests/` returns
  zero hits.
- `docs/archive/` retention policy is documented and enforced.
- `SCIENTIST_GUIDE.md` opens with a glossary block and a numbered first-run
  walkthrough.
- `staging.py` exports a `format_finding` (or equivalent) callable, with at
  least one caller using it.
- All 887 existing tests still pass.

## Estimated effort

~1 engineering day total, distributed across the six steps. The largest
single time sink is step 04 (retention pruning), which is mostly mechanical
file operations + git history checks.

## Step 01 decision (recorded 2026-04-26)

**Canonical entry point: the experiment loop**
(`list_entries → list_bundles → load_bundle → run_task / run_workflow`).

**Loser: `prompt_and_run` and `plan_request`** — un-register from
`MCP_TOOL_NAMES` (drop from `LIFECYCLE_TOOLS` in `mcp_contract.py:87–100`
and the `mcp.tool` registrations in `server.py:4417–4438`). Keep the
Python function definitions so the ~36 existing tests and any internal
callers continue to work; only the MCP surface registration goes away.
Also drop `PRIMARY_TOOL_NAME` since nothing should claim primacy on the
inspect-before-execute lane.

**Evidence:**
- `AGENTS.md:138` documents only the experiment loop as the scientist's
  flow. `SCIENTIST_GUIDE.md` and `README.md` reference neither
  `prompt_and_run` nor `plan_request` (zero matches).
- `mcp_contract.py:69–75` already groups the loop tools under a dedicated
  `EXPERIMENT_LOOP_TOOLS` tuple with a docstring describing it as the
  scientist's path.
- `prompts/step_02_apply_entry_point.md:9` labels "drop `prompt_and_run` /
  `plan_request`" as the **default case** — the plan author already
  anticipated this outcome.
- No telemetry available; absence from all user-facing docs is the
  best available proxy that no external client has wired into them.

**Risk acknowledged:** if a script or external client is calling
`prompt_and_run` over MCP, it will get an unknown-tool error after step
02. Reversible by re-adding to the tuple.
