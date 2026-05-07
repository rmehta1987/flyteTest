# Step 03 — extend_module_loads with documented precedence

## Context

`module_loads` on `ResourceSpec` currently *replaces* `DEFAULT_SLURM_MODULE_LOADS` rather than extending it. So `module_loads=["bcftools/1.20"]` silently drops the four defaults (`python/3.11.9`, `apptainer/1.4.1`, `gatk/4.5.0`, `samtools/1.22.1`). The escape hatch (importing `DEFAULT_SLURM_MODULE_LOADS` and splatting) requires importing a private constant — discoverable only via `AGENTS.md`. **This is the #1 silent footgun in the API.**

Add a new `extend_module_loads` field. When set alone, it appends to defaults (the common case). When both are set, `module_loads` wins (legacy behavior preserved) and a warning is logged so the user notices.

## Files to read before editing

- `src/flytetest/specs.py:39` — `ResourceSpec` definition (currently 9 fields after Step 01 settles; Step 03 makes it 10)
- `src/flytetest/spec_executor.py:1290` — `DEFAULT_SLURM_MODULE_LOADS`
- `src/flytetest/spec_executor.py:1393` — current `selected = module_loads or DEFAULT_SLURM_MODULE_LOADS` site
- `AGENTS.md` §Prompt/MCP/Slurm — the existing escape-hatch documentation (will need updating)

## Files to create / edit

| Action | File |
|---|---|
| Edit | `src/flytetest/specs.py` |
| Edit | `src/flytetest/spec_executor.py` |
| Edit | `tests/test_spec_executor.py` |
| Edit | `AGENTS.md` |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### `src/flytetest/specs.py`

Add `extend_module_loads` to `ResourceSpec`:

```python
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
    extend_module_loads: tuple[str, ...] = ()  # NEW
    notes: str | None = None
```

Update the `module_loads` field's docstring to point to `extend_module_loads` as the recommended path:

```python
module_loads: tuple[str, ...] = ()
"""Full replacement of DEFAULT_SLURM_MODULE_LOADS.

For most use cases prefer `extend_module_loads` instead — it appends to
the defaults rather than replacing them. Use `module_loads` only when
you need to drop a default (rare).

If both `module_loads` and `extend_module_loads` are set, `module_loads`
wins for backward compatibility and a warning is logged.
"""

extend_module_loads: tuple[str, ...] = ()
"""Modules to append to DEFAULT_SLURM_MODULE_LOADS for this recipe.

Recommended over `module_loads` for the common case of "I want the
defaults plus bcftools/1.20". The resulting module list is
DEFAULT_SLURM_MODULE_LOADS + extend_module_loads, in that order.

If both `module_loads` and `extend_module_loads` are set, this field is
ignored and a warning is logged — `module_loads` wins.
"""
```

### `src/flytetest/spec_executor.py:1393` — precedence + warning

Replace:

```python
selected = module_loads or DEFAULT_SLURM_MODULE_LOADS
```

with:

```python
import logging
logger = logging.getLogger(__name__)

def _resolve_module_loads(
    module_loads: tuple[str, ...],
    extend_module_loads: tuple[str, ...],
    *,
    defaults: tuple[str, ...] = DEFAULT_SLURM_MODULE_LOADS,
) -> tuple[str, ...]:
    """Resolve the effective module_loads list per documented precedence.

    Precedence:
      - module_loads alone → full replace (legacy)
      - extend_module_loads alone → defaults + extend
      - both → module_loads wins (legacy semantics), warning logged
      - neither → defaults
    """
    if module_loads and extend_module_loads:
        logger.warning(
            "Both module_loads (%r) and extend_module_loads (%r) set on "
            "ResourceSpec; module_loads wins, extend_module_loads is ignored. "
            "Use extend_module_loads alone for the common 'add to defaults' case.",
            list(module_loads),
            list(extend_module_loads),
        )
        return tuple(module_loads)
    if module_loads:
        return tuple(module_loads)
    if extend_module_loads:
        return tuple(defaults) + tuple(extend_module_loads)
    return tuple(defaults)
```

Replace the call site `selected = module_loads or DEFAULT_SLURM_MODULE_LOADS` with `selected = _resolve_module_loads(module_loads, extend_module_loads)`.

### Tests

- `extend_module_loads=["bcftools/1.20"]` produces `("python/3.11.9", "apptainer/1.4.1", "gatk/4.5.0", "samtools/1.22.1", "bcftools/1.20")` (5 modules)
- `module_loads=["mymod/1.0"]` produces `("mymod/1.0",)` (1 module — full replace, legacy)
- Both set → warning logged, returns `module_loads` value
- Neither set → returns DEFAULT_SLURM_MODULE_LOADS unchanged

Use `caplog` (pytest-caplog) to assert the warning fires when both are set.

### `AGENTS.md`

In the §Prompt/MCP/Slurm section, update the module-loads description:

Currently says (paraphrased): "module_loads is a full replacement of DEFAULT_SLURM_MODULE_LOADS. To extend, import the constant and splat: `module_loads=[*DEFAULT_SLURM_MODULE_LOADS, "bcftools/1.20"]`."

Replace with:

```
- `resource_request` accepts `module_loads` (full replacement of
  `DEFAULT_SLURM_MODULE_LOADS`) and `extend_module_loads` (appended to
  the defaults). Use `extend_module_loads` for the common case of
  adding a module to the defaults; use `module_loads` only when you
  need to drop a default. If both are set, `module_loads` wins and a
  warning is logged. The legacy splat pattern still works:
  `module_loads=[*DEFAULT_SLURM_MODULE_LOADS, "bcftools/1.20"]`.
```

## Acceptance criteria

- `ResourceSpec` has `extend_module_loads` field; docstring on both fields documents the precedence
- Setting `extend_module_loads` alone yields defaults + extension in module-load order
- Setting both fields produces a logged warning; `module_loads` wins
- Tests cover all 4 precedence cases
- `AGENTS.md` reflects the new convention

## CHANGELOG entry template

```
## Unreleased

### Slurm UX rollout — Phase 0 step 03 (2026-05-07)

- [x] 2026-05-07 `specs.py`: `ResourceSpec` adds `extend_module_loads` field. Recommended over `module_loads` for the common case of adding modules to `DEFAULT_SLURM_MODULE_LOADS`.
- [x] 2026-05-07 `spec_executor.py:1393`: precedence — `module_loads` alone full-replaces; `extend_module_loads` alone appends to defaults; both set → `module_loads` wins, warning logged. Eliminates the silent-drop footgun for the common case.
- [x] 2026-05-07 `AGENTS.md` §Prompt/MCP/Slurm: documented the new precedence and recommended path.
```
