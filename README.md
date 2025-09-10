# winregkit

Helper library for Windows Registry operations.

## Features
- Easy-to-use API for reading and writing Windows Registry keys
- Command-line interface (CLI)
- Python 3.11+
- MIT License
- Managed and built with [uv](https://github.com/astral-sh/uv)


## Installation

1. Install [uv](https://github.com/astral-sh/uv):
   ```sh
   pip install uv
   ```
2. Sync project dependencies:
   ```sh
   uv sync
   ```

## Usage

### Library
```python
from winregkit import registry
# ... use registry API ...
```

### CLI
```sh
uvx registry-cli --help
```

## Development

- Install dev dependencies:
  ```sh
  uv sync --dev
  ```
- Run tests:
  ```sh
  pytest
  ```

## Usage

### Library
```python
from winregkit import registry
# ... use registry API ...
```

### CLI
```sh
uv pip install .
registry-cli --help
```

## Development
- Run tests:
  ```sh
  uv pip install -e .[dev]
  pytest
  ```

## License
MIT License. See `LICENSE` for details.
