# MCP Surface Reshape — Implementation Plan

Master plan: `/home/rmeht/.claude/plans/replicated-growing-cookie.md`. This document is the implementer's checklist.

## Goal

Replace the brittle prose-parsing MCP surface with a typed "experiment loop" (`list_entries` → `list_bundles` → `load_bundle` → `run_task`/`run_workflow`), preserving flyteTest's four DESIGN pillars (typed biological contracts, frozen run recipes with `source_prompt`, pipeline-family stage order, offline-HPC staging). Hard-break the M21 flat `inputs` shape on `run_task` / `run_workflow` as an intentional coordinated migration (DESIGN §8.7).

## Ordered commits

Each bullet is intended as one atomic commit with a descriptive subject. Run `python -m compileall` on touched files + the relevant focused tests before each commit.

1. **Registry payload widening.** `server.py::_entry_payload` returns `pipeline_family`, `pipeline_stage_order`, `biological_stage`, `accepted_planner_types`, `produced_planner_types`, `supported_execution_profiles`, `slurm_resource_hints`, `local_resource_defaults`, full `inputs` + `outputs` InterfaceField lists, and the full `execution_defaults` dict (including any new runtime-image / tool-DB / module-loads / env-vars keys). Add `pipeline_family` cosmetic filter. Return only entries with non-empty `showcase_module`. Tests: category filter, pipeline_family filter, non-showcased exclusion.

2. **New module `src/flytetest/bundles.py`.** `ResourceBundle` dataclass with fields `name, description, pipeline_family, bindings, inputs, runtime_images, tool_databases, applies_to`. `BundleAvailability` dataclass. `_check_bundle_availability(b)` returns structured availability without raising. `list_bundles(pipeline_family=None)` returns all bundles with `available` flag and `reasons`. `load_bundle(name)` returns `supported=True` payload or `supported=False` with reasons; raises `KeyError` only for unknown names. **No module-level validation call.** Seed with bundles for existing fixtures under `data/` — audit first, drop any whose backing data is absent. Tests: listing with mixed availability, loading available and unavailable bundles, startup robustness with broken fixture.

3. **New module `src/flytetest/staging.py`.** `StagingFinding` dataclass, `check_offline_staging(artifact, shared_fs_roots)` walks `artifact.runtime_images`, `artifact.tool_databases`, `artifact.resolved_input_paths` and returns findings. `local` profile skips shared-fs check but verifies existence; `slurm` profile enforces both. Tests: missing container, missing tool DB, path outside shared_fs_roots.

4. **`WorkflowSpec` grows `tool_databases: dict[str, str]`.** Update `spec_artifacts.py`; `artifact_from_typed_plan` wires from plan; `save_workflow_spec_artifact` + `load_workflow_spec_artifact` serialize round-trip; existing frozen artifacts on disk continue to load with an empty dict default (read-path backward compat, since we never modify frozen artifacts per AGENTS.md hard constraint). Tests: round-trip with and without the field.

5. **Expand `execution_defaults` schema.** Document four optional keys on `RegistryCompatibilityMetadata.execution_defaults`: `runtime_images: dict[str, str]`, `module_loads: tuple[str, ...]`, `env_vars: dict[str, str]`, `tool_databases: dict[str, str]`. Populate on existing entries where appropriate (BRAKER3 annotation, BUSCO QC). Add resolution order in `plan_typed_request`: entry defaults → bundle fields → explicit kwargs. Tests: entry-only defaults, bundle override, kwarg override, all layered together; resolved environment frozen into `WorkflowSpec`.

6. **`_materialize_bindings` binding-value grammar.** `resolver.py::_materialize_bindings` dispatches on three mutually-exclusive forms inside each binding dict: raw path (existing), `$manifest` (existing), `$ref` (new — reads `durable_asset_index.json` via `LocalManifestAssetResolver.resolve(..., durable_index=...)`). All three lower to the same concrete planner dataclass, and the resolved concrete path is what gets frozen into the `WorkflowSpec`. Tests: raw form, `$manifest` form, `$ref` form, unknown run_id decline, missing output_name decline, ambiguous resolution decline.

7. **Reshape `run_task`** at `server.py:995`. New signature: `(task_name, bindings=None, inputs=None, resources=None, execution_profile="local", runtime_images=None, tool_databases=None, source_prompt="")`. Validate bindings against `entry.compatibility.accepted_planner_types`. Derive scalars via `_scalar_params_for_task(task_name, bindings)`. Call `plan_typed_request`; freeze via `artifact_from_typed_plan` + `save_workflow_spec_artifact`; dispatch via `LocalWorkflowSpecExecutor` / `SlurmWorkflowSpecExecutor`. Return `outputs: dict` (not `output_paths`) via `_collect_named_outputs(entry, run_record_path)`. Empty `source_prompt` appends advisory to `limitations`. Tests: bundle spread, unknown bindings decline, missing scalar decline, freeze happens, outputs dict keyed by registry.

8. **Reshape `run_workflow`** at `server.py:869` — symmetric signature to `run_task` including `bindings` and `tool_databases`. Preserve the BRAKER3 evidence-check limitation, reworded to accept either scalar-path inputs OR typed `ReadSet` / `ProteinEvidenceSet` bindings. Tests: bundle spread, symmetric call with `run_task`, named outputs.

9. **Staging preflight wired into Slurm submit.** `SlurmWorkflowSpecExecutor.submit` calls `check_offline_staging(artifact, shared_fs_roots)` before `sbatch`; non-empty findings short-circuit with structured `limitations` and a decline reply — no `sbatch` call made. `classify_slurm_failure()` untouched. Tests: missing container blocks submit; missing tool-DB blocks submit; all-present path proceeds.

10. **Add `validate_run_recipe` MCP tool.** Takes `artifact_path`, `execution_profile`, optional `shared_fs_roots`. Loads the artifact, resolves every binding through `LocalManifestAssetResolver` (catching exceptions as findings), runs `check_offline_staging`, returns `{"supported": bool, "recipe_id": ..., "findings": [...]}`. Register in `create_mcp_server()`. Tests: clean recipe passes, missing binding fails, missing container fails.

11. **Structured decline routing.** `_limitation_reply` / `_unsupported_target_reply` populate `suggested_bundles` (filtering out unavailable bundles via `_check_bundle_availability`), `suggested_prior_runs` (reads durable asset index for entries whose `produced_planner_types` match what the declined target accepts), and a human-readable `next_steps` list. Tests: decline for BRAKER3 with no inputs returns all three channels populated; decline with no available bundle returns only `next_steps`.

12. **Remove prose heuristics from `planning.py`.** Delete `_extract_prompt_paths`, `_extract_braker_workflow_inputs`, `_extract_protein_workflow_inputs`, `_extract_execution_profile`, `_extract_runtime_images`, `_classify_target`, M18 BUSCO keyword branch. `plan_typed_request` becomes structured-only with no prose parameter parsing. `plan_request` tool returns a structured decline pointing at `list_entries` / `list_bundles` / `run_task` / `run_workflow` rather than attempting prose parsing. `_try_composition_fallback` preserved unchanged. Tests: previously prose-parsed flows now either work via structured calls or decline cleanly.

13. **Call-site sweep.** `rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/` — every hit is a call-site review. Update test fixtures, smoke scripts, `docs/mcp_showcase.md`, `docs/tutorial_context.md`, any active milestone planning docs that quote the old flat `inputs=` shape. Acceptance: green CI with no uses of the old shape.

14. **MCP contract and tool descriptions.** `mcp_contract.py`: reframe around the experiment loop; add a one-sentence note to `run_task`/`run_workflow`/`run_slurm_recipe` descriptions that `queue` and `account` must be user-supplied (DESIGN §7.5); mark `prepare_run_recipe` / `run_local_recipe` / `run_slurm_recipe` / `approve_composed_recipe` as inspect-before-execute power-user tools. Tests: MCP schema reflects new signatures.

15. **Documentation + agent-context refresh.** Update in the same branch:
    - `AGENTS.md` — add `bundles.py`, `staging.py`, `validate_run_recipe`, binding-grammar to Project Structure; note experiment loop in Prompt/MCP/Slurm; note staging preflight invariant.
    - `DESIGN.md` — update §6.2 (MCP tool surface list), §7.5 (preflight staging check by name), opening (family extensibility claim, with the `TASK_PARAMETERS` coupling called out honestly).
    - `CHANGELOG.md` — dated entry covering all of the above including the BC break and the two audience-targeted derivative docs.
    - `.codex/registry.md` — "Adding a Pipeline Family" walkthrough; link `_gatk.py`.
    - `.codex/tasks.md` — bindings/inputs split; `TASK_PARAMETERS` still present as known coupling; follow-up pointer.
    - `.codex/workflows.md` — workflows accept bindings via the symmetric shape.
    - `.codex/testing.md` — patterns for `$ref` resolution, staging findings, decline-to-bundles, empty-prompt advisory, availability reporting.
    - `.codex/code-review.md` — MCP-layer-branch-free checklist item.
    - `.codex/agent/{registry,task,workflow,test,code-review,architecture}.md` — mirror the above.
    - `docs/realtime_refactor_checklist.md` — tick closed items; archive superseded planning doc on completion.
    - `docs/mcp_showcase.md` — rewrite as the experiment loop; `prepare_run_recipe` moves to an Inspect-Before-Execute appendix.
    - `docs/tutorial_context.md` — typed-binding prompt templates; `$ref` cross-run reuse example.
    - Grep-sweep verification: `rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md` → zero stale references.

16. **Copy this file and `SCIENTIST_GUIDE.md`** into the project root at `/home/rmeht/Projects/flyteTest/`. Commit separately with a descriptive subject.

## Hard constraints (never violate)

- Do not modify frozen saved artifacts at retry/replay time (AGENTS.md).
- Do not submit a Slurm job without a frozen run record.
- Do not change `classify_slurm_failure()` semantics without a decision record.
- Do not silently rewrite the baseline; only change what this task requires.
- Preserve the M15 P2 approval gate: `requires_user_approval` must remain set for planner-composed novel DAGs; only registered single-entry targets via `run_task` / `run_workflow` bypass it.

## Pitfalls

- Don't reintroduce prose parsing in the decline-to-bundles router. `suggested_bundles` / `suggested_prior_runs` are structured queries, not keyword matches.
- Don't make `_validate_bundles()` a module-level call. Call-site validation only (`list_bundles`, `load_bundle`). Startup must succeed regardless of `data/` state.
- Don't introduce a parallel `environment_profiles.py` catalog. Environment metadata lives on `RegistryCompatibilityMetadata.execution_defaults`; bundles inherit from and override it.
- Don't keep `output_paths` as a transitional alias. The BC break covers it too.
- Don't expand `TASK_PARAMETERS` in this milestone if it can be avoided; the follow-up moves the whole table onto the registry.

## Verification commands (run before merge)

```
python -m compileall src/flytetest/
rg -n "_extract_prompt_paths|_extract_braker_workflow_inputs|_extract_protein_workflow_inputs|_classify_target|_extract_execution_profile|_extract_runtime_images" src/flytetest/   # zero hits
rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/                                                                                                                                      # zero old-shape hits
rg -n 'run_task\(|run_workflow\(|plan_typed_request\(|_extract_prompt_paths|_classify_target' docs/ .codex/ AGENTS.md CLAUDE.md DESIGN.md                                                            # zero stale refs
python -c "import flytetest.server"                                                                                                                                                                  # startup robust
pytest tests/                                                                                                                                                                                        # full suite green
```
