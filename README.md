# winregkit

[![CI](https://github.com/kristjanvalur/pywinregkit/actions/workflows/ci.yml/badge.svg)](https://github.com/kristjanvalur/pywinregkit/actions/workflows/ci.yml)

A modern, pythonic interface to the Windows registry.

## Introduction

Python comes with `winreg` for registry operations, but it is a thin wrapper over
Win32 APIs and can be cumbersome for day-to-day usage.

`winregkit` provides a higher-level, object-oriented interface with simple tree
navigation, dict-like value access, and context-manager support.

## Features
- Easy-to-use API for reading and writing Windows Registry keys
- Python 3.11+
- Windows platform
- MIT License
- Managed and built with [uv](https://github.com/astral-sh/uv)


## Installation

```sh
pip install winregkit
```

Or the equivalent command in your preferred package manager.

## Usage

### Library
```python
from winregkit import current_user
import winreg


# open for read
with current_user.subkey("Software", "MyApp").open() as key:
    print(key["name"])
    print(key.get("missing", "default"))

# open for write (subkeys can be passed directly to open as a convenience)
with current_user.open("Software", "MyApp", write=True) as key:
    key["name"] = "winregkit"
    key["enabled"] = 1

# pathlib-style path concatenation is also supported via "/"
with (current_user / "Software" / "MyApp").open(write=True) as key:
    key["theme"] = "dark"

# create/open for write (create is shorthand for open(create=True, write=True))
with current_user.create("Software", "MyApp") as key:
    key["name"] = "winregkit"
    key["enabled"] = 1

# the Key object provides dict access and values can be iterated over:
with current_user.open("Software", "MyApp") as key:
    for name, value in key.items():
        print(name, value)

# the underlying type of a value can be retrieved, and a custom type can be
# set, overriding default conversions:
with current_user.open("Software", "MyApp", write=True) as key:
    value, value_type = key.get_typed("enabled")
    print(value, value_type)

    key.set_typed("payload", b"\x00\x01\x02", winreg.REG_BINARY)

# existence checks are available on keys:
app_key = current_user.subkey("Software", "MyApp")
print(app_key.exists())

```

`subkey(...)` is optional convenience for pre-building a path. You can either
chain with `subkey(...)` first, or pass subkeys directly to `open(...)` / `create(...)`.

### Typical workflow
- Use root factories (`current_user`, `local_machine`, etc.)
- Navigate with `subkey(...)` (optional)
- Open with `open(...)` or `create(...)` and a context manager
- Use dict-style value access (`key[name]`, `key[name] = value`)
- Use `get_typed` / `set_typed` only when explicit registry types are needed

### Using registry paths
`Key` supports constructing and round-tripping full registry paths.

```python
from winregkit import Key

# Construct from explicit path parts
key = Key.from_parts(("HKCU", "Software", "MyApp"))

# Construct from a full path string (either HKCU or HKEY_CURRENT_USER style)
same_key = Key.from_path(r"HKEY_CURRENT_USER\Software\MyApp")

# Read parts back (root token + subkey parts)
assert key.parts == ("HKCU", "Software", "MyApp")

# name is the final lexical segment
assert key.name == "MyApp"

# parents() returns lexical ancestors from nearest parent upward
assert [ancestor.name for ancestor in key.parents()] == ["Software", "HKCU"]
```

Use `from_parts(...)` when you already have tokenized components, and
`from_path(...)` when parsing user-provided registry path strings.

### `Key` methods at a glance
- `subkey(*parts)`: build a child key path without opening it
- `open(...)`: return a new opened key for read/write access
- `create(*parts)`: shorthand for creating/opening a key for writing
- `exists()`: check whether a key exists
- `walk(...)`: traverse a key tree, yielding `(key, subkey_names, value_names)` (similar to `os.walk()`)
- `keys()`, `values()`, `items()`: iterate value names, values, or `(name, value)` pairs
- `name`: final lexical path segment for this key
- `parts`: tuple of key path components, including root token when present
- `parent`: lexical parent key (or `None` at registry root)
- `parents()`: tuple of lexical ancestors from immediate parent up to root
- `get(name, ...)`: read a value with fallback default
- `get_typed(...)` / `set_typed(...)`: read/write values with explicit registry type
- `value_del(name)` or `del key[name]`: delete a value
- `delete(...)`: delete a key (optionally recursively)
- `as_dict()` / `from_dict(data)`: export/import a subtree structure

### Default value name
The registry's default (unnamed) value is represented by the empty string (`""`).

- Iteration methods (`items()`, `items_typed()`, `keys()`) return `""` for the default value name.
- Set/delete helpers also accept `None` as an equivalent.

## Development

This project uses the [uv](https://docs.astral.sh/uv/) package manager.

- Install uv, e.g. using `pip install uv`

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
