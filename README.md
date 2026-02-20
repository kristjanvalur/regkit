# winregkit

Helper library for Windows Registry operations.

## Features
- Easy-to-use API for reading and writing Windows Registry keys
- Python 3.11+
- Windows platform
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
from winregkit import current_user

# create/open for write (subkeys can be passed directly)
with current_user.create("Software", "MyApp") as key:
  key["name"] = "winregkit"
  key["enabled"] = 1

# open for read (same inline-subkey convenience)
with current_user.open("Software", "MyApp") as key:
  print(key["name"])
  print(key.get("missing", "default"))
```

`subkey(...)` is optional convenience for pre-building a path. You can either
chain with `subkey(...)` first, or pass subkeys directly to `open(...)` / `create(...)`.

### Preferred API style
- Use root factories (`current_user`, `local_machine`, etc.)
- Navigate with `subkey(...)` (optional)
- Open with `open(...)` or `create(...)` and a context manager
- Use dict-style value access (`key[name]`, `key[name] = value`)
- Use `value_get` / `value_set` only when explicit registry types are needed

## Development

- Install dev dependencies:
  ```sh
  uv sync --dev
  ```
- Run tests:
  ```sh
  uv run pytest
  ```

## License
MIT License. See `LICENSE` for details.

## Changelog
See `CHANGELOG.md` for release history and policy.
