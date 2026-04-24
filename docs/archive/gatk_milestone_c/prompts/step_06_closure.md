# Step 06 — Closure: Agent-Context Sweep, CHANGELOG, Submission Prompt, Verification

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Closure steps synthesise across
the whole milestone: write a ≤100-line submission prompt that accurately
summarises what landed, update `AGENTS.md` + `DESIGN.md` without
breaking existing sections, and run the full verification gate.
Milestone A and B closure prompts both used Sonnet for this reason.

## Goal

Finish Milestone C:

1. Sweep agent-context docs (`AGENTS.md`, `DESIGN.md`) to point at the
   new cluster prompt file.
2. Write the milestone-level CHANGELOG entry.
3. Author `docs/gatk_milestone_c_submission_prompt.md` (≤100 lines).
4. Run every verification gate from the plan §6.
5. Mark Step 06 and the milestone Complete in
   `docs/gatk_milestone_c/checklist.md`.
6. Merge `gatkport-c` into `main` once gates pass.

## Context

- Milestone A submission prompt for format reference:
  `docs/gatk_milestone_a_submission_prompt.md`.
- Milestone A closure prompt for format reference:
  `docs/gatk_milestone_a/prompts/step_10_closure.md`.
- Milestone B closure prompt for recent precedent:
  `docs/gatk_milestone_b/prompts/step_09_closure.md`.
- Milestone C is documentation-only — no Python changes should appear
  in `git diff --stat`. If any Python change is present, stop and
  investigate before proceeding.

## Inputs to read first

- `docs/gatk_milestone_a_submission_prompt.md` — copy structure, length,
  and voice.
- `AGENTS.md` — current Project Structure section (you will append to
  it, not rewrite).
- `DESIGN.md` — §5.6 Germline Variant Calling (you will append a
  Milestone C note).
- `CHANGELOG.md` — read `## Unreleased` to confirm Steps 01–05 entries
  exist; the milestone-level entry goes above them.

## What to build

### 1. `AGENTS.md` agent-context sweep

Under the Project Structure → "Workflows" or documentation section,
add one line naming the new cluster prompt file:

```
- `docs/mcp_variant_calling_cluster_prompt_tests.md` — live-cluster
  prompt scenarios for the variant_calling family (sanity, happy path,
  workflow, cancel, retry, escalation).
```

Do not move any existing line; append only.

### 2. `DESIGN.md` §5.6 update

Under §5.6 Germline Variant Calling, append:

> Milestone C adds the live-cluster validation prompt set at
> `docs/mcp_variant_calling_cluster_prompt_tests.md` and a Variant
> Calling Pipeline section in
> `docs/mcp_full_pipeline_prompt_tests.md`. These are
> documentation-only artifacts that exercise the Milestone A + B
> surface through the MCP server on RCC.

Do not change any prior §5.6 paragraphs.

### 3. Milestone-level CHANGELOG entry

Add under `## Unreleased`, **above** the existing Step 01–05 entries
for this milestone:

```markdown
### GATK Milestone C — Complete (YYYY-MM-DD)

Closes Milestone C of the Phase 3 GATK port (tracker:
`docs/gatk_milestone_c/checklist.md`). Delivers the live-cluster
validation prompt set for the variant_calling family and refreshes
`docs/mcp_full_pipeline_prompt_tests.md` with a Variant Calling
Pipeline section. Documentation-only — no new Python, tasks,
workflows, registry entries, or planner types.

- [x] YYYY-MM-DD docs/mcp_variant_calling_cluster_prompt_tests.md: Scenarios 1–8.
- [x] YYYY-MM-DD docs/mcp_full_pipeline_prompt_tests.md: Variant Calling Pipeline section (Stages 0–3).
- [x] YYYY-MM-DD AGENTS.md and DESIGN.md §5.6 updated.
- [x] YYYY-MM-DD docs/gatk_milestone_c_submission_prompt.md authored.
- [x] YYYY-MM-DD full pytest green; python -m compileall clean.
- Deferred to future milestones: merge_bam_alignment (uBAM path), VQSR, interval-scoped HaplotypeCaller.
```

Replace `YYYY-MM-DD` with today's UTC date (`date -u +%Y-%m-%d`).

### 4. Submission prompt — `docs/gatk_milestone_c_submission_prompt.md`

≤100 lines. Structure:

- `# GATK Milestone C Submission` title.
- One-paragraph summary naming the milestone scope (cluster prompt
  set + full-pipeline doc refresh) and the deferred items.
- "## What landed" — bullet list referencing
  `docs/mcp_variant_calling_cluster_prompt_tests.md` and the updated
  `docs/mcp_full_pipeline_prompt_tests.md`.
- "## What did not land" — explicit list: merge_bam_alignment, VQSR,
  interval-scoped HaplotypeCaller, any actual fixture data in the
  repo, any new `scripts/rcc/` helper.
- "## Exit criteria" — bullet list quoting the plan §6 verification
  gates.
- "## Pointer docs" — links to:
  - `docs/gatk_milestone_c/milestone_c_plan.md`
  - `docs/gatk_milestone_c/checklist.md`
  - `docs/mcp_variant_calling_cluster_prompt_tests.md`
  - `docs/mcp_full_pipeline_prompt_tests.md`
  - `docs/gatk_milestone_a_submission_prompt.md` (for context)
- "## Next scoping targets" — one paragraph naming Milestone D
  candidates (VQSR, merge_bam_alignment, interval-scoped
  HaplotypeCaller).

Mirror the voice of `docs/gatk_milestone_a_submission_prompt.md` —
factual, no marketing adjectives.

### 5. Checklist update

In `docs/gatk_milestone_c/checklist.md`:

- Mark Step 06 `Complete`.
- At the top of the file, change the milestone status line to
  `Milestone status: Complete`.

## Verification — all must pass

```bash
# No Python diffs in this milestone
git diff --stat main... | grep -E '\.py$' && { echo "ERROR: Python changed in a doc-only milestone"; exit 1; } || echo "OK: no Python diffs"

# Plan §6 gates
python -m compileall src/flytetest/
pytest
rg -n "variant_calling" docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "germline_short_variant_discovery" docs/mcp_full_pipeline_prompt_tests.md
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" docs/mcp_variant_calling_cluster_prompt_tests.md docs/mcp_full_pipeline_prompt_tests.md
rg -n "mcp_variant_calling_cluster_prompt_tests" AGENTS.md DESIGN.md

# Submission prompt bounds
test -f docs/gatk_milestone_c_submission_prompt.md
wc -l docs/gatk_milestone_c_submission_prompt.md   # expect <= 100

# Import smoke on a fresh shell
python -c "import flytetest.server"
```

`grep -E '\.py$'` must NOT match (empty output). Stargazer grep gate
must return zero hits. `wc -l` must report ≤ 100.

## Commit message

```
variant_calling: close Milestone C — cluster prompt set, full-pipeline refresh, submission prompt
```

## Merge

After all gates pass:

```bash
git checkout main
git merge --no-ff gatkport-c
git branch -d gatkport-c
```

Do not force-push. Do not skip hooks.

## Checklist

- [ ] `AGENTS.md` appended with cluster prompt file reference.
- [ ] `DESIGN.md` §5.6 appended with Milestone C note.
- [ ] Milestone-level CHANGELOG entry added.
- [ ] `docs/gatk_milestone_c_submission_prompt.md` ≤ 100 lines.
- [ ] `git diff --stat main...` shows no `.py` changes.
- [ ] Full `pytest` green.
- [ ] All plan §6 verification gates green.
- [ ] Step 06 marked Complete in checklist.
- [ ] Milestone C marked Complete at top of checklist.
- [ ] `gatkport-c` merged into `main`.
