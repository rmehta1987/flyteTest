# MCP Surface Reshape Checklist

This checklist tracks the scientist-centered MCP surface reshape described in
`docs/mcp_reshape/mcp_reshape_plan.md`. It is separate from
`docs/realtime_refactor_checklist.md` (platform milestone tracker) and
`docs/dataserialization/checklist.md` (serialization + registry restructure).

Master plan: `docs/mcp_reshape/mcp_reshape_plan.md`.
Per-step submission prompts: `docs/mcp_reshape/prompts/`.

Use this file as the canonical shared tracker for this refactor. Future
sessions mark completed steps, record partial progress, and note blockers
here. Keep entries short and scannable.

## Branch

Work lands on the active MCP reshape branch (coordinate before starting).

## Status Labels

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

## Steps

Ordering groups the work so safer, additive foundation pieces land first,
then the coordinated BC-break reshape of the run tools, then the sweep of
call sites and documentation.

### Foundation (additive, no BC risk)

| # | Step | Plan section | Prompt | Status |
|---|------|--------------|--------|--------|
| 01 | Add `InterfaceField.required` default-True flag | §3b (commit 1) | `prompts/step_01_interface_field_required.md` | Complete |
| 02 | New module `mcp_replies.py` — typed reply dataclasses | §3d | `prompts/step_02_mcp_replies.md` | Complete |
| 03 | New module `errors.py` — typed exception hierarchy | §3g (commit 1) | `prompts/step_03_errors.md` | Complete |
| 04 | New module `bundles.py` — `ResourceBundle` + availability | §4 | `prompts/step_04_bundles.md` | Complete |
| 05 | New module `staging.py` — offline-staging preflight | §8 (module) | `prompts/step_05_staging.md` | Complete |
| 06 | `WorkflowSpec.tool_databases` field + round-trip | §8 (artifact) | `prompts/step_06_workflowspec_tool_databases.md` | Complete |
| 07 | `recipe_id` format → `<YYYYMMDDThhmmss.mmm>Z-<target>` | §3h | `prompts/step_07_recipe_id_format.md` | Complete |

### Registry + resolver

| # | Step | Plan section | Prompt | Status |
|---|------|--------------|--------|--------|
| 08 | Widen `_entry_payload` + `list_entries(pipeline_family)` | §1 | `prompts/step_08_list_entries_widening.md` | Complete |
| 09 | Registry–manifest name alignment sweep | §3b (commit 2) | `prompts/step_09_manifest_name_alignment.md` | Complete |
| 10 | Export `MANIFEST_OUTPUT_KEYS` on every task module | §3b (commit 3) | `prompts/step_10_manifest_output_keys.md` | Complete |
| 11 | `test_registry_manifest_contract.py` contract test | §3b (commit 4) | `prompts/step_11_manifest_contract_test.md` | Complete |
| 12 | Expand `execution_defaults` schema + resolution order | §3c | `prompts/step_12_execution_defaults_schema.md` | Complete |
| 13 | Typed exceptions in `_materialize_bindings` (raise path) | §3g (commit 2) | `prompts/step_13_resolver_typed_exceptions.md` | Complete |
| 14 | `$ref` binding grammar + durable-index lookup | §7 | `prompts/step_14_binding_grammar.md` | Complete |
| 15 | `list_available_bindings` additive `typed_bindings` field | §3f | `prompts/step_15_list_available_bindings_typed.md` | Not started |

### Planner

| # | Step | Plan section | Prompt | Status |
|---|------|--------------|--------|--------|
| 16 | Remove prose heuristics from `planning.py` | §5 | `prompts/step_16_remove_prose_heuristics.md` | Not started |
| 17 | `plan_request` asymmetric freeze (single-entry vs composed) | §3j | `prompts/step_17_plan_request_asymmetric_freeze.md` | Not started |

### Server reshape (BC break — coordinated)

| # | Step | Plan section | Prompt | Status |
|---|------|--------------|--------|--------|
| 18 | Operator-side logging (§3e) | §3e | `prompts/step_18_operator_logging.md` | Not started |
| 19 | Exception-to-decline translator `_execute_run_tool` | §3g (commit 4) | `prompts/step_19_execute_run_tool_wrapper.md` | Not started |
| 20 | Structured decline routing (bundles/prior-runs/next-steps) | §10 | `prompts/step_20_decline_routing.md` | Not started |
| 21 | Reshape `run_task` (bindings + dry_run + RunReply) | §2 / §3b / §3g / §3i | `prompts/step_21_run_task_reshape.md` | Not started |
| 22 | Reshape `run_workflow` (symmetric with `run_task`) | §3 / §3b / §3g / §3i | `prompts/step_22_run_workflow_reshape.md` | Not started |
| 23 | Wire `check_offline_staging` into `SlurmWorkflowSpecExecutor.submit` | §8 (executor) | `prompts/step_23_staging_preflight_slurm_submit.md` | Not started |
| 24 | Add `validate_run_recipe` MCP tool | §11 | `prompts/step_24_validate_run_recipe.md` | Not started |
| 25 | Register `list_bundles` / `load_bundle` on the server | §4 (server) | `prompts/step_25_bundle_tools_server.md` | Not started |

### Sweep + docs

| # | Step | Plan section | Prompt | Status |
|---|------|--------------|--------|--------|
| 26 | Call-site sweep for the BC migration | §12 | `prompts/step_26_call_site_sweep.md` | Not started |
| 27 | `mcp_contract.py` tool descriptions reframe | §6 | `prompts/step_27_mcp_contract_descriptions.md` | Not started |
| 28 | AGENTS / DESIGN / CHANGELOG / README + `.codex/` sweep | §14 / §15 | `prompts/step_28_docs_and_agent_context.md` | Not started |
| 29 | `docs/mcp_showcase.md` + `docs/tutorial_context.md` rewrite | §14 | `prompts/step_29_user_docs_rewrite.md` | Not started |
| 30 | Seed-bundle tool-DB reality check + audit | §13 | `prompts/step_30_seed_bundle_audit.md` | Not started |

## Verification Gates

Before merging, the plan's §Verification block must pass. Summary:

- `python -m compileall src/flytetest/`
- `rg -n "_extract_prompt_paths|_extract_braker_workflow_inputs|_extract_protein_workflow_inputs|_classify_target|_extract_execution_profile|_extract_runtime_images" src/flytetest/` → zero hits
- `rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/` → zero hits using the old flat `inputs=` shape
- `rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md` → zero stale references
- `python -c "import flytetest.server"` → startup robust regardless of `data/` state
- `pytest tests/` → green

## Hard Constraints

- Do not modify frozen saved artifacts at retry/replay time (AGENTS.md).
- Do not submit a Slurm job without a frozen run record.
- Do not change `classify_slurm_failure()` semantics without a decision record.
- Preserve the M15 P2 approval gate: `requires_user_approval` stays set for
  planner-composed novel DAGs; only registered single-entry targets via
  `run_task` / `run_workflow` bypass it.

## Out of Scope (this milestone)

See the master plan's `## Out of Scope` section. Highlights:

- Server-side LLM parsing; client-side NL is chosen.
- Backwards-compatibility shim for the old M21 flat `inputs` shape.
- Moving `TASK_PARAMETERS` onto `RegistryCompatibilityMetadata` — known
  coupling, slated for an immediate follow-up.
- Lighting up GATK — separate milestone; this plan preserves extensibility.
- Manifest-backed bundle file format (JSON/YAML instead of Python literals).
- Reply-size caps for scatter-gather workloads.
