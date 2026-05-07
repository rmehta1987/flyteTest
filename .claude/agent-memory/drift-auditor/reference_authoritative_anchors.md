---
name: authoritative_anchors
description: Canonical locations for high-risk declarations and rules in flyteTest. File:line refs may shift; verify before quoting.
type: reference
---

Verified during the first audit (PR #12, 2026-05-06). Line numbers shift as code grows — re-verify with `rg` before recommending.

**Compatibility-critical surfaces** (also enforced by `.claude/hooks/protect-files.sh`):
- `src/flytetest/server.py` — MCP handler logic
- `src/flytetest/mcp_contract.py` — SHOWCASE_TARGETS, FLAT_TOOLS, TOOL_DESCRIPTIONS
- `src/flytetest/planning.py` — planner output shape
- `src/flytetest/spec_executor.py` — frozen-recipe executors
- `src/flytetest/registry/__init__.py` — REGISTRY_ENTRIES tuple
- `flyte_rnaseq_workflow.py` — workflow compat exports

**Canonical declarations** (with file:line at audit time):
- `MANIFEST_OUTPUT_KEYS`: `src/flytetest/tasks/variant_calling.py:29` (registry-manifest contract; every output declared in a RegistryEntry must appear in this tuple)
- `SHOWCASE_TARGETS`: `src/flytetest/mcp_contract.py:493` (iterates REGISTRY_ENTRIES, yields one target per entry with non-empty showcase_module — the gate that controls MCP exposure)
- `FLAT_TOOLS`: `src/flytetest/mcp_contract.py:106` (tuple of flat-tool names; companion to TOOL_DESCRIPTIONS)
- Registry types: `src/flytetest/registry/_types.py:13` (InterfaceField), `:31` (RegistryCompatibilityMetadata), `:53` (RegistryEntry)

**CHANGELOG discipline** (lines 1-26 of `CHANGELOG.md`):
- "newest section always first; never append to the bottom" — entries go immediately under `## Unreleased`
- "treat this file as the shared working memory for meaningful units of work; update it after each completed slice"
- Polish/docs PRs are meaningful slices and warrant entries; missing CHANGELOG for a merged PR is MEDIUM drift.

**Authority hierarchy** (per drift-auditor role):
`AGENTS.md` > `DESIGN.md` > `.codex/` area guides > `.codex/agent/*.md` role guides > inline docstrings > comments. Code is ground truth for what runs.
