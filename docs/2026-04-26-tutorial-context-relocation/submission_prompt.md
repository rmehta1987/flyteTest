# Submission Prompt — `.codex/tutorial_context.md` relocation

## Source

`CRITIQUE_REPORT.md` finding **ENG-10** (secondary track of the
2026-04-25 critique follow-up; deferred from that milestone).

## Goal

The file `.codex/tutorial_context.md` currently mixes two audiences:
agent-facing meta-context (how Claude/Codex should behave when working
on tutorial tasks) with biology-facing tutorial content (how the
GATK / annotation pipelines actually work). Decide whether to move the
file under `.codex/agent/` or split it.

## Read first

1. `AGENTS.md`
2. `CLAUDE.md` (specialist guides table — `tutorial_context.md` is
   one of the listed guides)
3. `.codex/tutorial_context.md` (the file itself)
4. `.codex/agent/README.md` and the other `.codex/agent/*.md` files
   to see what already lives there
5. `rg -l 'tutorial_context' src tests docs` — every reference

## Decision

This is a decision-first milestone. Stage 1: pick one of two paths.

**Option A — Move only.** `git mv .codex/tutorial_context.md
.codex/agent/tutorial_context.md`. Use this if the file is mostly
agent-meta with biology content as supporting context.

**Option B — Split.** Create
`.codex/agent/tutorial_context.md` (agent-meta only) and
`.codex/tutorial_biology_context.md` (biology-only) or fold the
biology section into `docs/gatk_pipeline_overview.md`. Use this if
the agent-meta and biology content can stand alone without each
other.

## Decision evidence to gather before choosing

- Word-count split: agent-meta vs biology lines.
- Whether any callers (CLAUDE.md, AGENTS.md, scripts) reference the
  file by section heading (which would constrain a split).
- Whether the biology content duplicates `docs/gatk_pipeline_overview.md`
  (if yes, split is cleaner — no duplication, biology section gets
  folded into the existing pipeline doc).

## In scope

- Whatever you decide above.
- Update every reference: `CLAUDE.md`'s specialist guides table,
  any `AGENTS.md` or other `.codex/*.md` cross-link, any in-tree
  doc that points at `.codex/tutorial_context.md`.
- One dated `CHANGELOG.md` entry recording the decision and the
  reason.

## Out of scope

- Rewriting either content stream beyond what the move requires.
- Inventing new agent-meta guidance not already in the file.
- Deleting biology content that is currently load-bearing.

## Acceptance

- `rg -l 'tutorial_context' src tests docs CLAUDE.md AGENTS.md`
  returns only the new path(s) — no stale links.
- Full test suite passes (no test references should break, but
  validate).
- Decision and rationale recorded in CHANGELOG.

## Risk and stop conditions

- If the file is heavily section-cross-referenced from outside,
  splitting will break links you didn't see; stop and report
  rather than mass-rewriting them.

## Commit

`secondary-cleanup: relocate tutorial_context.md to .codex/agent/` (Option A)

or

`secondary-cleanup: split tutorial_context.md into agent and biology halves` (Option B)
