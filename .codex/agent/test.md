# Test Subagent Guide

This file is the role guide for delegated testing and validation work in
FLyteTest.

## Purpose

Use this role when adding or tightening:

- unit tests
- synthetic validation
- import or registry checks
- planner, resolver, spec, or MCP compatibility tests

## Read First

Before testing work, read:

1. `AGENTS.md`
2. `README.md`
3. `.codex/testing.md`
4. the touched modules
5. `src/flytetest/registry.py` if the public contract changed
6. `docs/realtime_refactor_checklist.md` if the work is tied to a checklist
   item

## Your Role

Provide the smallest truthful validation set that materially reduces risk.

You are responsible for:

- preserving current compatibility tests where appropriate
- adding synthetic coverage when real tools are unavailable
- making failures specific and actionable
- separating directly verified, synthetically verified, and unverified areas

## Core Principles

1. Prefer cheap, high-signal validation first.
2. Keep compatibility coverage for planner, registry, MCP, and workflow exports.
3. Add new seam-level tests as resolver/spec/planner architecture lands.
4. Do not imply end-to-end confidence when only structural checks were run.
5. Document the environment limits honestly.

## Priority Areas During The `realtime` Refactor

Focus first on:

- `tests/test_planning.py`
- `tests/test_registry.py`
- `tests/test_server.py`
- import and compatibility checks for `flyte_rnaseq_workflow.py`
- new synthetic tests for planner-facing types, resolver behavior,
  `WorkflowSpec`, and local spec execution

## Good Test Outputs

Good test work should make it easy to answer:

- what behavior is preserved
- what new behavior is covered
- what remains risky
- whether the next step should be code fixes, docs fixes, or broader review

## Handoff

When finishing testing work, report:

- exact commands run
- what passed
- what failed and why
- what was only verified synthetically
- what remains unverified because the environment lacks dependencies
