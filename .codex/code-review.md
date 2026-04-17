# Code Review Guide

This file is a repo-specific guide for reviewing FLyteTest changes.

## Purpose

Use this guide when performing a review pass on tasks, workflows, typed assets, registry entries, manifests, docs, or helper scripts.

The review goal is to catch bugs, regressions, misleading assumptions, and validation gaps.

## Review Mindset

Focus on:

- correctness
- pipeline faithfulness
- deterministic behavior
- interface consistency
- validation adequacy

Keep summaries short.
Findings come first.

## Read First

Before reviewing, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. the touched modules
4. `README.md` if user-facing behavior changed
5. `src/flytetest/registry/` if public interfaces changed
6. `CHANGELOG.md` and the milestone archive when the change touches planned scope or completed milestones

## What To Look For

Prioritize findings in this order:

1. broken imports or module wiring
2. task/workflow signature mismatch with registry or docs
3. biologically incorrect stage boundaries
4. hidden assumptions presented as fact
5. non-deterministic file ordering or manifest content
6. collector bugs and output discovery fragility
7. compatibility regressions in existing entrypoints
8. missing feasible validation

## Repo-Specific Risk Areas

Common FLyteTest review targets:

- `flyte_rnaseq_workflow.py` compatibility exports
- `src/flytetest/registry/` accuracy
- `AGENTS.md` and `DESIGN.md` agreement on working rules versus architecture
- `src/flytetest/types/assets.py` provenance clarity
- result bundle structure under `results/`
- helper scripts for local installs and container checks
- current-scope statements in `README.md`

## Findings Format

A good review finding should include:

- severity or priority
- file reference
- what is wrong
- why it matters
- what behavior could break

Good example topics:

- registry entry says `chunk_size` but code uses `proteins_per_chunk`
- README says a task returns a file, code returns a directory
- a new module is hidden by `.gitignore`
- docs still call a milestone “future” after it was implemented

## Assumption Review

Check especially for claims around:

- BRAKER3 commands
- EVM preparation details
- protein database preprocessing
- tool output formats being treated as stable without documentation

If the implementation infers a step, the docs or manifest should say so.

## Validation Review

Ask:

- what was actually executed
- what was only compiled
- what was tested synthetically
- what was left unverified due to environment limits

Missing feasible validation is itself a review finding.

## Don’t

- don’t spend the review mostly praising structure while missing breakages
- don’t rewrite the feature during review unless explicitly asked
- don’t report style nits before correctness issues
- don’t assume docs are right if code disagrees

## Handoff

When finishing a review, communicate:

- findings first, ordered by severity
- open questions or assumptions second
- brief overall summary last
