# Step 01 — Extend `haplotype_caller` with Optional Intervals

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Backward-compatible signature change
on an existing task. The key risk is accidentally breaking the 4 existing
`HaplotypeCallerInvocationTests` — verify those pass before committing.

## Goal

Add `intervals: list[str] | None = None` to `haplotype_caller` in
`src/flytetest/tasks/variant_calling.py`. When non-empty, emit one `-L
<interval>` flag per entry. Existing behavior (whole-genome, no `-L`)
preserved when `intervals` is `None` or `[]`.

## Context

- Milestone F plan §4: `docs/gatk_milestone_f/milestone_f_plan.md`.
- Existing task: `haplotype_caller` in `src/flytetest/tasks/variant_calling.py`
  (Milestone A, `File`-based signature with `@variant_calling_env.task`).
- Branch: `gatkport-f` (`git checkout -b gatkport-f`).

## What to build

### `src/flytetest/tasks/variant_calling.py`

In `haplotype_caller`, add `intervals: list[str] | None = None` before
`gatk_sif`. Insert after the `cmd` list is built, before `run_tool`:

```python
for interval in (intervals or []):
    cmd.extend(["-L", interval])
```

No other changes. The output filename, manifest keys, and return type are
unchanged.

### `tests/test_variant_calling.py`

Add to the existing `HaplotypeCallerInvocationTests` class:

- `test_haplotype_caller_with_intervals_adds_L_flags` — patches `run_tool`;
  calls `haplotype_caller` with `intervals=["chr1", "chr2:1-1000000"]`;
  asserts `-L chr1` and `-L chr2:1-1000000` appear in the captured cmd.
- `test_haplotype_caller_no_intervals_omits_L` — calls without `intervals`;
  asserts `-L` does **not** appear in the captured cmd.

Existing `HaplotypeCallerInvocationTests` tests must all still pass unchanged.

## CHANGELOG

```
### GATK Milestone F Step 01 — haplotype_caller interval support (YYYY-MM-DD)
- [x] YYYY-MM-DD extended haplotype_caller with optional intervals parameter (backward compatible).
- [x] YYYY-MM-DD added 2 new tests; all existing HaplotypeCaller tests pass.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/tasks/variant_calling.py
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs -k "HaplotypeCaller"
```

All `HaplotypeCallerInvocationTests` must pass including the two new tests.

## Commit message

```
variant_calling: extend haplotype_caller with optional intervals support
```

## Checklist

- [ ] `intervals: list[str] | None = None` parameter added.
- [ ] `-L` flags emitted only when `intervals` is non-empty.
- [ ] All existing `HaplotypeCallerInvocationTests` still pass.
- [ ] 2 new interval-specific tests passing.
- [ ] CHANGELOG updated.
- [ ] Step 01 marked Complete in checklist.
