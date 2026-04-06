# Testing Guide

This file is a repo-specific guide for validation and testing work in FLyteTest.

## Purpose

Use this guide when validating new tasks, workflows, manifests, helper scripts, or registry wiring.

This repo often depends on external bioinformatics tools that may not be available in the current environment, so good testing work includes both executable checks and honest limits.

## Read First

Before testing, read:

1. `AGENTS.md`
2. `README.md` for the documented contract
3. the touched task/workflow modules
4. `src/flytetest/registry.py` if the public interface changed
5. any helper scripts that were modified

## Testing Priorities

Prioritize tests and checks in this order:

1. imports and Python compilation
2. signature and registry consistency
3. deterministic path/result handling
4. manifest correctness
5. shell helper syntax
6. synthetic local execution when external tools are unavailable
7. real tool execution when the environment supports it

## Feasible Validation In This Repo

Often useful checks include:

- `python3 -m py_compile` on touched Python files
- small `python3` import checks against `src/`
- registry lookup checks
- package export checks
- `bash -n` for changed shell scripts
- synthetic fixture tests that stub or bypass unavailable external tools

When real binaries are present, add:

- direct tool version checks
- local workflow smoke runs
- container-image command checks through `scripts/test_singularity_images.sh`

## Real-Data Fixtures

This repo now includes a lightweight real-data fixture set derived from the Galaxy Training Network Braker3 tutorial:

- `data/genome.fa`
- `data/RNAseq.bam`
- `data/proteins.fa`

Before defaulting to synthetic-only validation for a new pipeline milestone,
check whether that stage already has a documented tutorial-backed dataset or
local mirrored fixture directory in `README.md`, `docs/tutorial_context.md`, or
under `data/`.

Use these files for milestone-scoped smoke tests when the relevant binaries are available locally.

Guidelines:

- prefer copying or subsetting fixture inputs into a temp directory instead of editing them in place
- keep fixture-backed tests short and stage-focused
- use the fixture set to validate path discovery, command wiring, and output collection on realistic file shapes
- keep synthetic tests as the primary safety net for deterministic logic and no-binary environments
- if a stage needs larger or tool-specific fixtures later, document that gap explicitly instead of silently expanding scope

## Synthetic Testing Pattern

When a real tool like Exonerate, PASA, or STAR is unavailable:

- create minimal fake inputs
- exercise deterministic staging and collector logic
- simulate the expected raw output shape closely enough to test converters and manifests
- verify that stable result bundles and manifest keys are produced

When the real tool is available and the Galaxy-derived fixture files are sufficient:

- add one smoke test that uses the local fixture paths under `data/`
- keep runtime and fixture size bounded so the suite stays practical for milestone work

Synthetic validation is especially valuable for:

- chunking logic
- output discovery helpers
- concatenation logic
- manifest shaping
- registry/export integration

## What To Report

Every testing handoff should separate:

- verified directly
- verified synthetically
- not verified because the environment lacks dependencies

Be explicit. “Untested” is better than implied confidence.

## Common Risks To Check

- task/workflow signature drift from registry entries
- README examples using old parameter names
- manifest keys not matching collected outputs
- ignored files preventing new modules from showing up in git
- import failures caused by missing config constants or export wiring
- stale compatibility exports in `flyte_rnaseq_workflow.py`

## Don’t

- don’t claim end-to-end validation if only compilation was checked
- don’t skip cheap synthetic validation when real execution is unavailable
- don’t ignore helper scripts if the feature depends on them
- don’t focus only on happy-path biology and miss path/manifest bugs

## Handoff

When finishing testing work, communicate:

- exact commands run
- what passed
- what failed and why
- what remains unverified
- whether the next step should be code fixes, docs fixes, or broader review
