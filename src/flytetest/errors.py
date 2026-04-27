"""Typed exception hierarchy for the MCP exception-to-decline translation layer.

Raising a :class:`PlannerResolutionError` subclass opts the failure into the
exception-to-decline translation layer implemented in the ``_execute_run_tool``
wrapper (Step 19).  The wrapper catches any ``PlannerResolutionError``, reads
its structured attributes, and populates a ``PlanDecline`` with a
``next_steps`` field derived from those attributes.

Any other exception propagates normally and is logged via the §3e error-logging
path.  Do not raise a ``PlannerResolutionError`` for programming errors or
unexpected failures — only for well-understood resolution failures where a
structured decline with recovery hints is appropriate.
"""

from __future__ import annotations

from typing import Literal


class PlannerResolutionError(Exception):
    """Base class for all structured planner-resolution failures.

    Subclasses store contextual fields as attributes so that the
    exception-to-decline translation layer can build a deterministic
    ``PlanDecline.next_steps`` without parsing the message string.
    """


class UnknownRunIdError(PlannerResolutionError):
    """Raised when a referenced ``run_id`` is not found in the run index.

    Attributes:
        run_id: The run identifier that was not found.
        available_count: Number of run records currently in the index.
    """

    def __init__(self, run_id: str, available_count: int) -> None:
        self.run_id = run_id
        self.available_count = available_count
        super().__init__(
            f"run_id {run_id!r} not found; {available_count} run(s) available in the index"
        )


class UnknownOutputNameError(PlannerResolutionError):
    """Raised when a referenced output name does not exist on a known run.

    Attributes:
        run_id: The run identifier whose outputs were searched.
        output_name: The output name that was not found.
        known_outputs: All output names that *are* present on the run.
    """

    def __init__(
        self,
        run_id: str,
        output_name: str,
        known_outputs: tuple[str, ...],
    ) -> None:
        self.run_id = run_id
        self.output_name = output_name
        self.known_outputs = known_outputs
        known_str = ", ".join(known_outputs) if known_outputs else "(none)"
        super().__init__(
            f"output {output_name!r} not found on run {run_id!r}; "
            f"known outputs: {known_str}"
        )


class BindingPathMissingError(PlannerResolutionError):
    """Raised when a binding-resolved filesystem path does not exist on disk.

    Covers both raw-path bindings (the scientist wrote the path directly) and
    ``$manifest`` bindings (the scientist named a manifest sidecar that, in
    turn, is missing).  The ``kind`` field records which binding form was
    being resolved when the path came up missing — both produce identical
    recovery advice in the translator, but the message wording preserves the
    distinction so a scientist can see whether the missing file was the
    manifest or the raw-path target.

    Attributes:
        path: The filesystem path that was expected but not found.
        kind: ``"raw_path"`` for direct path bindings; ``"manifest"`` for
            ``$manifest`` bindings whose sidecar file is absent.
    """

    def __init__(self, path: str, *, kind: Literal["raw_path", "manifest"] = "raw_path") -> None:
        self.path = path
        self.kind = kind
        prefix = "manifest path" if kind == "manifest" else "binding path"
        super().__init__(f"{prefix} {path!r} does not exist on disk")


class BindingTypeMismatchError(PlannerResolutionError):
    """Raised when a resolved binding source produces the wrong planner type.

    Attributes:
        binding_key: Planner type requested by the caller.
        resolved_type: Planner type or source type actually produced.
        source: Human-readable origin of the resolved value.
    """

    def __init__(self, binding_key: str, resolved_type: str, source: str) -> None:
        self.binding_key = binding_key
        self.resolved_type = resolved_type
        self.source = source
        super().__init__(
            f"binding {binding_key!r} expected {binding_key!r} but source "
            f"{source!r} resolved to {resolved_type!r}"
        )
