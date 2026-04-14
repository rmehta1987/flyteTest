# CLAUDE.md

@AGENTS.md

## Specialist guides — read before working in that area

| Area | Guide |
|---|---|
| Code documentation and docstrings | `.codex/documentation.md`, `.codex/comments.md` |
| Testing and validation | `.codex/testing.md` |
| Task modules (`src/flytetest/tasks/`) | `.codex/tasks.md` |
| Workflow modules (`src/flytetest/workflows/`) | `.codex/workflows.md` |
| Code review | `.codex/code-review.md` |
| Architecture decisions | `.codex/agent/architecture.md` |
| Specialist role prompts | `.codex/agent/task.md`, `.codex/agent/workflow.md`, `.codex/agent/test.md`, `.codex/agent/code-review.md` |

## Claude Code Efficiency

To minimize rereading, prefer targeted inspection after the first full read.
If a file has already been read and has not changed, use `rg -n` to locate the
relevant lines, then inspect only a narrow range with `sed -n` or
`nl -ba ... | sed -n`.

Before rereading an unchanged file, check whether it changed with
`git status --short` or `git diff --name-only`.

Reread the full file only when local context is insufficient, the file changed,
or the task depends on the file's overall structure.
