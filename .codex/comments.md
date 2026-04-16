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

1. the touched module
2. the relevant `.codex` guide for the area being edited, such as `.codex/tasks.md` or `.codex/workflows.md`
3. the relevant `docs/tool_refs/...` file when the code wraps a biological tool

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

The opening `"""` and all continuation lines should be flush with the left
margin (column 0) at the module level. Do not indent the body 4 spaces — that
pattern exists in some files in this repo and should not be continued.

Correct:

```python
"""BRAKER3 task implementations for FLyteTest.

This module stages local ab initio annotation inputs, runs the documented
BRAKER3 boundary, normalizes `braker.gff3` for later EVM use, and collects
stable result bundles.
"""
```

Incorrect (4-space indent on continuation lines — avoid this):

```python
"""BRAKER3 task implementations for FLyteTest.

    This module stages local ab initio annotation inputs, runs the documented
    BRAKER3 boundary, normalizes `braker.gff3` for later EVM use, and collects
    stable result bundles.
"""
```

## Function Docstrings

Every top-level function should give a maintainer everything they need to
understand the function's role without reading the body:

- what the function does and where it lives in the system
- what boundary or contract it represents
- any non-obvious lifecycle behavior, error handling, or output invariants

**The depth target is `slurm_poll_loop` in `slurm_monitor.py`.** That docstring
explains deployment context (started inside the MCP server event loop), lifecycle
("never returns normally; runs until cancelled"), error handling strategy
(exponential backoff on failure, cancellation re-raised immediately), and each
Args entry explains *why the parameter exists*, not just its type.  Use that
level of substance as the standard for any function with non-trivial behavior.

A one-liner is correct when it captures everything a maintainer needs to know.
Use sub-sections (`Error handling:`, `Output contract:`, `Retry logic:`) when
the behavior in those areas is complex enough that a reader would otherwise need
to read the full body.

Include Args and Returns sections only when they add content beyond the type
hints.  Each Args entry must answer why the stage or function needs that
input — its biological role, the constraint on its value, or the pipeline
contract it participates in.  Each Returns entry must say what invariant the
caller can rely on, not just name the returned type.

If the honest answer is "the name and type hint already say it all," omit
the section.  If you cannot write a description more informative than "A value
used by the helper," that is a signal to omit the section, not to keep the
boilerplate.

Good examples — one-liners that are complete on their own:

```python
def _braker_gff3(run_dir: Path) -> Path:
    """Resolve the single `braker.gff3` file produced under a BRAKER3 run tree."""
```

```python
@annotation_env.task
def normalize_braker3_for_evm(braker_run: Dir) -> Dir:
    """Normalize resolved `braker.gff3` into a stable later-EVM-ready GFF3 directory."""
```

Good example — each Args entry explains the engineering reason the parameter
exists, not just its type:

```python
def batch_query_slurm_job_states(
    job_ids: Sequence[str],
    *,
    command_timeout: float = _DEFAULT_COMMAND_TIMEOUT,
) -> dict[str, SlurmSchedulerSnapshot]:
    """Fetch Slurm states for multiple jobs in a single scheduler call.

    Issues one squeue call and one sacct call for all IDs at once to avoid
    the per-job request loop that would require N round-trips per poll cycle.
    Jobs absent from scheduler output are omitted from the result rather than
    returned as empty snapshots, so callers can distinguish "unknown to Slurm"
    from "seen but not yet in a terminal state."

    Args:
        job_ids: Slurm job IDs to query in one batch.  Batching is the
            entire point of this function; passing a single ID works but
            misses the efficiency goal.  Duplicates are deduplicated so the
            scheduler does not receive redundant job-ID entries.
        command_timeout: Wall-clock limit per scheduler command.  Exists to
            prevent a hung squeue or sacct call from stalling the async poll
            loop indefinitely; raises subprocess.TimeoutExpired on breach.
    """
```

A biological example — the Args entry explains the pipeline contract, not the type:

```python
@busco_env.task
def busco_assess_proteins(
    repeat_filter_results: Dir,
    busco_lineages_text: str,
    busco_sif: str = "",
) -> Dir:
    """Assess repeat-filtered protein completeness against a BUSCO lineage dataset.

    Args:
        repeat_filter_results: Result bundle from annotation_repeat_filtering.
            Must contain run_manifest.json and the final repeat-masked protein
            FASTA.  BUSCO runs against this protein set, not the raw BRAKER3
            output, so the repeat-filtering stage must complete first.
        busco_lineages_text: Comma-separated BUSCO lineage names
            (e.g. "eukaryota_odb10").  Each name must match a lineage
            directory installed in the BUSCO data path; the value controls
            which single-copy ortholog set the completeness assessment uses.
        busco_sif: Path to the BUSCO Apptainer image.  When empty, BUSCO
            runs from PATH; set this for cluster runs where the binary is
            not globally available.
    """
```

Anti-pattern — boilerplate that adds no information. This pattern exists in
parts of the codebase and should not be continued when touching those files:

```python
def _manifest_path(directory: Path, label: str) -> Path:
    """Resolve the manifest expected under one staged directory.

    Args:
        directory: A value used by the helper.
        label: A value used by the helper.

    Returns:
        The returned `Path` value used by the caller.
    """
```

## Inline Comments

Use inline comments only where they save real reader effort.  Every inline
comment must answer *why*, not *what*.  The code already says what it does;
a comment that restates the code adds noise.  A comment that explains a
biological assumption, a constraint from the pipeline notes, or an
engineering reason that is not visible from the code itself is worth keeping.

Good uses — each explains a reason that is not visible from the code alone:

```python
# squeue wins over sacct when both respond; squeue reflects live state
# while sacct may lag for recently completed jobs.
state = sq_state or sa_state
```

```python
# Exclusive lock for reads prevents a reader from seeing a partially-replaced
# record during a concurrent atomic write, even though os.replace is inode-
# atomic — the lock closes the read/write race window at the application level.
with _exclusive_record_lock(record_path):
    return load_slurm_run_record(source)
```

```python
# Deduplicate before building the CSV to avoid sending redundant job-ID
# entries to the scheduler; some Slurm versions treat duplicates as an error.
unique_ids = list(dict.fromkeys(job_ids))
```

```python
# Use the PASA-updated sorted GFF3, not the raw EVM output — repeat
# filtering must start from the post-PASA annotation boundary per the notes.
gff3 = _pasa_update_sorted_gff3(results_dir)
```

Avoid:

- restating what the code already says (`# increment counter` above `count += 1`)
- narrating simple assignments or obvious type conversions
- comments that describe *what* without saying *why* it is safe or necessary
- leaving comments that will go stale faster than the code they annotate

## Dataclass Docstrings

For dataclasses with non-obvious fields, add an `Attributes:` section to the
class docstring.  A good example in this repo is `SlurmPollingConfig` in
`slurm_monitor.py`, which documents each field's role and constraint rather
than just its type.

Simple dataclasses whose field names are self-evident do not need an
`Attributes:` section.  The threshold is whether a future reader would have
to check the default value or a calling site to understand what the field
controls.

Watch for copy-paste docstring drift among dataclasses.  Several dataclasses
in `spec_executor.py` share a boilerplate body ("It captures the node
metadata, resolved planner inputs, and frozen runtime policy...") that
describes `LocalNodeExecutionRequest` but was pasted into classes with
different purposes.  When touching any of those classes, replace the
boilerplate with a description that matches the actual class.

## Nested Functions and Closures in Tests

Inner functions defined inside test methods should use a one-liner docstring,
not a full Google-style Args/Returns block.  The caller is always the enclosing
test method; the context is already visible.

Correct:

```python
def handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
    """Stage a synthetic result directory and record the node call."""
    ...
```

Avoid (full Args/Returns sections on a 5-line closure add noise without value):

```python
def handler(request: LocalNodeExecutionRequest) -> dict[str, Path]:
    """Stage a synthetic result directory and record the node call.

    Args:
        request: The local execution request forwarded by the caller.

    Returns:
        The returned `dict[str, Path]` value used by the caller.
    """
    ...
```

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
