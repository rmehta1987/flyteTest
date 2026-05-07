# Step 04 — ResourceSpec format validators

## Context

`ResourceSpec` fields are typed as `str | None` with no validation. So a user can set `memory="32 GB"` (with a space — Slurm rejects this format), `walltime="48h"` (not Slurm format), or `cpu="eight"` (not a number) and the freeze succeeds. The error surfaces 30 seconds into the sbatch attempt instead of immediately. Add `__post_init__` validators that catch these at freeze time.

## Files to read before editing

- `src/flytetest/specs.py:39` — `ResourceSpec` definition (10 fields after Step 03)
- Slurm format references for memory units, walltime, CPU
- Existing tests for `ResourceSpec` (verify that valid existing specs still pass)

## Files to create / edit

| Action | File |
|---|---|
| Edit | `src/flytetest/specs.py` |
| Edit | `tests/test_specs.py` (or matching test file — create if missing) |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### `src/flytetest/specs.py` — `__post_init__`

```python
import re

_MEMORY_RE = re.compile(r"^\d+(\.\d+)?(K|M|G|T)i?$")
_WALLTIME_RE = re.compile(r"^(\d+-)?\d{1,2}:\d{2}(:\d{2})?$")

@dataclass(frozen=True)
class ResourceSpec:
    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None
    partition: str | None = None
    account: str | None = None
    walltime: str | None = None
    execution_class: str | None = None
    module_loads: tuple[str, ...] = ()
    extend_module_loads: tuple[str, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.memory is not None and not _MEMORY_RE.match(self.memory):
            raise ValueError(
                f"memory={self.memory!r} does not match expected format "
                f"<number>(K|M|G|T)[i] (e.g., '32G', '2Ti'). "
                f"Common mistake: trailing/leading whitespace; do not include 'B' or 'GB'."
            )
        if self.walltime is not None and not _WALLTIME_RE.match(self.walltime):
            raise ValueError(
                f"walltime={self.walltime!r} does not match Slurm format "
                f"D-HH:MM:SS or HH:MM:SS or HH:MM (e.g., '04:00:00', '1-12:00:00'). "
                f"Common mistake: '48h' or '4 hours' — Slurm requires colon-separated."
            )
        if self.cpu is not None:
            try:
                cpu_int = int(self.cpu)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"cpu={self.cpu!r} is not a positive integer string."
                ) from exc
            if cpu_int <= 0:
                raise ValueError(f"cpu={self.cpu!r} must be a positive integer.")
        if self.execution_class and self.execution_class != "local":
            if not (self.partition and self.partition.strip()):
                raise ValueError(
                    f"partition is required for execution_class={self.execution_class!r} "
                    f"(empty / whitespace not allowed)."
                )
            if not (self.account and self.account.strip()):
                raise ValueError(
                    f"account is required for execution_class={self.execution_class!r} "
                    f"(empty / whitespace not allowed)."
                )
```

Note on `frozen=True` dataclasses: `__post_init__` runs after the field assignments, and it can raise without complications since no mutation is needed. If validation needs to *modify* a field (which we don't), we'd need `object.__setattr__`.

### Tests

```python
def test_memory_with_space_raises():
    with pytest.raises(ValueError, match="memory="):
        ResourceSpec(memory="32 GB")

def test_walltime_non_slurm_format_raises():
    with pytest.raises(ValueError, match="walltime="):
        ResourceSpec(walltime="48h")

def test_cpu_non_integer_raises():
    with pytest.raises(ValueError, match="cpu="):
        ResourceSpec(cpu="eight")

def test_partition_required_for_slurm():
    with pytest.raises(ValueError, match="partition is required"):
        ResourceSpec(execution_class="slurm", account="mylab")

def test_account_required_for_slurm():
    with pytest.raises(ValueError, match="account is required"):
        ResourceSpec(execution_class="slurm", partition="caslake")

def test_valid_spec_passes():
    spec = ResourceSpec(
        cpu="8",
        memory="32G",
        walltime="04:00:00",
        partition="caslake",
        account="mylab",
        execution_class="slurm",
    )
    assert spec.memory == "32G"

def test_local_execution_no_partition_required():
    # execution_class="local" or None → partition/account not required
    ResourceSpec(execution_class="local")  # should not raise
    ResourceSpec()  # should not raise
```

Run the existing test suite to confirm no fixture creates a `ResourceSpec` with newly-rejected values. If any do, that's a real bug exposed by the validators — fix the fixture.

## Acceptance criteria

- `ResourceSpec(memory="32 GB")` raises `ValueError`
- `ResourceSpec(walltime="48h")` raises `ValueError`
- `ResourceSpec(cpu="eight")` raises `ValueError`
- `ResourceSpec(execution_class="slurm", account="x")` raises (missing partition)
- `ResourceSpec(execution_class="slurm", partition="x")` raises (missing account)
- All existing valid specs still pass freeze
- `python -m pytest tests/` shows no new test failures attributable to this change

## CHANGELOG entry template

```
## Unreleased

### Slurm UX rollout — Phase 0 step 04 (2026-05-07)

- [x] 2026-05-07 `specs.py`: `ResourceSpec.__post_init__` validates `memory`, `walltime`, `cpu`, and (when `execution_class != "local"`) `partition` and `account` formats at freeze time. Catches typos like `memory="32 GB"` (with space) or `walltime="48h"` before sbatch instead of 30 seconds into the submit attempt.
```
