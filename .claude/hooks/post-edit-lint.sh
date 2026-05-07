#!/bin/bash
# After Edit/Write to a Python file, run `ruff check --fix` on it.
# Quiet on success; surfaces ruff errors to stderr.
# Skips silently if ruff is not installed (no blocking).

INPUT=$(cat)

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

TOOL=$(echo "$INPUT" | jq -r '.tool_name')
if [ "$TOOL" != "Edit" ] && [ "$TOOL" != "Write" ]; then
  exit 0
fi

FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [ -z "$FILE" ]; then
  exit 0
fi

# Only lint Python files.
if [[ "$FILE" != *.py ]]; then
  exit 0
fi

# Resolve to a path that exists.
if [ ! -f "$FILE" ]; then
  exit 0
fi

# Prefer project-venv ruff; fall back to system ruff; skip if neither.
RUFF=""
if [ -n "$CLAUDE_PROJECT_DIR" ] && [ -x "$CLAUDE_PROJECT_DIR/.venv/bin/ruff" ]; then
  RUFF="$CLAUDE_PROJECT_DIR/.venv/bin/ruff"
elif command -v ruff >/dev/null 2>&1; then
  RUFF="ruff"
else
  exit 0
fi

# Run ruff check --fix; suppress success output, surface errors.
if ! "$RUFF" check --fix "$FILE" >/dev/null 2>&1; then
  echo "ruff found issues in $FILE; run '$RUFF check $FILE' for details" >&2
fi

exit 0
