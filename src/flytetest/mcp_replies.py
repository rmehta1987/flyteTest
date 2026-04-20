"""Typed dataclasses for reshaped MCP reply payloads.

This module is the single source of truth for the new scientist-facing MCP
wire format introduced by the reshape plan. Tool implementations construct
these dataclasses and call ``dataclasses.asdict()`` at the tool boundary when
the FastMCP surface needs plain JSON-compatible dictionaries.

Only the reshaped run, plan, bundle, and validation replies live here.
Existing lifecycle-tool replies keep their current dict literals until a later
follow-up migrates them, if that proves worthwhile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SuggestedBundle:
    """One starter bundle suggested as a recovery path after a decline."""

    name: str
    description: str
    applies_to: tuple[str, ...]
    available: bool


@dataclass(frozen=True)
class SuggestedPriorRun:
    """One prior run whose outputs may satisfy a declined request."""

    run_id: str
    produced_type: str
    output_name: str
    hint: str


@dataclass(frozen=True)
class RunReply:
    """Success reply from the reshaped ``run_task`` and ``run_workflow`` tools."""

    supported: Literal[True]
    recipe_id: str
    run_record_path: str
    artifact_path: str
    execution_profile: Literal["local", "slurm"]
    execution_status: Literal["success", "failed"]
    exit_status: int | None
    outputs: dict[str, str]
    limitations: tuple[str, ...]
    task_name: str = ""
    workflow_name: str = ""


@dataclass(frozen=True)
class PlanDecline:
    """Structured decline reply for run, plan, and validation entrypoints."""

    supported: Literal[False]
    target: str
    pipeline_family: str
    limitations: tuple[str, ...]
    suggested_bundles: tuple[SuggestedBundle, ...] = ()
    suggested_prior_runs: tuple[SuggestedPriorRun, ...] = ()
    next_steps: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanSuccess:
    """Successful plan preview returned by the reshaped ``plan_request`` tool."""

    supported: Literal[True]
    target: str
    pipeline_family: str
    biological_goal: str
    requires_user_approval: bool
    bindings: dict[str, dict[str, object]]
    scalar_inputs: dict[str, object]
    composition_stages: tuple[str, ...]
    artifact_path: str
    suggested_next_call: dict[str, object]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class BundleAvailabilityReply:
    """Catalog entry returned by ``list_bundles()``."""

    name: str
    description: str
    pipeline_family: str
    applies_to: tuple[str, ...]
    binding_types: tuple[str, ...]
    available: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ValidateRecipeReply:
    """Validation reply returned by ``validate_run_recipe``."""

    supported: bool
    recipe_id: str
    execution_profile: Literal["local", "slurm"]
    findings: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class DryRunReply:
    """Preview reply returned when a reshaped run tool receives ``dry_run=True``."""

    supported: Literal[True]
    recipe_id: str
    artifact_path: str
    execution_profile: Literal["local", "slurm"]
    resolved_bindings: dict[str, dict[str, str]]
    resolved_environment: dict[str, object]
    staging_findings: tuple[dict[str, str], ...]
    limitations: tuple[str, ...]
    task_name: str = ""
    workflow_name: str = ""


__all__ = [
    "BundleAvailabilityReply",
    "DryRunReply",
    "PlanDecline",
    "PlanSuccess",
    "RunReply",
    "SuggestedBundle",
    "SuggestedPriorRun",
    "ValidateRecipeReply",
]