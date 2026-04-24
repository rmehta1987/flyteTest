Use this prompt when starting Step 01 or when handing it off to another session.

Model: Sonnet sufficient — pure additive type work with round-trip tests.

```text
You are starting Milestone A of the FLyteTest Phase 3 GATK4 germline variant
calling port. Work under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md  (hard constraints, core rules)
- /home/rmeht/Projects/flyteTest/DESIGN.md  (planner types, pipeline boundaries)
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/checklist.md
- /home/rmeht/Projects/flyteTest/docs/gatk_milestone_a/milestone_a_plan.md  (§6.1)

Context:

- This is Step 01 (Foundation). Depends on nothing — it is the first step.
- Blocks every subsequent step: registry entries and task signatures
  reference the three new planner types added here.

Key decisions already made (do not re-litigate):

- New types are planner-facing (inherit `PlannerSerializable`), not Flyte
  runtime assets; they live in `src/flytetest/planner_types.py`, not
  `src/flytetest/types/assets.py`.
- `AlignmentSet` holds filesystem paths, not Stargazer `cid` fields.
- `VariantCallSet` unifies GVCF and VCF under one dataclass, discriminated
  by a `variant_type` field ("gvcf" | "vcf"); this matches Stargazer's
  `Variants` class but path-based.
- `KnownSites` includes VQSR-facing fields (`training`, `truth`, `prior`,
  `vqsr_mode`) even though VQSR is out of scope — carrying them now avoids
  a compatibility break when Milestone B/C adds VariantRecalibrator.
- `ReferenceGenome` is reused verbatim from `planner_types.py`; no new
  reference-flavored type.

Task:

1. Add three frozen-slot dataclasses to `src/flytetest/planner_types.py`:
   `AlignmentSet`, `VariantCallSet`, `KnownSites`. Field list per
   `milestone_a_plan.md` §6.1 (copy verbatim). All inherit
   `PlannerSerializable`.

2. Extend `__all__` in `planner_types.py` to export the three new names.

3. Confirm `SerializableMixin` round-trip works automatically by running
   the existing planner-type round-trip test module; if the tests use an
   explicit type list, add the three new types to that list.

4. Add three round-trip tests (one per type) that construct an instance
   with every field populated and assert `from_dict(to_dict(x)) == x`.
   Also add one test constructing only required fields (paths) and
   asserting defaults land as expected.

Tests to add:

- `test_alignment_set_round_trips` — all fields set.
- `test_variant_call_set_round_trips_gvcf` + `_vcf` — variant_type
  discriminator behavior.
- `test_known_sites_round_trips_with_vqsr_fields` — carries training /
  truth / prior / vqsr_mode.
- `test_known_sites_defaults_minimal` — vcf_path + resource_name only.

Verification:

- `python -m compileall src/flytetest/planner_types.py`
- `pytest tests/test_planner_types.py -xvs` (or the file currently
  covering planner round-trips — confirm path by `rg "PlannerSerializable|ReferenceGenome" tests/`)

Commit message: "variant_calling: add AlignmentSet/VariantCallSet/KnownSites planner types".

Then mark Step 01 Complete in docs/gatk_milestone_a/checklist.md.

Add a CHANGELOG.md entry dated today under `## Unreleased`:

```
### GATK Milestone A Step 01 — Planner types for variant calling (YYYY-MM-DD)

- [x] YYYY-MM-DD added AlignmentSet, VariantCallSet, KnownSites planner
  dataclasses to src/flytetest/planner_types.py; round-trip coverage in
  tests/test_planner_types.py
```
```
