# Critique follow-up — checklist

Source: `CRITIQUE_REPORT.md`, ranked synthesis.

## Primary milestone (this folder's plan)

- [x] **Step 01 — choose entry point.** Decide between `prompt_and_run` /
  `plan_request` and the documented `list_entries → list_bundles →
  load_bundle → run_task / run_workflow` loop. [ENG-01]
  (2026-04-26: experiment loop wins; un-register `prompt_and_run` and
  `plan_request`. Decision recorded in `critique-followup_plan.md`.)
- [x] **Step 02 — apply the decision.** Un-register the loser from
  `MCP_TOOL_NAMES` *or* edit AGENTS.md to drop the loop language. [ENG-01]
  (2026-04-26: removed `plan_request` and `PRIMARY_TOOL_NAME` from
  `LIFECYCLE_TOOLS`; deleted both `mcp.tool` registrations in
  `server.py:create_mcp_server`; Python definitions retained.)
- [x] **Step 03 — collapse duplicate `ReferenceGenome`.** Delete one
  definition (`src/flytetest/planner_types.py:42` *or*
  `src/flytetest/types/assets.py:49`); update imports. [ENG-02]
  (2026-04-26: kept `planner_types` version; assets version was a
  strict subset; updated 5 import sites + 1 serialization snapshot.)
- [x] **Step 04a — strip boilerplate test docstrings.** Delete every
  occurrence of "This test keeps the current contract explicit and guards
  the documented behavior against regression." [ENG-05]
  (2026-04-26: 230 occurrences removed across 25 test files; class-level
  "This test class keeps..." variant out of scope.)
- [x] **Step 04b — retention-prune `docs/archive/`.** Add
  `docs/archive/README.md` retention paragraph; delete entries older than
  the cutoff (60 days suggested). [ENG-04]
  (2026-04-26: README rewritten with 60-day policy + prune workflow; no
  deletions — oldest entry is 20 days old; file count 50 already <80
  target; first eligible pruning date is 2026-06-05.)
- [x] **Step 04c — split `CHANGELOG.md`.** Move entries older than the
  cutoff into `CHANGELOG.archive.md`; keep the current file under ~500
  lines. [ENG-09]
  (2026-04-26: 1932 → ~530 lines; cut between GATK Milestone A and
  older Track A / MCP Reshape blocks; archive file 1409 lines.)
- [x] **Step 05a — glossary block at top of `SCIENTIST_GUIDE.md`.** Five
  one-line definitions: recipe, bundle, manifest, run record, execution
  profile. [SCI-01]
  (2026-04-26: glossary inserted between title and TL;DR.)
- [x] **Step 05b — numbered first-run FASTQ walkthrough in
  `SCIENTIST_GUIDE.md`.** Use `variant_calling_germline_minimal` as the
  example bundle. [SCI-05]
  (2026-04-26: 7-call walkthrough inserted between experiment-loop
  overview and prior-run reuse; each step cites failure modes;
  preflight step cites staging.py:check_offline_staging.)
- [x] **Step 06 — `format_finding(...)` helper in
  `src/flytetest/staging.py`.** Additive; one caller updated. [SCI-04]
  (2026-04-26: helper added; `validate_run_recipe` now adds a `message`
  key to each staging finding dict; 3 new unit tests pass; total 905.)

## Secondary (track but not this milestone)

- [x] Merge `manifest_envelope.py` + `manifest_io.py` into `manifest.py`.
  [ENG-03]
  (2026-04-27: consolidated both modules into `src/flytetest/manifest.py`;
  8 importers updated; 2 test files merged into `tests/test_manifest.py`;
  test count unchanged at 905 passed; DESIGN.md project-structure block
  updated.)
- [x] Introduce `RecipeId = NewType("RecipeId", str)` and thread through
  public signatures. [ENG-07]
  (2026-04-27: alias added in `spec_artifacts.py` next to `make_recipe_id`;
  exported via `__all__`. Annotated 5 public surfaces: `make_recipe_id`
  return, `RunReply.recipe_id`, `DryRunReply.recipe_id`,
  `ValidateRecipeReply.recipe_id`, `SlurmRunRecord.recipe_id`. Private
  sbatch render helpers kept on bare `str`. NewType is runtime-free; tests
  unchanged at 903 passed.)
- [x] Rename or delete `m18_busco_demo` bundle. [SCI-02]
  (2026-04-26: renamed to `busco_protein_qc_minimal`; 12 refs updated.)
- [x] Move `.codex/tutorial_context.md` to `.codex/agent/` *or* split the
  agent-meta from biology content. [ENG-10]
  (2026-04-27: Option A — moved to `.codex/agent/tutorial_context.md`; ~89%
  agent-meta, biology content is enumerative supporting context for the
  prompt templates and not separable. 7 active call sites updated; 17
  internal self-references rewritten.)
- [x] Add 5-line module docstrings clarifying `planning.py` vs.
  `composition.py` boundary. [ENG-08]
  (2026-04-26: boundary paragraph added to both module docstrings.)
- [x] Decide on `PlannerResolutionError` 5-classes-vs-4-handlers split.
  [ENG-06]
  (2026-04-27: Option A — collapsed to 4/4. `ManifestNotFoundError` merged
  into `BindingPathMissingError` with a `kind: Literal["raw_path",
  "manifest"]` field that picks the message prefix. Three raise sites in
  `resolver.py` updated; translator at `server.py:1246` becomes single-class
  `except`. No public-surface change — `PlanDecline` carries no category
  field; SCIENTIST_GUIDE/DESIGN/README never named the dropped class. Tests:
  903 passed, 1 skipped (was 905 — net −2 from removed standalone-identity
  tests of the merged class; new `kind="manifest"` coverage added).)

## Open questions to resolve before starting

- [x] Confirm `prompt_and_run` usage in real clients (telemetry or
  maintainer recall).
  (2026-04-27: ENG-01 step 02 deregistration is effective — no
  `@mcp.tool` registration remains for `prompt_and_run`, and
  `MCP_TOOL_NAMES = EXPERIMENT_LOOP_TOOLS + INSPECT_TOOLS +
  LIFECYCLE_TOOLS` no longer contains it. Python definitions and tests
  are retained as documentation/regression coverage; the contract
  resource at `server.py:4445` still surfaces a docs-only description
  but is not an executable surface. No active client path exists.)
- [x] Confirm `composition.py` reachability from the MCP surface (grep).
  (2026-04-27: reachable transitively. `src/flytetest/composition.py`
  is imported only by `src/flytetest/planning.py:39`
  (`from flytetest.composition import compose_workflow_path`), and
  `planning.py` is on the MCP server import path. This matches the
  ENG-08 boundary docstrings: planning is the entrypoint that
  classifies and freezes; composition is the bounded graph search
  planning calls when no single registered entry matches.)
- [x] Inspect `docs/archive/Prompts/` — keep or delete?
  (2026-04-27: KEEP. 38 historical submission prompts; oldest Apr 16,
  youngest Apr 24 (3–11 days old). All within the 60-day retention
  window set by ENG-04. First eligible pruning date: 2026-06-05.
  `Prompts/` capitalization is unusual but a rename would be churn-
  only. No action needed now.)
