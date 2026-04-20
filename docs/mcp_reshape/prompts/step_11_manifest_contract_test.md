Use this prompt when starting Step 11 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3b — registry-wide contract test)

Context:

- This is Step 11. One registry-wide test asserts every showcased entry's
  declared output names are members of the task module's `MANIFEST_OUTPUT_KEYS`.

Task:

1. Create `tests/test_registry_manifest_contract.py`:

   ```python
   import importlib

   from flytetest.registry import REGISTRY_ENTRIES


   def test_every_declared_output_is_a_declared_manifest_key():
       for entry in REGISTRY_ENTRIES:
           if not entry.showcase_module:
               continue
           module = importlib.import_module(entry.showcase_module)
           manifest_keys = set(getattr(module, "MANIFEST_OUTPUT_KEYS", ()))
           declared = {f.name for f in entry.outputs}
           missing = declared - manifest_keys
           assert not missing, (
               f"{entry.name}: declared outputs {sorted(missing)} are not "
               f"listed in {entry.showcase_module}.MANIFEST_OUTPUT_KEYS"
           )
   ```

2. Extras in `MANIFEST_OUTPUT_KEYS` that aren't declared on the registry
   entry are allowed (internal audit fields). Missing declared names fail
   the test.

Tests:

- This IS the test. Run it against the aligned state from Steps 09-10 —
  should pass.

Verification:

- `pytest tests/test_registry_manifest_contract.py -v`
- The test must fail if any showcased entry's output is missing from its
  task module's `MANIFEST_OUTPUT_KEYS`. Verify by temporarily adding a fake
  `InterfaceField("bogus", "str", "nope")` to one entry and confirming the
  test fails.

Commit message: "tests: add registry-manifest contract test for every showcased entry".

Then mark Step 11 Complete in docs/mcp_reshape/checklist.md.
```
