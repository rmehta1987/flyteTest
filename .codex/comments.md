# Code Readability Guide

This file is a repo-specific guide for docstrings, module headers, and inline comments in FLyteTest.
It is not a generic Python style guide and it does not override `AGENTS.md` or `DESIGN.md`.

## Purpose

Use this guide when:

- creating a new Python module
- adding or updating task, workflow, helper, or collector functions
- doing readability passes on existing code
- reviewing whether comments and docstrings are sufficient for future contributors and delegated agents

In FLyteTest, readable code is part of reproducibility.
The repo models a biologically ordered pipeline with real tool assumptions, so code should explain the stage boundary and any non-obvious behavior at the point where it is implemented.

## Read First

Before making readability edits, read:

1. `AGENTS.md`
2. `DESIGN.md`
3. the touched module
4. the relevant `.codex` guide for the area being edited, such as `.codex/tasks.md` or `.codex/workflows.md`
5. the relevant `docs/tool_refs/...` file when the code wraps a biological tool

## Repo Standard

In this repo:

- every Python file should start with a short module docstring that explains the file's purpose and pipeline position
- every top-level function and class should have a concise docstring
- every task and workflow function should document its biological or architectural boundary
- private helpers should still have short docstrings when they resolve paths, normalize outputs, discover files, or encode assumptions
- inline comments should be used sparingly and only when the logic is not obvious from the code itself
- if a function uses a shortcut, condensed path, or repo-specific workaround, add a brief inline comment that explains why it is safe

This applies to both current and future code.
When touching an existing file, bring the touched functions and the module header up to this standard.

## Module Docstrings

Each module should open with a short docstring that tells a future reader:

- what the file is for
- where it sits in the pipeline or package
- what kind of code it contains

Good module docstrings are usually 2-5 lines.

Example:

```python
"""BRAKER3 task implementations for FLyteTest.

This module stages local ab initio annotation inputs, runs the documented
BRAKER3 boundary, normalizes `braker.gff3` for later EVM use, and collects
stable result bundles.
"""
```

## Function Docstrings

Every top-level function should answer the most useful short questions:

- what does this function do
- what boundary does it represent
- what important assumption or output contract should a maintainer know

Prefer short docstrings over long ones.
Most helper functions only need a single sentence.

Examples:

```python
def _braker_gff3(run_dir: Path) -> Path:
    """Resolve the single `braker.gff3` file produced under a BRAKER3 run tree."""
```

```python
@annotation_env.task
def normalize_braker3_for_evm(braker_run: Dir) -> Dir:
    """Normalize resolved `braker.gff3` into a stable later-EVM-ready GFF3 directory."""
```

## Inline Comments

Use inline comments only where they save real reader effort.

Good uses:

- explaining why a path-discovery heuristic is safe
- clarifying a repo-specific Flyte workaround
- marking where an assumption from the notes is being implemented conservatively
- explaining a normalization rule that is not obvious from the code
- explaining a shortcut or abbreviated code path that would otherwise surprise a future reader

Avoid:

- repeating the code literally
- narrating simple assignments
- leaving comments that will go stale faster than the code

## Comments Do Not Replace Manifests Or Docs

Comments and docstrings should help someone read the code.
They do not replace:

- result manifests
- `README.md`
- tool reference docs
- explicit assumption lists in user-facing outputs

Important biological or runtime assumptions should still be visible in manifests and docs, not only in code comments.

## Recommended Pattern

For most new modules:

1. add a module docstring first
2. add concise docstrings to all top-level functions
3. add inline comments only around non-obvious logic
4. check that comments match the actual code after finishing the implementation

## Review Questions

Before finishing readability work, ask:

- can a new contributor tell what this file is for from the first few lines
- can a delegated worker tell what each function boundary is without reverse-engineering all callers
- are assumptions described where they matter
- are any comments redundant, stale, or too vague to be useful

## Don't

- don't add long tutorial-style docstrings to every helper
- don't state unsupported biology as fact in comments
- don't duplicate the same explanation in a module docstring, function docstring, inline comment, manifest, and README unless each copy serves a different audience
- don't skip docstrings for helpers just because they are private if they encode meaningful behavior
- don't use shortcuts without enough comment context for a future reader to understand why the shortcut is acceptable

## Handoff

When finishing readability work, communicate:

- which files gained module docstrings
- whether all touched functions now have docstrings
- any places where comments still need domain confirmation
