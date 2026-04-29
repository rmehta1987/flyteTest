# Chapter 10: Verification and PR checklist

Run these in order before pushing. Stop on the first failure and fix it before
moving on — each step rules out a different class of breakage, so a green later
step does not redeem a red earlier one.

## Step 1 — Compile

```
python3 -m compileall src/flytetest tests
```

Expected: no errors. If it fails, you have a syntax error or an import-time
bug; check `git diff --stat src/` to see which file you touched.

## Step 2 — Targeted unit tests

```
PYTHONPATH=src python3 -m pytest -k "<your task name pattern>" -q
```

Replace `<your task name pattern>` with what matches your new test classes.
For the on-ramp reference (`my_custom_filter` + `apply_custom_filter`):

```
PYTHONPATH=src python3 -m pytest -k "MyCustomFilter or apply_custom_filter" -q
```

## Step 3 — Full test suite

When the targeted run is green, run everything:

```
PYTHONPATH=src python3 -m pytest tests/ -q
```

A failure here that wasn't in your targeted set usually means a registry
contract test or a manifest-keys contract test caught a missing edit
elsewhere. See [Chapter 4](04_manifests.md) and [Chapter 6](06_registry.md).

## Step 4 — Registry smoke

```
PYTHONPATH=src python3 -c "from flytetest.registry import REGISTRY_ENTRIES; \
  names = sorted(e.name for e in REGISTRY_ENTRIES); \
  assert '<your_task_name>' in names; \
  print('OK', '<your_task_name>')"
```

Confirms the registry actually picks your new entry up at import. A silent
typo in the family `__init__.py` re-export would fail here.

## Step 5 — MCP smoke

If you added a flat tool in `src/flytetest/mcp_tools.py`:

```
PYTHONPATH=src python3 -c "from flytetest.mcp_tools import <vc_your_tool>; \
  assert <vc_your_tool>.__doc__"
```

The docstring assert is deliberate — flat-tool docstrings are the only prose
an MCP client sees, so an empty docstring is a contract bug.

## Step 6 — Git-diff self-review

Open `git diff` and walk the checklist:

- [ ] `CHANGELOG.md` has a dated entry under today's section in `## Unreleased`
- [ ] `MANIFEST_OUTPUT_KEYS` includes any new output keys your task produces
- [ ] `TASK_PARAMETERS` in `src/flytetest/server.py` has an entry if your task has scalar params (workflows do not need this — see [Chapter 9](09_mcp_exposure.md))
- [ ] Registry entry has correct `accepted_planner_types` and `produced_planner_types`
- [ ] No emojis introduced in source files (project convention)
- [ ] No unrelated edits in `git diff` — preserve user changes outside your scope

## Step 7 — Open the PR

```
git push -u origin <branch>
gh pr create --title "<task>: <short description>" --body "<summary + test plan>"
```

Keep the title under 70 characters. Put detail — what changed, why, and how
you tested it — in the body. Reference the milestone doc folder if the work
came from one.

## Done

When all six pre-flight steps pass and the diff is clean, your task is ready
for review. The reviewer's job is to confirm the contracts you already
checked above; they should not be the first run of `pytest -q`.
