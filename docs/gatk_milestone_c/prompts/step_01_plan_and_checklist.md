# Step 01 — Plan + Checklist Skeleton

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Structural doc work that must mirror
the voice and layout of `docs/gatk_milestone_a/milestone_a_plan.md` and
`docs/gatk_milestone_b/milestone_b_plan.md` verbatim. Haiku risks drift
from the established plan conventions.

## Goal

Stand up the tracker docs for Milestone C so later step prompts can
reference stable anchors (`§1 Context`, `§5 Steps`, `§6 Verification
Gates`, etc.) without ambiguity.

## Context

- Milestone B plan §7 named Milestone C as "cluster validation prompt set
  and refresh of `docs/mcp_full_pipeline_prompt_tests.md`".
- The plan + checklist at `docs/gatk_milestone_c/milestone_c_plan.md` and
  `docs/gatk_milestone_c/checklist.md` may already exist from the
  prompt-authoring session that created this step file. If they do,
  **verify they match the Milestone A/B structure and update in place
  rather than overwriting**.
- Branch: `gatkport-c`. Create it with `git checkout -b gatkport-c`
  before editing if not already on it.

## Inputs to read first

- `docs/gatk_milestone_a/milestone_a_plan.md` — copy the §-numbering and
  voice.
- `docs/gatk_milestone_b/milestone_b_plan.md` — copy the backward-
  compatibility framing.
- `docs/gatk_milestone_b/checklist.md` — the status-table shape.
- `AGENTS.md` — hard constraints and efficiency notes.

## What to build

### `docs/gatk_milestone_c/milestone_c_plan.md`

Ensure it contains, in order:

1. `§1 Context` — names Milestone C as documentation-only; no Python,
   no new registry entries, no new planner types.
2. `§2 Pillars / Invariants (carried from Milestones A and B)` — four
   pillars (freeze-before-execute, typed surfaces, manifest envelope,
   no Stargazer bleed-in).
3. `§3 Deliverables` — lists:
   - **New files**: `docs/mcp_variant_calling_cluster_prompt_tests.md`,
     `docs/gatk_milestone_c_submission_prompt.md`.
   - **Refreshed files**: `docs/mcp_full_pipeline_prompt_tests.md`,
     `AGENTS.md`, `DESIGN.md` §5.6, `CHANGELOG.md`.
4. `§4 Out of Scope` — no Python changes; `merge_bam_alignment` and VQSR
   still deferred; no new smoke scripts.
5. `§5 Steps` — six-row table pointing at the six step prompts in
   `prompts/`.
6. `§6 Verification Gates` — the exact bullet list under "## Verification
   Gates" in the checklist must match.
7. `§7 Hard Constraints` — documentation-only scope; stop and escalate
   if a step appears to require code; every task/workflow name must
   resolve to `VARIANT_CALLING_ENTRIES`.

### `docs/gatk_milestone_c/checklist.md`

Mirror the Milestone B checklist exactly:

- "Branch" header naming `gatkport-c`.
- "Status Labels" list: `Not started`, `In progress`, `Blocked`,
  `Complete`.
- Six-row status table (one row per step prompt) under the same
  section headings as §5 of the plan.
- "Verification Gates" section copied from plan §6.
- "Hard Constraints" section reiterating the documentation-only scope.
- "Out of Scope" section listing deferred items.

## Files to create or update

- `docs/gatk_milestone_c/milestone_c_plan.md` (create if missing; verify
  if present).
- `docs/gatk_milestone_c/checklist.md` (create if missing; verify if
  present).

## CHANGELOG

Add under `## Unreleased`:

```
### GATK Milestone C Step 01 — Plan + checklist skeleton (YYYY-MM-DD)

- [x] YYYY-MM-DD created/verified docs/gatk_milestone_c/milestone_c_plan.md.
- [x] YYYY-MM-DD created/verified docs/gatk_milestone_c/checklist.md.
```

Replace `YYYY-MM-DD` with today's date (UTC, `date -u +%Y-%m-%d`).

## Verification

```bash
test -f docs/gatk_milestone_c/milestone_c_plan.md
test -f docs/gatk_milestone_c/checklist.md
rg -n "§5 Steps" docs/gatk_milestone_c/milestone_c_plan.md
rg -n "## Steps" docs/gatk_milestone_c/checklist.md
rg -n "gatkport-c" docs/gatk_milestone_c/checklist.md
python -m compileall src/flytetest/
```

All five `rg`/`test` commands must exit non-zero-free; `compileall` must
be clean.

## Commit message

```
variant_calling: open Milestone C — plan + checklist skeleton
```

## Checklist

- [ ] Plan doc present with §1–§7 in the order given above.
- [ ] Checklist doc present with the six-row status table.
- [ ] Branch `gatkport-c` checked out.
- [ ] CHANGELOG updated with today's date.
- [ ] Step 01 marked `Complete` in `docs/gatk_milestone_c/checklist.md`.
- [ ] Verification commands green.
