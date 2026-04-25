# Critique follow-up — checklist

Source: `CRITIQUE_REPORT.md`, ranked synthesis.

## Primary milestone (this folder's plan)

- [ ] **Step 01 — choose entry point.** Decide between `prompt_and_run` /
  `plan_request` and the documented `list_entries → list_bundles →
  load_bundle → run_task / run_workflow` loop. [ENG-01]
- [ ] **Step 02 — apply the decision.** Un-register the loser from
  `MCP_TOOL_NAMES` *or* edit AGENTS.md to drop the loop language. [ENG-01]
- [ ] **Step 03 — collapse duplicate `ReferenceGenome`.** Delete one
  definition (`src/flytetest/planner_types.py:42` *or*
  `src/flytetest/types/assets.py:49`); update imports. [ENG-02]
- [ ] **Step 04a — strip boilerplate test docstrings.** Delete every
  occurrence of "This test keeps the current contract explicit and guards
  the documented behavior against regression." [ENG-05]
- [ ] **Step 04b — retention-prune `docs/archive/`.** Add
  `docs/archive/README.md` retention paragraph; delete entries older than
  the cutoff (60 days suggested). [ENG-04]
- [ ] **Step 04c — split `CHANGELOG.md`.** Move entries older than the
  cutoff into `CHANGELOG.archive.md`; keep the current file under ~500
  lines. [ENG-09]
- [ ] **Step 05a — glossary block at top of `SCIENTIST_GUIDE.md`.** Five
  one-line definitions: recipe, bundle, manifest, run record, execution
  profile. [SCI-01]
- [ ] **Step 05b — numbered first-run FASTQ walkthrough in
  `SCIENTIST_GUIDE.md`.** Use `variant_calling_germline_minimal` as the
  example bundle. [SCI-05]
- [ ] **Step 06 — `format_finding(...)` helper in
  `src/flytetest/staging.py`.** Additive; one caller updated. [SCI-04]

## Secondary (track but not this milestone)

- [ ] Merge `manifest_envelope.py` + `manifest_io.py` into `manifest.py`.
  [ENG-03]
- [ ] Introduce `RecipeId = NewType("RecipeId", str)` and thread through
  public signatures. [ENG-07]
- [ ] Rename or delete `m18_busco_demo` bundle. [SCI-02]
- [ ] Move `.codex/tutorial_context.md` to `.codex/agent/` *or* split the
  agent-meta from biology content. [ENG-10]
- [ ] Add 5-line module docstrings clarifying `planning.py` vs.
  `composition.py` boundary. [ENG-08]
- [ ] Decide on `PlannerResolutionError` 5-classes-vs-4-handlers split.
  [ENG-06]

## Open questions to resolve before starting

- [ ] Confirm `prompt_and_run` usage in real clients (telemetry or
  maintainer recall).
- [ ] Confirm `composition.py` reachability from the MCP surface (grep).
- [ ] Inspect `docs/archive/Prompts/` — keep or delete?
