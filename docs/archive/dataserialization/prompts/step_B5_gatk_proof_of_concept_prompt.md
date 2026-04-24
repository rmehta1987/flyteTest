Use this prompt when starting the Step B5 GATK proof of concept slice
or when handing it off to another session.

```text
You are finishing Track B of the FLyteTest registry restructure under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/checklist.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/serialization_registry_restructure_plan.md

Context:

- This is Step B5 — the proof of concept. B3+B4 must be complete.
- This step demonstrates that the new structure works: adding a new pipeline
  family requires creating one file and adding one import line.
- The GATK entry is catalog-only — it does NOT have a handler, planning
  coverage, or execution support yet.

Task:

1. Create `src/flytetest/registry/_gatk.py`:
   - Define `GATK_ENTRIES: tuple[RegistryEntry, ...]` with one entry:
     `gatk_haplotype_caller` (category="workflow").
   - Use realistic metadata: pipeline_family="variant_calling",
     pipeline_stage_order=3, plausible resource defaults.
   - Set `showcase_module=""` — no handler yet, not on MCP surface.
   - Use the Stargazer reference project at `/home/rmeht/Projects/stargazer/`
     for realistic GATK4 input/output signatures if available. Otherwise use
     plausible placeholders.

2. In `src/flytetest/registry/__init__.py`:
   - Add one import: `from flytetest.registry._gatk import GATK_ENTRIES`
   - Add `GATK_ENTRIES` to the `REGISTRY_ENTRIES` concatenation.

3. Verify the new entry is visible:
   ```python
   python3 -c "
   from flytetest.registry import REGISTRY_ENTRIES, list_entries, get_pipeline_stages
   print(f'{len(REGISTRY_ENTRIES)} entries')
   gatk = [e for e in REGISTRY_ENTRIES if e.name == 'gatk_haplotype_caller']
   assert len(gatk) == 1, 'GATK entry not found'
   stages = get_pipeline_stages('variant_calling')
   assert len(stages) >= 1, 'No variant_calling stages'
   print(f'GATK entry visible, {len(stages)} variant_calling stage(s)')
   "
   ```

4. Verify the GATK entry does NOT appear in MCP showcase targets (since
   showcase_module is empty):
   ```python
   python3 -c "
   from flytetest.mcp_contract import SUPPORTED_TARGET_NAMES
   assert 'gatk_haplotype_caller' not in SUPPORTED_TARGET_NAMES
   print('GATK correctly excluded from MCP surface')
   "
   ```

5. Run the full test suite:
   `python3 -m unittest discover -s tests -v`

6. Update `CHANGELOG.md` and `docs/dataserialization/checklist.md`.

Important constraints:

- Setting showcase_module alone is NOT sufficient to make a workflow fully
  MCP-runnable. Do not set it for the GATK entry.
- This entry is a placeholder for future GATK work — keep it realistic but
  do not implement the actual workflow.
- The total entry count will now be 74 (73 existing + 1 GATK).

Validation:

1. `python3 -m compileall src/flytetest/` — no import errors
2. `python3 -m unittest discover -s tests` — full suite passes
3. `python3 -c "from flytetest.registry import REGISTRY_ENTRIES; print(len(REGISTRY_ENTRIES))"` — 74

Report back with:

- checklist items completed
- files created and modified
- entry count before and after
- confirmation GATK entry is in catalog but not on MCP surface
- validation run summary
```
