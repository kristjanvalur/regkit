# Copilot Instructions for winregkit

## Project context
- `winregkit` is a small Python library around Windows Registry operations.
- Main implementation lives in `src/winregkit/`.
- Tests rely heavily on `tests/fakewinreg.py` to validate behavior on non-Windows and to compare against real `winreg` when available.

## Tech and tooling
- Python version target: **3.11+**.
- Packaging/build: `hatchling` (`pyproject.toml`).
- Environment/dependency workflow uses **uv**.
- Version management should use `uv version` (e.g. `uv version --bump patch`, `uv version 0.0.1rc1`) instead of manually editing `pyproject.toml`.
- Type checking uses **mypy strict mode** on `src/winregkit`.
- Linting/import order uses **ruff** with import sorting (`I`).

## Code style and implementation rules
- Keep changes minimal and focused; do not refactor unrelated code.
- Preserve existing API shape and naming unless explicitly asked.
- Prefer explicit type annotations that satisfy strict mypy.
- Follow existing patterns:
  - `Key` methods raise `KeyError` for missing values/keys where the library API currently does so.
  - Low-level backend exceptions (`FileNotFoundError`, `OSError`, `PermissionError`) are translated only where the current code already translates them.
- Keep compatibility with both real `winreg` and `tests.fakewinreg` behavior.
- Avoid platform-specific assumptions that would break tests on non-Windows.

## Testing expectations
- Run targeted tests first for touched behavior, then broader tests.
- Typical commands:
  - `uv sync --dev`
  - `pytest`
- If type-significant code is changed, also run:
  - `uv run mypy src/winregkit`

## File-specific guidance
- `src/winregkit/registry.py` is the core behavior surface; changes here should preserve context-manager and handle lifecycle semantics (`open`, `close`, `opened`, `create`, `delete`).
- `tests/fakewinreg.py` is a behavioral compatibility shim. If production behavior changes, update tests and shim only when required by the requested change.
- CLI (`src/winregkit/cli.py`) is intentionally minimal currently; do not expand it unless requested.

## When adding or changing code
- Add/adjust tests in `tests/` for any behavior change.
- Keep imports sorted and remove unused imports.
- Keep docstrings concise and consistent with existing style.
- Prefer straightforward implementations over abstractions.
- Update `CHANGELOG.md` for release-worthy changes (including `rc`/pre-release tags).
- Keep changelog entries concise and user-facing; avoid listing individual development bug-fix details.

## Things to double-check before finishing
- No accidental public API breaks in `winregkit.__init__` exports.
- Tests pass locally.
- New code passes strict typing.
- No unrelated formatting-only churn.