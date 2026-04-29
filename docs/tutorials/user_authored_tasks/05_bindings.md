# Chapter 5: The binding contract

One pitfall trips up almost everyone who writes their first task: **parameter
name collisions with planner-type fields.** It produces silent shadowing, a
clean-looking dry run, and then a baffling failure at execution time. This
chapter exists so you can skip the bug.

## The rule

If your task or workflow declares `accepted_planner_types=(X,)`, then your
task / workflow parameter names must **not** match any field name on `X`.

When the planner resolves a typed binding, it looks at the planner-type
dataclass and routes each field into the task's `inputs` map. The resolver
also classifies any task parameter whose name matches a binding inner-key as
"already covered by the typed binding" and skips it during scalar input
validation. If you accidentally name a parameter the same as a planner field,
the two checks disagree: dry-run validation sees the parameter as covered,
the local executor still expects it in `inputs`, and the run dies with
confusing `Unknown scalar inputs` / `Missing required workflow inputs`
errors.

The canonical reference for this rule lives at
`.codex/user_tasks.md:57-91` (section "Naming-collision gotcha"). Read it
once; it is the source of truth.

## Concrete example — wrong (do not copy)

Hypothetical task that *looks* fine and breaks at run time:

```python
# Hypothetical — DO NOT use this pattern.
# accepted_planner_types=("VariantCallSet",) on the registry side.
@variant_calling_env.task
def my_broken_filter(vcf_path: File, min_qual: float = 30.0) -> File:
    ...
```

Why it breaks: `VariantCallSet` is defined at
`src/flytetest/planner_types.py:238` with a `vcf_path` field on line 246.
The parameter name `vcf_path` collides with that field. The resolver
shadows the parameter, the dry run reports success, and the actual run
fails because the task signature expects a populated `vcf_path` while the
local executor was told that key was already covered by the typed binding.

Other collisions on the same dataclass to watch for: `variant_type`,
`caller`, `sample_ids`, `reference_fasta_path`, `vcf_index_path`, `build`,
`cohort_id`. Any field on `VariantCallSet` is off-limits as a task
parameter name when you accept that type.

## Concrete example — fixed

The shipped task uses `input_vcf` instead. From
`src/flytetest/tasks/variant_calling.py:1278-1282`:

```python
@variant_calling_env.task
def my_custom_filter(
    input_vcf: File,
    min_qual: float = 30.0,
) -> File:
```

The matching workflow uses the same name, from
`src/flytetest/workflows/variant_calling.py:645-649`:

```python
@variant_calling_env.task
def apply_custom_filter(
    input_vcf: File,
    min_qual: float = 30.0,
) -> File:
```

The flat-tool layer keeps the same convention; the planner-field name
`vcf_path` only appears inside the binding dict, not in the function
signature. From `.codex/user_tasks.md:83-87`:

```python
def vc_apply_custom_filter(input_vcf: str, min_qual: float = 30.0, ...):
    return _run_workflow(
        workflow_name="apply_custom_filter",
        bindings={"VariantCallSet": {"vcf_path": input_vcf}},  # planner field
        inputs={"input_vcf": input_vcf, "min_qual": min_qual}, # function param
        ...
    )
```

With `input_vcf` the resolver populates the parameter from the typed
asset's `vcf_path` field, the executor sees the parameter present in
`inputs`, and the two validation paths agree. No shadowing.

## Debugging when it does happen

If you hit `PlannerResolutionError`, an `Unknown scalar inputs` message,
or you see `None` arrive at runtime where a path was expected:

1. Open your registry entry. Note every name in `accepted_planner_types`.
2. Open `src/flytetest/planner_types.py` and list the fields on each of
   those dataclasses.
3. Cross-check against your task / workflow signature. Any parameter name
   that matches a field name is the bug.
4. Rename the parameter (see the next section for the convention) and
   update every call-site (task signature, workflow signature, flat tool,
   tests, registry `inputs=` interface description).

## The shortcut: name parameters by role, not by resolved path

Convention across the codebase: name parameters by the **role** the value
plays in the task body, not by its resolved-path interpretation.

- Use `input_vcf`, `joint_vcf`, `vcf_in` — not `vcf_path`.
- Use `bam`, `aligned_bam`, `input_bam` — not `bam_path`.
- Use `ref` or `reference_fasta` only after checking the planner type
  fields you accept.

The planner already provides paths; you do not need `_path` in the
parameter name to remember that. The shorter, role-based name is also
what every existing task in `src/flytetest/tasks/` uses.

## Forward pointer

Chapter 6 ([06_registry.md](06_registry.md)) walks through every
load-bearing field on `RegistryEntry` and `RegistryCompatibilityMetadata`,
including where `accepted_planner_types` is declared and how it drives the
binding resolution covered above.

---

[← Prev: Manifests and outputs](04_manifests.md) · [Next: Registry entry deep-dive →](06_registry.md)
