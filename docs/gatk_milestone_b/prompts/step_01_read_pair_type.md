# Step 01 — Add `ReadPair` Planner Type

## Goal

Add `ReadPair` to `src/flytetest/planner_types.py` so that the
`bwa_mem2_mem` task (Step 03) and `preprocess_sample` workflow (Step 07)
have a typed input surface for paired-end FASTQ reads.

## Context

- Milestone B plan: `docs/gatk_milestone_b/milestone_b_plan.md` §3.
- Existing planner types for reference: `AlignmentSet`, `KnownSites` (added
  in Milestone A Step 01).
- Test coverage lives in `tests/test_planner_types.py`.
- Pattern: inherit `PlannerSerializable`, use `@dataclass(frozen=True)`,
  add to `__all__`.

## What to build

### `src/flytetest/planner_types.py`

Add after `AlignmentSet`:

```python
@dataclass(frozen=True)
class ReadPair(PlannerSerializable):
    """Paired-end FASTQ inputs for one sample."""
    sample_id: str
    r1_path: str
    r2_path: str | None = None
```

Add `"ReadPair"` to `__all__`.

### `tests/test_planner_types.py`

Add a `ReadPairRoundTripTests` class with at least:

- `test_read_pair_paired_round_trips` — `ReadPair(sample_id="s1", r1_path="/r1.fq.gz", r2_path="/r2.fq.gz")` round-trips through `serialize_value_plain` / `deserialize_value_strict`.
- `test_read_pair_single_end_round_trips` — `ReadPair(sample_id="s1", r1_path="/r1.fq.gz")` round-trips (r2_path=None).

### `CHANGELOG.md`

Add under `## Unreleased`:

```
### GATK Milestone B Step 01 — ReadPair planner type (YYYY-MM-DD)
- [x] YYYY-MM-DD added `ReadPair` dataclass to `src/flytetest/planner_types.py`.
- [x] YYYY-MM-DD added paired and single-end round-trip tests to `tests/test_planner_types.py`.
```

## Commit message

```
variant_calling: add ReadPair planner type for paired-end FASTQ inputs
```

## Checklist

- [ ] `ReadPair` in `planner_types.py` with `sample_id`, `r1_path`, `r2_path`.
- [ ] `"ReadPair"` in `__all__`.
- [ ] Two round-trip tests passing.
- [ ] `pytest tests/test_planner_types.py -xvs` green.
- [ ] CHANGELOG updated.
- [ ] Step 01 marked Complete in `docs/gatk_milestone_b/checklist.md`.
