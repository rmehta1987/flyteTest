Use this prompt when starting Step 14 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§7 — binding-value grammar)

Context:

- This is Step 14. Depends on Step 13 (typed resolver exceptions +
  `BindingTypeMismatchError` appended to errors.py). Adds the `$ref` binding
  form so scientists can reference a prior run's output without copy-pasting
  paths, AND adds the §7 type-compatibility check that rejects a
  `$ref` / `$manifest` whose producing entry declared a different planner
  type than the binding key.

Key decisions already made (do not re-litigate):

- Three mutually-exclusive forms inside each binding dict:
  - Raw path (existing): `{"fasta_path": "/abs/path.fa"}` — dispatched by
    absence of `$ref` / `$manifest`.
  - `$manifest` (existing): `{"$manifest": "...run_manifest.json",
    "output_name": "..."}`.
  - `$ref` (new): `{"$ref": {"run_id": "...", "output_name": "..."}}`.
- All three lower to the same concrete planner dataclass with a concrete
  filesystem path, which is what gets frozen into `WorkflowSpec` (not the
  pointer). The pointer indirection is convenience, not reproducibility.
- Mixing forms is allowed within one call: a raw-path `ReferenceGenome` and
  a `$ref`-based `AnnotationGff` can coexist.
- Type-compatibility check is EXACT-NAME match only (§7). Biology types are
  flat — no subtype hierarchy; `ReadSet` is not a supertype of `FastqSet`.
- Raw-path form is NOT type-checked. The scientist asking "use this file I
  have on disk" is asserting the type; raw-path is the deliberate escape
  hatch for intentional reinterpretation.

Task:

1. Extend `src/flytetest/resolver.py::_materialize_bindings` to dispatch on
   form: raw / `$manifest` / `$ref`. The `$ref` form reads the durable asset
   index via `LocalManifestAssetResolver.resolve(..., durable_index=...)`
   (existing M20b plumbing).

2. Resolve each binding to a concrete planner dataclass instance; the
   concrete filesystem path is frozen into the plan (and later into
   `WorkflowSpec`).

3. Implement the §7 type-compatibility check, run after path resolution
   and before `PlannerSerializable` construction, for BOTH `$ref` and
   `$manifest` forms:
   - `$ref`: compare the binding key (e.g. `"ReadSet"`) against
     `DurableAssetRef.produced_type` (populated at write time from the
     producing entry's `produced_planner_types`). On mismatch, raise
     `BindingTypeMismatchError(binding_key, resolved_type=produced_type,
     source=run_id)`.
   - `$manifest`: read the manifest's top-level `stage` key, look up the
     entry via `registry.get_entry(stage)`, read
     `entry.compatibility.produced_planner_types`. If the binding key is
     not an exact member, raise `BindingTypeMismatchError(binding_key,
     resolved_type=<first-of-produced_planner_types-or-per-output-type>,
     source=<manifest_path>)`. If the manifest carries per-output type
     info, prefer it; otherwise require tuple membership.
   - Raw-path form is not type-checked — documented as the deliberate
     escape hatch.

4. Failure paths raise the typed exceptions from Step 13, including the
   new `BindingTypeMismatchError`. Do NOT catch here — Step 19 translates.

Tests to add (tests/test_resolver.py):

- Raw path form resolves unchanged.
- `$manifest` form resolves via the existing path.
- `$ref` form resolves via the durable index → concrete path.
- Unknown `$ref.run_id` raises `UnknownRunIdError`.
- `$ref` with bad `output_name` raises `UnknownOutputNameError` carrying
  the known-outputs list.
- Mixed-form call (raw + `$ref`) resolves all bindings correctly.
- `$ref` whose producing entry declares a different `produced_type` than
  the binding key raises `BindingTypeMismatchError` with
  `binding_key`, `resolved_type`, and `source=run_id` populated.
- `$manifest` whose producing entry's `produced_planner_types` does not
  contain the binding key raises `BindingTypeMismatchError` with
  `source=<manifest_path>` populated.
- Raw-path form with a "wrong" biological type on disk does NOT raise
  — raw path is the escape hatch.

Verification:

- `python -m compileall src/flytetest/resolver.py`
- `pytest tests/test_resolver.py`

Commit message: "resolver: add $ref binding form for cross-run reuse".

Then mark Step 14 Complete in docs/mcp_reshape/checklist.md.
```
