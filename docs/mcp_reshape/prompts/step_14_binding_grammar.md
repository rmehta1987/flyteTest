Use this prompt when starting Step 14 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§7 — binding-value grammar)

Context:

- This is Step 14. Depends on Step 13 (typed resolver exceptions). Adds
  the `$ref` binding form so scientists can reference a prior run's output
  without copy-pasting paths.

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

Task:

1. Extend `src/flytetest/resolver.py::_materialize_bindings` to dispatch on
   form: raw / `$manifest` / `$ref`. The `$ref` form reads the durable asset
   index via `LocalManifestAssetResolver.resolve(..., durable_index=...)`
   (existing M20b plumbing).

2. Resolve each binding to a concrete planner dataclass instance; the
   concrete filesystem path is frozen into the plan (and later into
   `WorkflowSpec`).

3. Failure paths raise the typed exceptions from Step 13.

Tests to add (tests/test_resolver.py):

- Raw path form resolves unchanged.
- `$manifest` form resolves via the existing path.
- `$ref` form resolves via the durable index → concrete path.
- Unknown `$ref.run_id` raises `UnknownRunIdError`.
- `$ref` with bad `output_name` raises `UnknownOutputNameError` carrying
  the known-outputs list.
- Mixed-form call (raw + `$ref`) resolves all bindings correctly.

Verification:

- `python -m compileall src/flytetest/resolver.py`
- `pytest tests/test_resolver.py`

Commit message: "resolver: add $ref binding form for cross-run reuse".

Then mark Step 14 Complete in docs/mcp_reshape/checklist.md.
```
