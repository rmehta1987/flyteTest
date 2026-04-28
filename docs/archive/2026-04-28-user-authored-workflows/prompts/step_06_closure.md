# Step 06 — Closure

Run all verification gates, update CHANGELOG.md, commit, and archive.

---

## Verification gates (all must pass)

### Syntax
```bash
python3 -m compileall \
    src/flytetest/mcp_tools.py \
    src/flytetest/workflows/variant_calling.py \
    src/flytetest/registry/_variant_calling.py
```

### Flat tool tests
```bash
PYTHONPATH=src python3 -m pytest \
    tests/test_mcp_tools.py::VcCustomFilterTests \
    tests/test_mcp_tools.py::VcApplyCustomFilterTests \
    -v
```

### Workflow + registry tests
```bash
PYTHONPATH=src python3 -m pytest \
    tests/test_variant_calling.py::ApplyCustomFilterWorkflowRegistryTests \
    -v
```

### Registry contract guards
```bash
PYTHONPATH=src python3 -m pytest \
    tests/test_registry.py \
    tests/test_registry_manifest_contract.py \
    -x -q
```

### Full suite
```bash
PYTHONPATH=src python3 -m pytest --ignore=tests/test_compatibility_exports.py -q
# Record the actual test count.
```

### Scope guard
```bash
git diff --name-only | grep -E \
    "planning\.py|mcp_contract\.py|bundles\.py|spec_executor\.py|planner_types\.py"
# Must return nothing.
```

---

## CHANGELOG.md entry

Add immediately below `## Unreleased`:

```markdown
### User-authored workflow composition (2026-04-28)

- [x] 2026-04-28 `mcp_tools.py`: added `vc_custom_filter` flat tool for
  `my_custom_filter` task (VariantCallSet binding, min_qual scalar, resource
  params for Slurm); added `vc_apply_custom_filter` flat tool for composed workflow.
- [x] 2026-04-28 `workflows/variant_calling.py`: added
  `apply_custom_filter` composed workflow — applies
  `my_custom_filter` to an existing VCF without re-running upstream GATK steps;
  on-ramp reference composition for user-authored task wiring.
- [x] 2026-04-28 `registry/_variant_calling.py`: added `RegistryEntry` for
  `apply_custom_filter` (`category="workflow"`,
  `pipeline_stage_order=23`, `accepted/produced=VariantCallSet`,
  `runtime_images={}`, `showcase_module="flytetest.workflows.variant_calling"`).
- [x] 2026-04-28 Tests: `VcCustomFilterTests`,
  `VcApplyCustomFilterTests` in `test_mcp_tools.py`;
  `ApplyCustomFilterWorkflowRegistryTests` in `test_variant_calling.py`.
- [x] 2026-04-28 `.codex/user_tasks.md`: linked real flat tools and composed
  workflow as callable on-ramp templates; updated "Wiring into a workflow" section.
```

---

## Commit

```bash
git add \
    src/flytetest/mcp_tools.py \
    src/flytetest/workflows/variant_calling.py \
    src/flytetest/registry/_variant_calling.py \
    tests/test_mcp_tools.py \
    tests/test_variant_calling.py \
    .codex/user_tasks.md \
    CHANGELOG.md

git commit -m "user-authored-workflows: flat tools + composed workflow on-ramp reference"
```

## Archive

```bash
git mv docs/2026-04-28-user-authored-workflows docs/archive/2026-04-28-user-authored-workflows
git commit -m "archive: user-authored-workflows milestone"
```
