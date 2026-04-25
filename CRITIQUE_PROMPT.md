# Project Critique Prompt — Engineer + Research Scientist Dual Lens

You are reviewing the **flyteTest** project (a Flyte-based bioinformatics pipeline framework with an MCP surface for GATK4 germline variant calling and other genomics workflows). Produce a conservative, critical assessment from **two distinct perspectives**, then synthesize.

Be skeptical. Assume the project is over-engineered until proven otherwise. Push back on cleverness. Reward boring, simple, legible code.

## Ground rules

- **Read before judging.** Before any criticism of a specific module, read the actual code (`src/flytetest/`), the design doc (`DESIGN.md`), the changelog (`CHANGELOG.md`), the agent guides (`AGENTS.md`, `CLAUDE.md`, `.codex/*.md`), and a representative sample of tests (`tests/`). Cite `path:line` for every claim.
- **No speculation.** If you cannot point to a specific file, function, or test, do not make the claim. "This feels heavy" is not a finding; "`server.py` defines 14 MCP tools where 6 would cover the documented scientist loop (cite the loop in AGENTS.md)" is.
- **Conservative bias.** Default to "leave it alone" unless the cost of the current shape is concretely demonstrable (extra surface area to maintain, confusing to a new user, redundant with another module, untested branch, etc.).
- **No rewrites in the review.** Identify problems and propose the smallest possible change. Do not draft replacement code unless a one-or-two-line example clarifies a recommendation.
- **Respect hard constraints** in `AGENTS.md` (frozen artifacts, Slurm submission rules, `classify_slurm_failure` semantics, baseline preservation). A finding that violates these is invalid.

## Lens 1 — Staff Software Engineer

Audit the codebase as if you were the next maintainer who has to own it for two years. Evaluate:

1. **Surface area vs. value.** For each top-level module under `src/flytetest/` — does it earn its existence? Which modules duplicate concerns (e.g., do `planning.py`, `mcp_contract.py`, and `server.py` overlap on intent classification or tool registration)? Which abstractions exist for hypothetical needs rather than current ones?
2. **MCP tool inventory.** List every MCP tool exposed by `server.py`. For each, mark: (a) used in the documented scientist loop, (b) power-user-only, (c) candidate for removal or merge. Is there a simpler surface that covers ≥90% of real usage?
3. **Type system & dataclasses.** Are `planner_types.py`, `types/`, `mcp_replies.py`, and `errors.py` proportionate to the problem, or are they ceremony? Specifically: how many of these types have exactly one producer and one consumer? Those are candidates for inlining.
4. **Registry pattern.** Is `registry/` a real extension point, or a folder of constants pretending to be one? Count the number of external entry points vs. internal-only ones.
5. **Tests.** 858 tests is a lot. Sample 20 random tests — what fraction test framework plumbing vs. biological correctness vs. MCP wire format? Are there parameterized tests that could replace dozens of near-duplicate tests? Any tests that exist only to pin internal implementation details?
6. **Docs/agent guides.** `.codex/` has 10+ specialist guides plus `AGENTS.md` plus `CLAUDE.md` plus `DESIGN.md`. Identify overlap, contradictions, and stale sections. Which guides could be deleted or merged without information loss?
7. **Changelog & milestone docs.** Is `docs/archive/` accumulating dead context that no one will ever read? Recommend retention policy.
8. **Dependencies & build.** Look at `pyproject.toml` / lockfile. Any dependencies pulled in for a single helper? Anything pinned for reasons no longer true?
9. **Error paths.** Is the typed `PlannerResolutionError` hierarchy actually distinguishing cases callers handle differently, or is it five exception classes that all become the same decline?
10. **Naming & legibility.** Flag identifiers that require reading three files to understand. Flag "magic" string formats (e.g., `recipe_id` `<YYYYMMDDThhmmss.mmm>Z-<target_name>`) that should be a real type.

For each finding, output:
```
[ENG-NN] <one-line summary>
  evidence: <path:line> [+ additional citations]
  cost today: <what the current shape costs in maintenance/cognition/onboarding>
  smallest fix: <minimal concrete change>
  risk of change: <what could break>
  confidence: low | medium | high
```

## Lens 2 — Research Scientist (bioinformatician, GATK user)

Audit as a wet-lab-adjacent computational biologist who wants to call variants on real data this week. Evaluate:

1. **First-run experience.** Walk through the documented scientist loop: `list_entries → list_bundles → load_bundle → run_task / run_workflow`. From a clean checkout, how long until I have a frozen recipe ready to submit? What blocks me? What jargon ("recipe", "bundle", "manifest", "run record", "execution profile", "runtime images") is over-loaded or undefined for a biologist?
2. **Bundle catalog.** Read `bundles.py`. Are the curated bundles biologically meaningful (real reference + interval set + known-sites combo I'd actually use), or are they engineering test fixtures dressed up as bundles? Is the catalog sized for the problem (too few = I write my own; too many = I can't choose)?
3. **Workflow coverage.** Compare the 11 workflows in `workflows/variant_calling.py` against a real GATK4 germline best-practices flow. What's missing? What's split into too many pieces? What's biologically redundant (e.g., do `genotype_refinement` and `post_genotyping_refinement` belong as one workflow)?
4. **Default resources & realism.** Inspect default `resource_request` values and module loads. Would these actually run a 30x WGS sample without OOM or timeout? Are interval scatter defaults realistic?
5. **Slurm story.** A scientist on a 2FA cluster: is the documented sbatch-from-session flow actually walked through end-to-end somewhere, or only described in fragments? What happens on the first `check_offline_staging` failure — is the error message actionable for a biologist, or does it require reading the Python?
6. **Provenance & reproducibility.** When the run finishes, what does the scientist get? Is there a single artifact they can hand to a collaborator that captures inputs, tool versions, container digests, and outputs? Or is provenance scattered across files?
7. **Error messages & failure modes.** Trigger (mentally, by reading code) the top-5 ways a real run fails: missing reference index, wrong interval list build, bad sample name, container pull failure, Slurm queue rejection. For each, is the resulting message intelligible to a biologist?
8. **Documentation that matters to a scientist.** Most `.codex/` guides are agent-facing. What user-facing biology documentation exists? Is `docs/braker3_evm_notes.md` and the `tutorial_context.md` enough for a scientist new to the project, or is there a missing "I have FASTQs, what do I do" guide?
9. **Cognitive overhead.** Count the concepts a scientist must learn before submitting their first job. Compare to the absolute minimum the problem requires. Anything in the gap is a tax.
10. **Lock-in.** If the scientist outgrows this tool, can they leave with their results, or are intermediate artifacts in a custom format only this codebase understands?

For each finding, output:
```
[SCI-NN] <one-line summary>
  evidence: <path:line or doc reference>
  who is hurt: <which user persona, doing what task>
  smallest fix: <minimal concrete change>
  risk of change: <biological correctness, reproducibility, existing users>
  confidence: low | medium | high
```

## Synthesis

After both lenses, produce a **single ranked list** of the top 5–8 changes that would most improve the project, scored on:

- **Impact** (1–5): how much pain it removes
- **Cost** (1–5): engineering effort
- **Risk** (1–5): chance of breaking something users depend on
- **Conservatism check**: state explicitly *what evidence would change your mind* on each recommendation

Then call out:
- **Things to omit/delete** — modules, tools, tests, docs that pull weight without earning it. Be specific. "Delete X" not "consider simplifying X."
- **Redundancies to collapse** — duplicate concepts, parallel hierarchies, two ways to do the same thing.
- **User-friendliness gaps** — the top 3 places a new scientist or new engineer hits a wall.
- **What you would NOT change** — at least 3 things that look suspicious but are actually correct as-is. (If you can't find any, your review is biased.)

## Output format

A single markdown document. Sections in this order:
1. Scope & method (what you read, how long you spent, what you skipped and why)
2. Engineer findings (`[ENG-*]`)
3. Scientist findings (`[SCI-*]`)
4. Synthesis (ranked list, omissions, redundancies, gaps, leave-alones)
5. Open questions for the maintainer (things you couldn't decide without more context)

Length target: 1500–3000 words. If you're writing more, you're padding. If less, you didn't read enough.

## What this review is NOT

- Not a rewrite proposal.
- Not a design doc for a v2.
- Not a feature wishlist (no "you should add X").
- Not a style guide audit (no nitpicks about formatting or naming unless they actively cause confusion).
- Not flattery. If the project is good, say so briefly and move on to the problems.
