# Step 01 — `UnmappedBAM` Planner Type

## Model

**Sonnet 4.6** (`claude-sonnet-4-6`). Pure additive type work with round-trip
tests — same scope as Milestone A Step 01 and Milestone B Step 01 (`ReadPair`).

## Goal

Add `UnmappedBAM` to `src/flytetest/planner_types.py` with round-trip tests
in `tests/test_planner_types.py`.

## Context

- Milestone E plan §3: `docs/gatk_milestone_e/milestone_e_plan.md`.
- Pattern: `ReadPair` added in Milestone B (`src/flytetest/planner_types.py`).
  Copy its `@dataclass(frozen=True)` + `PlannerSerializable` structure exactly.
- Branch: `gatkport-e` (`git checkout -b gatkport-e`).

## What to build

### `src/flytetest/planner_types.py`

Add after `ReadPair`:

```python
@dataclass(frozen=True)
class UnmappedBAM(PlannerSerializable):
    """An unmapped BAM file with original read metadata preserved.

    Must be queryname-sorted (GATK MergeBamAlignment requirement).
    """
    bam_path: str
    sample_id: str
```

Add `"UnmappedBAM"` to `__all__`.

### `tests/test_planner_types.py`

Add `UnmappedBAMRoundTripTests` with:

- `test_unmapped_bam_round_trips` — full fields round-trip through
  `serialize_value_plain` / `deserialize_value_strict`.

## CHANGELOG

```
### GATK Milestone E Step 01 — UnmappedBAM planner type (YYYY-MM-DD)
- [x] YYYY-MM-DD added UnmappedBAM to src/flytetest/planner_types.py.
- [x] YYYY-MM-DD added round-trip test in tests/test_planner_types.py.
```

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/planner_types.py
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_planner_types.py -xvs -k "UnmappedBAM"
```

## Commit message

```
variant_calling: add UnmappedBAM planner type
```

## Checklist

- [ ] `UnmappedBAM` in `planner_types.py` with `bam_path`, `sample_id`.
- [ ] `"UnmappedBAM"` in `__all__`.
- [ ] Round-trip test passing.
- [ ] CHANGELOG updated.
- [ ] Step 01 marked Complete in `docs/gatk_milestone_e/checklist.md`.
