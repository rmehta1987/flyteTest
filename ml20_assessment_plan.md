# Milestone 20 Assessment Plan

## Purpose

This plan reviews `ml20_plan.md` before implementation.  It keeps the
M20a/M20b split, but tightens the Slurm-facing data model, function boundaries,
and validation gates so M20a can land without surprising later resume, replay,
or MCP clients.

The main conclusion is: the milestone split is good, but the dataclass shape
should be more typed than the current draft suggests.  MCP inputs can remain
plain mappings, but durable records should store typed, inspectable
`ResourceSpec` values wherever possible.

## Assessment Checklist

- [ ] Confirm the M20a/M20b numbering change in the checklist and user-facing
      roadmap docs before implementation starts.
- [ ] Add `src/flytetest/planning.py` to the M20a touched-file list because
      `ResourceSpec.module_loads` must flow through resource coercion and merge.
- [ ] Replace the draft `dict[str, str]` durable override model with a typed
      `ResourceSpec | None` field unless implementation proves a raw mapping is
      needed for compatibility.
- [ ] Ensure child Slurm records capture both the effective `resource_spec` and
      the resource override used to produce it.
- [ ] Preserve the frozen artifact exactly as written; apply retry overrides
      only at submission time.
- [ ] Add cache-identity compatibility notes because adding a default
      `ResourceSpec` field can change serialized `BindingPlan` payloads.
- [ ] Use bounded log-tail reading instead of loading whole scheduler logs into
      memory.
- [ ] Quote module names when rendering `module load` lines.
- [ ] Update README, `docs/capability_maturity.md`, `docs/mcp_showcase.md`,
      `docs/mcp_cluster_prompt_tests.md`, `docs/realtime_refactor_checklist.md`,
      milestone submission prompts, and `CHANGELOG.md` when the restructure or
      M20a behavior lands.

## Dataclass Assessment

### `ResourceSpec.module_loads`

The draft field is a good fit for `ResourceSpec` because module loading is part
of the scheduler/runtime resource contract, not a biological input.

Recommended shape:

```python
@dataclass(frozen=True, slots=True)
class ResourceSpec(SpecSerializable):
    """Describe expected compute resources for one step or workflow.

    Attributes:
        module_loads: Scheduler environment modules to load before activating
            the project runtime.  Empty means use FLyteTest's Slurm defaults
            for backward-compatible submissions.
    """

    cpu: str | None = None
    memory: str | None = None
    gpu: str | None = None
    queue: str | None = None
    account: str | None = None
    walltime: str | None = None
    execution_class: str | None = None
    module_loads: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
```

Implementation note: update `_coerce_resource_spec()` and
`_merge_resource_specs()` in `planning.py`.  Adding the field only to
`specs.py` will round-trip JSON, but it will not let MCP callers pass the
value through `prepare_run_recipe(resource_request=...)`.

### `SlurmRunRecord.resource_overrides`

The draft field is useful, but `dict[str, str]` is weaker than the repo's typed
spec model.  Prefer a typed optional override:

```python
@dataclass(frozen=True, slots=True)
class SlurmRunRecord(SpecSerializable):
    """Durable filesystem record for one accepted Slurm recipe submission.

    Attributes:
        resource_spec: Effective resource spec used to render the submitted
            `sbatch` script.  On escalation retries this includes overrides.
        resource_overrides: Explicit user-requested retry escalation values,
            if any.  `None` means the submission used the frozen recipe's
            resource spec unchanged.
    """

    resource_spec: ResourceSpec | None = None
    resource_overrides: ResourceSpec | None = None
```

This keeps the audit trail inspectable:

- `resource_spec` answers "what did this Slurm child actually request?"
- `resource_overrides` answers "what did the user change for this retry?"
- the saved artifact still answers "what was originally frozen?"

If the implementation keeps a mapping for compatibility, it should still
normalize the mapping through a helper and reject unknown keys before writing
the record.

### `SlurmLifecycleResult` tails

Do not add stdout/stderr tail fields to executor dataclasses unless the
executor starts reading files.  The current draft says log reading should live
in the server layer, so keep `SlurmLifecycleResult` pure and add the tails only
to the MCP response serialization.

## Function Examples

The examples below are intended as implementation guidance.  Names can shift to
fit the surrounding code, but the boundaries should remain the same.

### Coerce retry resource overrides

```python
_RETRY_RESOURCE_OVERRIDE_FIELDS = {
    "cpu",
    "memory",
    "walltime",
    "queue",
    "account",
    "gpu",
}


def _coerce_retry_resource_overrides(
    value: Mapping[str, Any] | ResourceSpec | None,
) -> tuple[ResourceSpec | None, tuple[str, ...]]:
    """Normalize MCP retry overrides into a typed resource spec.

    Args:
        value: Optional MCP-provided escalation values.  Mappings are accepted
            at the API edge, while durable records store a typed `ResourceSpec`.

    Returns:
        A typed override plus validation limitations.  A non-empty limitations
        tuple means the caller should decline without submitting a job.
    """
    if value is None:
        return None, ()
    if isinstance(value, ResourceSpec):
        return value, ()

    unknown = sorted(set(value) - _RETRY_RESOURCE_OVERRIDE_FIELDS)
    if unknown:
        return None, (f"Unsupported resource override key(s): {', '.join(unknown)}.",)

    kwargs = {
        key: str(raw)
        for key, raw in value.items()
        if key in _RETRY_RESOURCE_OVERRIDE_FIELDS and raw not in (None, "")
    }
    if not kwargs:
        return None, ("resource_overrides was provided but did not contain any non-empty override values.",)
    return ResourceSpec(**kwargs), ()
```

### Apply overrides without mutating the frozen recipe

```python
def _effective_resource_spec(
    frozen_resource_spec: ResourceSpec | None,
    resource_overrides: ResourceSpec | None,
) -> ResourceSpec | None:
    """Overlay retry escalation values onto the frozen Slurm resource spec."""
    if resource_overrides is None:
        return frozen_resource_spec
    base = frozen_resource_spec or ResourceSpec()
    return replace(
        base,
        cpu=resource_overrides.cpu or base.cpu,
        memory=resource_overrides.memory or base.memory,
        gpu=resource_overrides.gpu or base.gpu,
        queue=resource_overrides.queue or base.queue,
        account=resource_overrides.account or base.account,
        walltime=resource_overrides.walltime or base.walltime,
        execution_class=resource_overrides.execution_class or base.execution_class,
        module_loads=resource_overrides.module_loads or base.module_loads,
        notes=(*base.notes, *resource_overrides.notes),
    )
```

Use the effective resource spec in `_submit_saved_artifact()`:

```python
effective_resource_spec = _effective_resource_spec(
    binding_plan.resource_spec,
    resource_overrides,
)

script_text = render_slurm_script(
    artifact_path=artifact_path,
    workflow_name=workflow_spec.name,
    run_id=run_id,
    stdout_path=stdout_path,
    stderr_path=stderr_path,
    resource_spec=effective_resource_spec,
    repo_root=self._repo_root,
    python_executable=self._python_executable,
    resume_from_local_record=resume_from_local_record,
)

record = SlurmRunRecord(
    ...,
    resource_spec=effective_resource_spec,
    resource_overrides=resource_overrides,
    ...,
)
```

### Gate resource-exhaustion retry

```python
def retry(
    self,
    run_record_source: Path,
    *,
    resource_overrides: Mapping[str, Any] | ResourceSpec | None = None,
) -> SlurmRetryResult:
    """Resubmit one failed Slurm run from its durable run record."""
    ...
    override_spec, override_limitations = _coerce_retry_resource_overrides(resource_overrides)
    if override_limitations:
        return SlurmRetryResult(
            supported=False,
            source_run_record=current_record,
            failure_classification=failure_classification,
            retry_policy=current_record.retry_policy,
            action="retry",
            limitations=override_limitations,
        )

    escalation_retry = (
        failure_classification.failure_class == "resource_exhaustion"
        and override_spec is not None
    )
    if not failure_classification.retryable and not escalation_retry:
        return SlurmRetryResult(
            supported=False,
            source_run_record=current_record,
            failure_classification=failure_classification,
            retry_policy=current_record.retry_policy,
            action="retry",
            limitations=(
                f"Run `{current_record.run_id}` is classified as "
                f"`{failure_classification.failure_class}` and is not retryable. "
                f"{failure_classification.detail}",
            ),
        )

    retry_execution = self._submit_saved_artifact(
        current_record.artifact_path,
        retry_parent=current_record,
        resource_overrides=override_spec,
    )
```

Keep `classify_slurm_failure()` conservative.  `TIMEOUT`, `OUT_OF_MEMORY`, and
`DEADLINE` can remain `retryable=False`; the new behavior is an explicit user
escalation path, not automatic retryability.

### Render configurable module loads

```python
DEFAULT_SLURM_MODULE_LOADS = ("python/3.11.9", "apptainer/1.4.1")


def _slurm_module_load_lines(resource_spec: ResourceSpec | None) -> list[str]:
    """Render scheduler module-load commands for the generated Slurm script."""
    module_loads = resource_spec.module_loads if resource_spec is not None else ()
    selected_modules = module_loads or DEFAULT_SLURM_MODULE_LOADS
    return [f"  module load {shlex.quote(module_name)}" for module_name in selected_modules]
```

Then `render_slurm_script()` can keep the current optional-module block:

```python
return "\n".join(
    [
        "#!/usr/bin/env bash",
        *directives,
        "set -euo pipefail",
        f"cd {shlex.quote(str(repo_root))}",
        "if command -v module >/dev/null 2>&1; then",
        *_slurm_module_load_lines(resource_spec),
        "fi",
        ...
    ]
)
```

### Read bounded scheduler log tails

```python
MAX_MONITOR_TAIL_LINES = 500


def _read_text_tail(
    path: Path | None,
    *,
    tail_lines: int,
    allowed_root: Path,
) -> str | None:
    """Read a bounded tail from a scheduler log under the run directory."""
    if path is None or tail_lines == 0:
        return None
    if tail_lines < 0:
        raise ValueError("tail_lines must be >= 0")

    line_count = min(tail_lines, MAX_MONITOR_TAIL_LINES)
    try:
        resolved_path = path.resolve()
        resolved_root = allowed_root.resolve()
        if not resolved_path.is_relative_to(resolved_root) or not resolved_path.is_file():
            return None
        with resolved_path.open("r", encoding="utf-8", errors="replace") as handle:
            return "".join(deque(handle, maxlen=line_count)).rstrip("\n")
    except OSError:
        return None
```

Use it from `_monitor_slurm_job_impl()` after reconciliation:

```python
lifecycle = _result_from_slurm_lifecycle(result)
record = result.run_record
if record is not None and record.final_scheduler_state is not None:
    lifecycle["stdout_tail"] = _read_text_tail(
        record.stdout_path,
        tail_lines=tail_lines,
        allowed_root=record.run_record_path.parent,
    )
    lifecycle["stderr_tail"] = _read_text_tail(
        record.stderr_path,
        tail_lines=tail_lines,
        allowed_root=record.run_record_path.parent,
    )
else:
    lifecycle["stdout_tail"] = None
    lifecycle["stderr_tail"] = None
```

## Test Improvements Over `ml20_plan.md`

Add the original tests, plus these extra guards:

1. `prepare_run_recipe(resource_request={"module_loads": [...]})` persists the
   tuple after `_coerce_resource_spec()`.
2. `_merge_resource_specs()` preserves registry defaults while caller
   `module_loads` overrides only the module list.
3. Resource override retry from `OUT_OF_MEMORY` writes child
   `resource_spec.memory == "64Gi"` and child `resource_overrides.memory ==
   "64Gi"`.
4. Resource override retry from `TIMEOUT` writes child
   `resource_spec.walltime == "04:00:00"`.
5. `DEADLINE` either follows the same resource-exhaustion override path or is
   explicitly documented as excluded.
6. Unknown override key, negative `tail_lines`, and oversized `tail_lines` are
   rejected or clamped predictably.
7. Log-tail reading ignores a tampered path outside the run-record directory.
8. Empty `module_loads` continues to render `python/3.11.9` and
   `apptainer/1.4.1`.
9. Custom module names are shell-quoted in the rendered script.
10. A legacy artifact or run-record payload lacking `module_loads` still loads
    through `ResourceSpec.from_dict()`.

Avoid hard-coding the full test count in the verification text.  The useful
contract is the command and the expected pass/fail shape, not the number of
tests that existed when the plan was written.

## Documentation Improvements Over `ml20_plan.md`

The M20a implementation should update the places that currently describe
resource failures as requiring a brand-new recipe:

- `docs/mcp_showcase.md`
- `docs/mcp_cluster_prompt_tests.md`
- `src/flytetest/mcp_contract.py`
- `README.md`
- `docs/capability_maturity.md`
- `docs/realtime_refactor_checklist.md`
- `docs/realtime_refactor_milestone_20_submission_prompt.md` or its M20b
  replacement
- `CHANGELOG.md`

Also soften or document the "P2a track" phrase from `ml20_plan.md`; this label
is not currently obvious from the nearby roadmap docs.

## Acceptance Gate

M20a is ready to implement when the updated handoff plan answers these
questions:

- Which dataclass fields are additive metadata, and which affect effective
  execution?
- Does the child Slurm run record describe the effective resources used in the
  generated script?
- Are override inputs validated before `sbatch` is called?
- Does module loading remain backward-compatible for existing Slurm recipes?
- Are log tails bounded and limited to expected scheduler log locations?
- Are docs updated where current behavior changes from "re-prepare" to
  "explicit escalation retry"?
