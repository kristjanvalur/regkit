# Copilot Instructions for winregkit

## Project Overview
winregkit is a Python library that provides a helper API for Windows Registry operations. It wraps the standard `winreg` module with a more user-friendly interface, including a `Key` class for registry key manipulation. The project supports Python 3.11+ and is licensed under MIT.

Key features:
- Easy-to-use API for reading/writing registry keys
- Command-line interface (CLI) - currently a stub
- Cross-platform testing support via fakewinreg mock

## Project Structure
- `src/winregkit/`: Main package
  - `__init__.py`: Exports `Key` class and root key factories
  - `registry.py`: Core `Key` class implementation with registry operations
  - `cli.py`: Command-line interface (not yet implemented)
- `tests/`: Test suite
  - `fakewinreg.py`: Mock implementation of `winreg` for testing on non-Windows systems
  - Various test files for unit testing
- `pyproject.toml`: Project configuration (dependencies, build, tools)
- `uv.lock`: Dependency lock file (managed by uv)

## Dependencies and Tools
- **Dependency Management**: uv (https://github.com/astral-sh/uv)
  - Use `uv sync` to install dependencies
  - Use `uv sync --dev` for development dependencies
- **Linting/Formatting**: ruff
  - Line length: 120 characters
  - Target Python version: 3.11
  - Checks import order
- **Type Checking**: mypy
  - Strict mode enabled
  - Python version: 3.11
- **Testing**: pytest
- **Build System**: hatchling

## Coding Standards
- **Python Version**: 3.11 minimum
- **Type Hints**: Required, enforced by mypy strict mode
- **Imports**: Use absolute imports, order checked by ruff
- **Line Length**: 120 characters
- **Path Handling**: Use `ntpath` for registry key paths (Windows-style)
- **Error Handling**: Proper exception handling for registry operations

## Key Classes and Concepts
- **`Key` Class**: Main abstraction for registry keys
  - Factory methods for root keys: `classes_root()`, `current_user()`, `local_machine()`, etc.
  - Context manager support for automatic closing
  - Methods for opening, creating, deleting keys and values
- **Root Keys**: Standard Windows registry hives (HKEY_*)
- **Fake Winreg**: In-memory mock for testing, simulates registry behavior

## Testing Strategy
- Unit tests use `fakewinreg` to mock Windows registry on non-Windows platforms
- Tests are located in `tests/` directory
- Run tests with `pytest`
- conftest.py adds src to Python path for testing

## Development Workflow
1. Install dependencies: `uv sync --dev`
2. Run linting/formatting: `uvx ruff check src/winregkit; uvx ruff format src/winregkit`
3. Type check: `uvx mypy src/winregkit`
4. Run tests: `pytest`
5. Build: Use hatchling (configured in pyproject.toml)

## CLI Status
The CLI is currently not implemented (cli.py contains only a placeholder). The entry point is defined as `registry-cli = "registry_package.cli:main"` in pyproject.toml, but the module name appears to be a mismatch (should be `winregkit.cli:main`).

## Architecture Notes
- Pure Python, no C extensions
- Depends on standard `winreg` module (Windows only at runtime)
- Uses `ntpath` for path operations to match Windows registry semantics
- Thread-safe key handles with proper cleanup
- Type-safe with extensive use of type hints

## Common Patterns
- Use context managers for key operations: `with key.open() as h:`
- Handle registry exceptions (e.g., FileNotFoundError for missing keys)
- Use `Key` factory methods for root keys instead of direct winreg constants
- Test with fakewinreg to ensure cross-platform compatibility

## Potential Improvements
- Implement the CLI functionality
- Add more comprehensive error handling and logging
- Expand test coverage
- Add documentation strings and examples
- Fix CLI entry point module name in pyproject.toml</content>
<parameter name="filePath">e:\git\pywinregkit\copilot-instructions.md