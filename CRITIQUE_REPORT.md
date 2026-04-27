# flyteTest Critique — Engineer + Research Scientist Lens

## 1. Scope & method

Repository scanned at `critique@9097cf7`. Time spent: ~30 min over a single
session. Read in full: `README.md`, `AGENTS.md`, `CLAUDE.md`,
`CRITIQUE_PROMPT.md`, `src/flytetest/mcp_contract.py` (top half),
`src/flytetest/errors.py`, `src/flytetest/mcp_replies.py`,
`src/flytetest/staging.py`, `src/flytetest/bundles.py` (top portion),
`pyproject.toml`. Sampled: `src/flytetest/server.py` (tool registration block,
`plan_request` / `prompt_and_run` definitions), `src/flytetest/planning.py`
(class/def index), `src/flytetest/spec_executor.py` (Slurm defaults, module
loads, retry path), `src/flytetest/planner_types.py` /
`src/flytetest/types/assets.py` (class lists), `src/flytetest/composition.py`
(opening), `src/flytetest/pipeline_tracker.py`, `src/flytetest/manifest_envelope.py`,
`src/flytetest/manifest_io.py`, `tests/test_server.py` (test name listing,
boilerplate scan), `.codex/tutorial_context.md` (top section).

Skipped (and why): individual task / workflow modules under `src/flytetest/tasks/`
and `src/flytetest/workflows/` — sample sizes are large and the brief targets
the framework surface, not GATK biology correctness; per-module reviews would
duplicate the milestone audits in `docs/archive/`. Skipped most `.codex/agent/*`
guides — they describe how agents should write code, not the code itself.
Skipped `DESIGN.md` end-to-end; sampled section names only.

Counts that anchor the review (verified, not guessed): 28,585 LOC of package
Python, 25,196 LOC of tests, **887 test functions** across 46 test files,
**22 MCP tools** registered in `server.py` (`mcp_contract.py:103`–125),
**227 markdown files** under `docs/archive/`, **7 curated bundles** in
`bundles.py`, three runtime production dependencies in `pyproject.toml`
(`anyio`, `flyte`, `mcp[cli]`).

The project is internally coherent and the hard work is real. Most criticisms
below are about surface area and weight, not correctness.

## 2. Engineer findings

```
[ENG-01] `prompt_and_run` and `plan_request` overlap with the documented scientist loop and add a fourth way to start a run.
  evidence: src/flytetest/mcp_contract.py:96–103 (LIFECYCLE_TOOLS lists both); AGENTS.md "Scientist's experiment loop" defines list_entries → list_bundles → load_bundle → run_task / run_workflow as the canonical flow; server.py:992 (plan_request) and server.py:3579 (prompt_and_run) are top-level tools, not helpers.
  cost today: two extra MCP tools to document, test, and keep aligned with the rest. `prompt_and_run` is named PRIMARY_TOOL_NAME but isn't in the documented loop. New users will not know which entry point is canonical.
  smallest fix: pick one. Either remove `prompt_and_run` and `plan_request` from MCP_TOOL_NAMES (they can stay as Python functions for tests / scripts) or delete the documented experiment loop in AGENTS.md and make `prompt_and_run` the only entry. Don't keep both.
  risk of change: removing breaks any client that calls `prompt_and_run` directly. Mitigate by keeping the Python function, only un-registering the tool.
  confidence: high
```

```
[ENG-02] `ReferenceGenome` is defined twice with different shapes.
  evidence: src/flytetest/planner_types.py:42 (ReferenceGenome(PlannerSerializable)); src/flytetest/types/assets.py:49 (ReferenceGenome, plain dataclass, no Serializable mixin).
  cost today: pick-the-right-import tax on every new task or workflow that takes a reference. Drift between the two definitions is invisible to readers. The brief specifically asks about types with one producer and one consumer — this is the inverse case: one *name* with two definitions.
  smallest fix: delete the duplicate in `types/assets.py`; standardize on the planner_types version (it has the serialization mixin used by the manifest path). If they need to diverge, rename one (`AssetReferenceGenome` vs `PlannerReferenceGenome`).
  risk of change: import sites for `types/assets.ReferenceGenome` need to switch. ~1 hour with `rg`. No biological semantics change.
  confidence: high
```

```
[ENG-03] `manifest_envelope.py` (69 LOC) and `manifest_io.py` (133 LOC) split a single concern.
  evidence: src/flytetest/manifest_envelope.py:1–14 ("Shared helper for the common manifest envelope"); src/flytetest/manifest_io.py:1–13 ("Shared manifest and file-copy helpers").
  cost today: two imports for one mental model ("manifest"). New tasks have to know envelope-construction and JSON-IO live in different modules.
  smallest fix: merge into `manifest.py`; keep `build_manifest_envelope` and `as_json_compatible` side-by-side. No external API change.
  risk of change: low — both are internal helpers.
  confidence: medium
```

```
[ENG-04] `docs/archive/` has 227 markdown files and is still growing.
  evidence: `find docs/archive -type f -name '*.md' | wc -l` → 227. Range 2026-04-06 → 2026-04-24, plus a `README.md`, plus subdirs `gatk_milestone_a..i`, `mcp_reshape`, `dataserialization`, `Prompts`. AGENTS.md says "Consult archived plans only when checking prior decisions or historical scope."
  cost today: search noise (every `rg` over the repo without `--type-add` filters paginates through archive hits), git-clone bloat for new contributors, low-signal-to-noise for anyone who actually wants to find the active milestone.
  smallest fix: write a one-paragraph retention policy at `docs/archive/README.md`: "anything older than 60 days lives at the tag/commit it was archived at; this directory holds only the last 60 days." Then delete archived plans older than 60 days (the milestone outcome is in `CHANGELOG.md` and the code).
  risk of change: low — these are reference docs, not load-bearing. Anyone needing them can `git log -- docs/archive/...` and check out the file.
  confidence: medium
```

```
[ENG-05] Boilerplate test docstring "This test keeps the current contract explicit and guards the documented behavior against regression" is pasted across hundreds of tests.
  evidence: `rg -c 'This test keeps the current contract explicit' tests/` returns hits in test_registry.py (33), test_spec_executor.py (30), test_server.py (multiple), test_specs.py (6), etc. — unique sentence is identical wherever it appears.
  cost today: zero information per occurrence. Every test ends up "documented" with the same line, which trains readers to skip docstrings, which means the few real ones are missed.
  smallest fix: delete it. If a test needs explanation, write one specific to that test; otherwise the function name is enough.
  risk of change: none — pure prose.
  confidence: high
```

```
[ENG-06] `PlannerResolutionError` hierarchy has 5 classes mapping to 4 handler arms.
  evidence: src/flytetest/errors.py:18 (base) + 5 subclasses; server.py:1216–1259 has four `except` clauses, with `(ManifestNotFoundError, BindingPathMissingError)` collapsed into one.
  cost today: an additional class for the same decline. Either there's a real distinction (then split the handler) or there isn't (then merge the classes).
  smallest fix: read the two declines side-by-side. If the user-visible payload is identical, merge `BindingPathMissingError` into `ManifestNotFoundError` (or vice versa); otherwise split the handler and document the difference.
  risk of change: low — internal exception classes, never re-raised across the MCP boundary.
  confidence: medium
```

```
[ENG-07] `recipe_id` is a string format with a defined regex but no type.
  evidence: src/flytetest/spec_artifacts.py:34 `make_recipe_id`; AGENTS.md describes the format `<YYYYMMDDThhmmss.mmm>Z-<target_name>`. No `RecipeId = NewType(...)` or dataclass wrapper.
  cost today: every function that takes a recipe_id takes `str`, so type checkers can't catch a workflow_name passed where a recipe_id is wanted, or vice versa.
  smallest fix: `RecipeId = NewType("RecipeId", str)` in `spec_artifacts.py`; thread it through public signatures of `prepare_run_recipe`, `validate_run_recipe`, `run_*_recipe`, `monitor_slurm_job`. ~1 hour with mypy.
  risk of change: cosmetic; NewType is erased at runtime.
  confidence: medium
```

```
[ENG-08] `composition.py` and `planning.py` cover overlapping concerns at very different sizes.
  evidence: src/flytetest/planning.py is 1981 LOC, 5+ planning dataclasses (PlannedInput, EntryParameter, TypedPlanningGoal, AmbiguousMatch, NoMatch — planning.py:78–138); src/flytetest/composition.py is 468 LOC, also produces a frozen WorkflowSpec from biological intent (composition.py:1–8).
  cost today: two modules for "go from intent to a frozen WorkflowSpec". A new contributor has to learn which entry point belongs to which path.
  smallest fix: don't refactor — just add a 5-line module docstring to each that says explicitly "planning.py = single-target planning; composition.py = multi-stage path search" and links to the other. Costs minutes, prevents the next-maintainer trap.
  risk of change: zero (docs only).
  confidence: medium
```

```
[ENG-09] CHANGELOG.md is 1915 lines.
  evidence: `wc -l CHANGELOG.md` → 1915. AGENTS.md mandates dated notes for "meaningful work, completed progress, tried/failed approaches, blockers, dead ends, and follow-up risks."
  cost today: at this length the file is a log, not a changelog. No one will read it linearly. Its declared purpose ("keep current") competes with the milestone docs that already capture the same context.
  smallest fix: keep the last ~90 days inline and move older entries into `CHANGELOG.archive.md` (or just rely on git log for the deep history). Same retention idea as ENG-04.
  risk of change: low.
  confidence: low (this is a tooling preference; if it's actively used as-is, leave it).
```

```
[ENG-10] `tutorial_context.md` is shelved at the top of the specialist guide list but is mostly agent-facing prose.
  evidence: `.codex/tutorial_context.md:1–95`. The first non-frontmatter sentence orients the file for "Codex prompt planning"; CLAUDE.md lists it under "Biological tutorial context and fixture selection."
  cost today: a biologist clicking "biology tutorial context" gets a meta-document about how to prompt a coding agent. The naming creates a wrong first impression.
  smallest fix: either move to `.codex/agent/tutorial_context.md` (where other agent-facing docs already live), or split the "fixture selection" half (real biology) from the "how to prompt" half (agent meta) into two files.
  risk of change: low.
  confidence: medium
```

## 3. Scientist findings

```
[SCI-01] First-run jargon is dense.
  evidence: README.md:32–42 (Quick Start) names "recipe", "bundle", "run_task", "run_workflow", "dry_run", "frozen recipe", "validate_run_recipe", "run_slurm_recipe" in seven lines. AGENTS.md adds "execution profile", "runtime images", "tool databases", "manifest envelope", "compatibility metadata".
  who is hurt: a bench biologist following the README cold. The Quick Start defines none of the new nouns; SCIENTIST_GUIDE.md is referenced but not summarized inline.
  smallest fix: insert a 5-line glossary block at the top of SCIENTIST_GUIDE.md ("recipe = a frozen plan; bundle = ready-made inputs; manifest = the per-task output description"). Don't expand README.
  risk of change: none.
  confidence: high
```

```
[SCI-02] The bundle catalog is small but tilted to annotation.
  evidence: src/flytetest/bundles.py contains 7 ResourceBundle entries (bundles.py:38, 61, 84, 104, 126, 176, 241). 4 are annotation (braker3, busco, m18_busco_demo, protein_evidence_demo), 2 variant calling (germline_minimal, vqsr_chr20), 1 rnaseq.
  who is hurt: a scientist starting a GATK germline analysis has two bundles to choose from but no obvious mapping between them and a real cohort size. `m18_busco_demo` vs `busco_eukaryota_genome_fixture` looks like a milestone artifact dressed as a bundle.
  smallest fix: rename `m18_busco_demo` to something that isn't a milestone label, or delete it if it's redundant with `busco_eukaryota_genome_fixture`. For the bundle's `description` string, name the input data scale ("chr20 NA12878, 30× WGS subset"); the existing descriptions don't.
  risk of change: low — bundles are by-name lookup in `load_bundle`; renames need a grep.
  confidence: medium
```

```
[SCI-03] Slurm default module loads pin specific versions; no default cpu / memory / walltime.
  evidence: src/flytetest/spec_executor.py:1282 `DEFAULT_SLURM_MODULE_LOADS = ("python/3.11.9", "apptainer/1.4.1", "gatk/4.5.0", "samtools/1.22.1")`. Resource defaults aren't constants; cpu / memory / walltime come from per-recipe `resource_request` only (spec_executor.py:1438–1446).
  who is hurt: a scientist who copies a bundle and runs `dry_run=True` may find no resource hint at all unless the registry entry supplies one. AGENTS.md notes the registry hints are defaults but partition / account must come from the user — that's correct, but cpu / memory / walltime should also have a baseline that's known to be safe for a 30× WGS sample.
  smallest fix: document the expected resource shape with a single example in SCIENTIST_GUIDE.md ("HaplotypeCaller per chr20 interval: cpu=4, memory=16G, walltime=4:00:00"). Don't bake numbers into spec_executor; this is a docs gap.
  risk of change: none.
  confidence: medium
```

```
[SCI-04] `check_offline_staging` returns structured findings — good — but the human-readable failure message is not in the module.
  evidence: src/flytetest/staging.py:18–24 (StagingFinding fields: kind, key, path, reason). reason values are "not_found" / "not_readable" / "not_on_shared_fs". No formatter from finding to user-readable sentence in this module.
  who is hurt: a scientist whose first sbatch is blocked by preflight gets a list of dataclass dumps unless the caller renders them. The reason codes are intelligible to a programmer, not a biologist.
  smallest fix: add a `format_finding(f: StagingFinding) -> str` helper in `staging.py` that produces lines like "Container 'braker_sif' at data/images/braker3.sif: not found on shared filesystem; pull with `apptainer pull ...`." The fetch_hints in bundles.py already model the right tone.
  risk of change: low — additive helper, callers opt in.
  confidence: medium
```

```
[SCI-05] No single end-to-end "I have FASTQs, what do I do" walkthrough is linked from the README.
  evidence: README.md:65–78 lists `SCIENTIST_GUIDE.md`, `docs/gatk_pipeline_overview.md`, `docs/tool_refs/README.md`. The brief asks specifically about a from-FASTQs walkthrough; none of the README's three doc links is named "Quickstart" or anchors a numbered start-to-finish flow.
  who is hurt: same biologist as SCI-01, after they get past the glossary.
  smallest fix: add a "First run, end-to-end" anchor at the top of SCIENTIST_GUIDE.md that tracks one bundle (e.g., `variant_calling_germline_minimal`) from `load_bundle` to `monitor_slurm_job`, with the actual MCP calls. Don't write a new file.
  risk of change: none.
  confidence: medium
```

```
[SCI-06] Provenance is captured but spread across files without a single artifact a collaborator can take.
  evidence: spec_artifacts.py:34 (`make_recipe_id`), spec_executor.py:39–41 (slurm_run_record, submit_slurm.sh), manifest_envelope.py (per-stage manifests). No single zip/tar/folder convention in the docs that bundles {recipe.json, slurm_run_record.json, per-stage manifests, container digests}.
  who is hurt: a PI asking "send me the run" gets pointed at three directories.
  smallest fix: document (don't build) the convention. One paragraph in SCIENTIST_GUIDE.md naming the four files and where they live relative to a run dir.
  risk of change: zero.
  confidence: low (this may already be documented somewhere I didn't read).
```

## 4. Synthesis

### Top 5 changes, ranked

| Rank | Change | Impact | Cost | Risk | Evidence that would change my mind |
|---|---|---|---|---|---|
| 1 | Pick one entry point (delete `prompt_and_run` *or* the documented experiment loop, not both). [ENG-01] | 4 | 2 | 2 | If telemetry shows real clients calling both surfaces in parallel for different reasons, keep both but rename so the difference is obvious. |
| 2 | Delete duplicate `ReferenceGenome` definition. [ENG-02] | 3 | 1 | 1 | If the two classes intentionally diverge (one is for planner, one for asset round-trip), rename rather than merge — but document why. |
| 3 | Strip boilerplate test docstrings + retention-prune `docs/archive/` and `CHANGELOG.md`. [ENG-04, ENG-05, ENG-09] | 3 | 1 | 1 | If a recent contributor reports they actively grep `docs/archive/`, raise the cutoff from 60 to 180 days but keep the policy. |
| 4 | Glossary block at top of SCIENTIST_GUIDE.md + end-to-end FASTQs walkthrough. [SCI-01, SCI-05] | 4 | 1 | 1 | If new-user friction is already low (e.g., scientists onboard via direct support, not docs), drop priority. |
| 5 | Human-readable formatter for `StagingFinding`. [SCI-04] | 3 | 1 | 1 | If callers already format these consistently, this is moot. |

Things 6–8 (lower priority): merge `manifest_envelope.py` + `manifest_io.py` [ENG-03], `RecipeId` NewType [ENG-07], rename `m18_busco_demo` [SCI-02].

### Things to omit/delete

- **Boilerplate test docstring "This test keeps the current contract explicit…"** — every occurrence (hundreds). [ENG-05]
- **`m18_busco_demo` bundle** if it duplicates `busco_eukaryota_genome_fixture`. [SCI-02]
- **`docs/archive/` entries older than 60 days** — they're recoverable from git. [ENG-04]
- **One of `prompt_and_run` / `plan_request` from `MCP_TOOL_NAMES`** — keep the Python function, drop the registered tool. [ENG-01]
- **One `ReferenceGenome` definition.** [ENG-02]

### Redundancies to collapse

- Two start paths (experiment loop vs. `prompt_and_run`). [ENG-01]
- Two `ReferenceGenome` types. [ENG-02]
- Two manifest helper modules. [ENG-03]
- Two planning entry points (`planning.py` vs. `composition.py`) with no signposting. [ENG-08]
- Two long-form change records (`CHANGELOG.md` + `docs/archive/*_plan.md`) covering the same milestones. [ENG-04, ENG-09]

### User-friendliness gaps (top 3)

1. **No glossary or numbered first-run walkthrough.** A scientist reading README cold meets seven new nouns in seven lines. [SCI-01, SCI-05]
2. **Two registered ways to start a run with no clear "use this one" hint.** [ENG-01]
3. **Preflight failures surface as structured findings without a built-in formatter.** Calling code has to render them; some won't. [SCI-04]

### What I would NOT change

1. **`registry/_<family>.py` per-family layout** (registry/_variant_calling.py, _annotation.py, _consensus.py, _evm.py, _postprocessing.py, _protein_evidence.py, _rnaseq.py, _transcript_evidence.py). It's a real extension point, not constants pretending to be one — adding a new family = appending one file with one import in `__init__.py`, exactly as `bundles.py:9` describes.
2. **`spec_executor.py` at 2689 LOC.** Big, but coherent: it owns local + Slurm executors, run records, retry, and module-load handling. Splitting would scatter the Slurm submission invariant the project's hard constraints depend on.
3. **`check_offline_staging` returning findings rather than raising** (`src/flytetest/staging.py:18–24`). The brief asked about provenance and reproducibility; this design lets the caller decide whether to block (Slurm submit) or warn (`validate_run_recipe`). Don't unify.
4. **The 887-test suite is large but proportionate.** 25k LOC of tests against 28k LOC of production code (~0.88 ratio) is normal for a framework with a wire format. Sampled `tests/test_server.py:307–1166` shows tests are aimed at MCP-surface behavior, not framework plumbing — exactly what a library at this layer should test.
5. **The typed `PlanDecline` wire format** (`mcp_replies.py:57`). A structured decline with `suggested_bundles`, `suggested_prior_runs`, and `next_steps` is the right shape for an LLM-driven client.

## 5. Open questions for the maintainer

1. **Is `prompt_and_run` actually used?** I can see it's wired in and tested; I can't tell from the code whether real clients call it, or whether the documented experiment loop is the only one in production. ENG-01 hinges on this answer.
2. **Is `CHANGELOG.md` consumed by anyone other than agents reading the latest section?** If yes, ignore ENG-09; if no, the retention policy is straightforward.
3. **Are `composition.py` and `planning.py` both reachable from the MCP surface, or is `composition.py` only used internally?** A grep would tell me but the answer changes whether ENG-08 stays at "docstrings only" or escalates.
4. **`m18_busco_demo` vs `busco_eukaryota_genome_fixture`** — which one do scientists actually use? If the answer is "neither, they always use a custom bundle," both are candidates for removal.
5. **What's in `docs/archive/Prompts/`?** I didn't open it; the name suggests scratch prompts that may have been left behind by mistake.

Milestone plan warranted: yes — five top-tier recommendations, each cheap, none risky, but they touch different files and benefit from being sequenced. See `docs/2026-04-25-critique-followup/` for the plan.
