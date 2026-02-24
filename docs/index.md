# regkit

A modern, pythonic interface to the Windows registry.

## Highlights

- Object-oriented key navigation and lifecycle management.
- Dict-style value access.
- Typed value helpers when explicit registry types are needed.
- Compatibility with real `winreg` and a fake backend for testing.

## Quick start

```python
from regkit import current_user

with current_user.open("Software", "MyApp", write=True) as key:
    key["name"] = "regkit"
    key["enabled"] = 1

with current_user.open("Software", "MyApp") as key:
    print(key["name"])
```

## API docs

See the API Reference page for docstring-driven documentation.