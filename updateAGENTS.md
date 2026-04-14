Here’s the plan I’d use to update [AGENTS.md](/home/rmeht/Projects/flyteTest/AGENTS.md) for lower context cost while preserving the important guardrails.

**Plan**

1. Read the current repo doc rules before editing:
   - Review [`.codex/documentation.md`](/home/rmeht/Projects/flyteTest/.codex/documentation.md), since this is a documentation-only change.
   - Use the current [AGENTS.md](/home/rmeht/Projects/flyteTest/AGENTS.md) as the source text.

2. Measure the baseline:
   - Run `wc -l AGENTS.md` and optionally `wc -w AGENTS.md`.
   - Keep this as a before/after sanity check so the edit actually reduces context.

3. Preserve the important non-negotiables:
   - `DESIGN.md` is the architectural source of truth.
   - Current RNA-seq / annotation baseline must not be casually rewritten.
   - Registered tasks/workflows/planners/manifests should be preferred.
   - Slurm must go through frozen run records, not ad hoc shell behavior.
   - Biological steps must stay notes-faithful.
   - Docs/tests/manifests/changelog must stay aligned with behavior changes.

4. Trim duplicated rules:
   - Collapse the four `CHANGELOG.md` bullets into one concise bullet.
   - Remove the early detailed Slurm bullets from “Working Rules” and keep the full Slurm policy in the Prompt / MCP / Slurm section.
   - Remove repeated “update docs/tests/manifests when behavior changes” lines and keep section 4 as the canonical version.
   - Merge the repeated documentation/docstring guidance into a shorter rule that points to `.codex/documentation.md` and `.codex/testing.md`.
   - Compress biological guardrails into fewer, stronger bullets without weakening them.

5. Restructure lightly, not dramatically:
   - Keep the existing section order:
     - Purpose
     - Current State
     - Working Rules
     - What To Update When Behavior Changes
     - Validation Expectations
     - Biological Guardrails
     - Prompt / MCP / Slurm Rules
   - Avoid turning it into a new document; this should feel like a cleanup, not a rewrite.

6. Apply a focused patch:
   - Edit only [AGENTS.md](/home/rmeht/Projects/flyteTest/AGENTS.md).
   - Do not touch unrelated files.
   - Keep language direct and agent-friendly.

7. Validate the cleanup:
   - Run `git diff -- AGENTS.md`.
   - Run `wc -l AGENTS.md` and `wc -w AGENTS.md` again.
   - Skim the final file to confirm no Slurm, biology, changelog, or validation requirement was accidentally removed.

8. Final response:
   - Summarize what was trimmed.
   - Mention the before/after size reduction.
   - Note that no tests were needed because this is documentation-only.

The main goal: make `AGENTS.md` shorter by consolidating repeated rules, while leaving the biology and Slurm constraints sharp enough that future agents still behave carefully.