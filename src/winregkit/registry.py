"""helper classes for registry operations"""

from __future__ import annotations

import ntpath
import winreg
from functools import total_ordering
from typing import Any, Callable, Iterator, Optional, Sequence, Tuple, Union, cast

from typing_extensions import TypeAlias

HKeyTypeAlias: TypeAlias = Union[winreg.HKEYType, int]


# map the winreg root key constants to their names
root_keys: dict[int, str] = {}
for key, val in getattr(winreg, "__dict__", {}).items():
    if key.startswith("HKEY_"):
        root_keys[val] = key


def handle_to_str(handle: int) -> str:
    """Converts a handle to a string"""
    try:
        return root_keys[handle]
    except KeyError:
        return repr(handle)


def join_names(*names: str) -> str:
    """Joins the names together, removing any empty strings"""
    return ntpath.join(*names)


@total_ordering
class Key:
    """A key in the registry.

    Usage style:
    - Use root factories (`current_user`, `local_machine`, ...)
    - Navigate with `subkey(...)`
    - Open with `open(...)` or `create(...)` in a context manager
    - Read/write values via dict-style access (`key[name]`)
    """

    _ROOT_HANDLE_NAMES: dict[str, str] = {
        "HKEY_CLASSES_ROOT": "HKEY_CLASSES_ROOT",
        "HKCR": "HKEY_CLASSES_ROOT",
        "HKEY_CURRENT_USER": "HKEY_CURRENT_USER",
        "HKCU": "HKEY_CURRENT_USER",
        "HKEY_LOCAL_MACHINE": "HKEY_LOCAL_MACHINE",
        "HKLM": "HKEY_LOCAL_MACHINE",
        "HKEY_USERS": "HKEY_USERS",
        "HKU": "HKEY_USERS",
        "HKEY_CURRENT_CONFIG": "HKEY_CURRENT_CONFIG",
        "HKCC": "HKEY_CURRENT_CONFIG",
    }

    _parent: Key | int
    _name: str
    _handle: HKeyTypeAlias | None

    @classmethod
    def _canonical_root_name_for_handle(cls, handle: int) -> str:
        for root_name in set(cls._ROOT_HANDLE_NAMES.values()):
            if getattr(winreg, root_name, None) == handle:
                return root_name
        return handle_to_str(handle)

    @classmethod
    def _create_rooted_key(cls, root: int, *subkeys: str, root_name: str) -> Key:
        """Creates a key object for a root key"""
        root_key = cls(root, root_name)
        if not subkeys:
            return root_key
        return root_key.subkey(*subkeys)

    @classmethod
    def classes_root(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_CLASSES_ROOT"""
        return cls._create_rooted_key(winreg.HKEY_CLASSES_ROOT, *subkeys, root_name="HKEY_CLASSES_ROOT")

    @classmethod
    def current_user(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_CURRENT_USER"""
        return cls._create_rooted_key(winreg.HKEY_CURRENT_USER, *subkeys, root_name="HKEY_CURRENT_USER")

    @classmethod
    def local_machine(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_LOCAL_MACHINE"""
        return cls._create_rooted_key(winreg.HKEY_LOCAL_MACHINE, *subkeys, root_name="HKEY_LOCAL_MACHINE")

    @classmethod
    def users(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_USERS"""
        return cls._create_rooted_key(winreg.HKEY_USERS, *subkeys, root_name="HKEY_USERS")

    @classmethod
    def current_config(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_CURRENT_CONFIG"""
        return cls._create_rooted_key(winreg.HKEY_CURRENT_CONFIG, *subkeys, root_name="HKEY_CURRENT_CONFIG")

    @classmethod
    def from_parts(cls, parts: Sequence[str]) -> Key:
        """Creates a Key object from path parts.

        The first item must be a registry root token (for example `HKCU` or
        `HKEY_CURRENT_USER`). Remaining items are subkey path components.
        """
        if not parts:
            raise ValueError("parts cannot be empty")

        root_token = str(parts[0])
        if not root_token:
            raise ValueError("root token cannot be empty")

        token_upper = root_token.upper()
        try:
            root_handle_name = cls._ROOT_HANDLE_NAMES[token_upper]
        except KeyError as e:
            raise ValueError(f"Unknown registry root: {parts[0]!r}") from e

        root_handle = cast(int, getattr(winreg, root_handle_name))
        subkeys = tuple(str(part) for part in parts[1:])
        return cls._create_rooted_key(root_handle, *subkeys, root_name=token_upper)

    @classmethod
    def from_path(cls, path: str) -> Key:
        """Creates a Key object from a full registry path.

        Examples:
        - HKEY_CURRENT_USER\\Software\\MyApp
        - HKCU\\Software\\MyApp
        """
        if not path:
            raise ValueError("Path cannot be empty")

        normalized = path.strip().replace("/", "\\")
        parts = [p for p in normalized.split("\\") if p]
        if not parts:
            raise ValueError("Path cannot be empty")

        return cls.from_parts(parts)

    @staticmethod
    def _split_subkey_parts(name: str) -> tuple[str, ...]:
        return tuple(part for part in name.replace("/", "\\").split("\\") if part)

    def __init__(
        self,
        parent: Key | int,
        *names: str,
    ) -> None:
        """Create a new key object.  The key is not opened or created."""
        self._parent = parent
        if any(not n for n in names):
            raise ValueError("Key names cannot be empty")
        self._name = ntpath.join(*names) if names else (handle_to_str(parent) if not isinstance(parent, Key) else "")
        self._handle: Optional[HKeyTypeAlias] = parent if not isinstance(parent, Key) else None

    @property
    def name(self) -> str:
        """Returns the final lexical path part for this key."""
        parts = self._split_subkey_parts(self._name)
        if not parts:
            return ""
        return parts[-1]

    def __del__(self) -> None:
        """Destructor to ensure the key is closed"""
        self.close()

    def _hkey_name(self) -> Tuple[Any, str]:
        """returns a handle and name for the key.  Used internally."""
        if isinstance(self._parent, Key):
            if self._parent.is_open():
                return self._parent._handle, self._name
            h, n = self._parent._hkey_name()
            return h, join_names(n, self._name)
        return self._parent, self._name

    def _hkey_fullname(self) -> Tuple[Any, str]:
        """returns a top level handle and full name for the key.  Used internally."""
        if isinstance(self._parent, Key):
            h, n = self._parent._hkey_fullname()
            return h, join_names(n, self._name)
        return self._parent, self._name

    def path(self) -> str:
        """Returns the full registry path for this key."""
        _, name = self._hkey_fullname()
        return name

    def canonical_path(self) -> str:
        """Returns the canonical full registry path for this key."""
        handle, name = self._hkey_fullname()
        parts = list(self._split_subkey_parts(name))
        if parts:
            parts = parts[1:]
        root_name = self._canonical_root_name_for_handle(cast(int, handle))
        return "\\".join((root_name, *parts)) if parts else root_name

    def canonical_parts(self) -> tuple[str, ...]:
        """Returns canonical path parts for this key."""
        return self._split_subkey_parts(self.canonical_path())

    def __str__(self) -> str:
        """Returns the full registry path for this key."""
        return self.path()

    def __repr__(self) -> str:
        """Returns a string representation of the key"""
        h, n = self._hkey_fullname()
        state = "open" if self.is_open() else "closed"
        return f"Key<{handle_to_str(h)}:{n!r} {state}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Key):
            return NotImplemented
        return self.canonical_path().casefold() == other.canonical_path().casefold()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Key):
            return NotImplemented
        return self.canonical_path().casefold() < other.canonical_path().casefold()

    def __hash__(self) -> int:
        return hash(self.canonical_path().casefold())

    def open_handle(
        self,
        create: bool = False,
        write: bool = False,
    ) -> None:
        """Opens this key in-place.

        This is the low-level in-place open primitive used by `open(...)` and
        `create(...)`.

        If `create` is True, creates the key if it does not exist.
        If `write` is True, opens the key for writing.  If 'create' is True, the key is always opened for writing.
        Raises KeyError if the key does not exist and 'create' is False.
        """
        if self.is_open():
            raise RuntimeError("Key is already open")
        writable = True if create else write
        assert self._handle is None
        handle, name = self._hkey_name()
        try:
            # create argument is ignored if write is true
            access: int = getattr(winreg, "KEY_READ", 0)
            if writable:
                access |= getattr(winreg, "KEY_WRITE", 0)
            func = getattr(winreg, "CreateKeyEx", None) if create else getattr(winreg, "OpenKeyEx", None)
            if func is None:  # platform shim
                raise FileNotFoundError
            self._handle = func(handle, name, access=access)
        except FileNotFoundError as e:
            raise KeyError(f"Key {self.name!r} not found") from e

    def open(self, *subkeys: str, create: bool = False, write: bool = False) -> Key:
        """Open helper.

        Returns a new opened Key object, leaving the original instance
        unchanged.
        """
        key = self.subkey(*subkeys)
        key.open_handle(create=create, write=write)
        return key

    def create(self, *subkeys: str) -> Key:
        """Create helper.

        Convenience helper that returns a new key opened for writing,
        creating it if necessary.
        """
        key = self.subkey(*subkeys)
        key.open_handle(create=True, write=True)
        return key

    def subkey(self, *subkeys: str) -> Key:
        """Navigation helper.

        Returns a subkey object. If no subkeys are provided, it is the same as
        `dup()`.
        """
        if not subkeys:
            return self.dup()
        return Key(self, *subkeys)

    def dup(self) -> Key:
        """Returns a new, un-opened copy of this key"""
        result = Key(self._parent, self._name)
        if self.is_root():
            result._handle = self._handle
        return result

    def __call__(self, *subkeys: str) -> Key:
        """Compatibility shorthand for `subkey(...)`."""
        return self.subkey(*subkeys)

    def joinpath(self, *subkeys: str) -> Key:
        """Pathlib-style alias for `subkey(...)`."""
        return self.subkey(*subkeys)

    def __truediv__(self, subkey: str) -> Key:
        """Pathlib-style shorthand for `subkey(...)` with one path part."""
        return self.subkey(subkey)

    def exists(self) -> bool:
        """checks if the key exists"""
        if self.is_open():
            return True
        try:
            self.open_handle()
        except KeyError:
            return False
        else:
            return True
        finally:
            self.close()

    def is_open(self) -> bool:
        """Checks if the key is opened"""
        return self._handle is not None

    @property
    def parent(self) -> Key | None:
        """Returns the lexical parent key, or `None` for a registry root."""
        if isinstance(self._parent, Key):
            parts = self._split_subkey_parts(self._name)
            if not parts:
                return self._parent.dup()
            if len(parts) == 1:
                return self._parent.dup()
            return Key(self._parent, *parts[:-1])

        parts = self._split_subkey_parts(self._name)
        if not parts:
            return None
        if len(parts) == 1:
            return None
        return Key(self._parent, *parts[:-1])

    def parents(self) -> tuple[Key, ...]:
        """Returns lexical ancestors from immediate parent up to root."""
        result: list[Key] = []
        current = self.parent
        while current is not None:
            result.append(current)
            current = current.parent
        return tuple(result)

    @property
    def parts(self) -> tuple[str, ...]:
        """Returns path parts, including the root token when present."""
        _, name = self._hkey_fullname()
        return self._split_subkey_parts(name)

    @property
    def handle(self) -> HKeyTypeAlias:
        """Returns the native backend handle for this open key.

        Raises RuntimeError if the key is not open.
        """
        if self._handle is None:
            raise RuntimeError("Key is not open")
        return self._handle

    def is_root(self) -> bool:
        """Checks if the key is a root key"""
        return self._parent == self._handle

    def close(self) -> None:
        """Closes the key."""
        # close if open and if not a root key
        if self.is_open() and not self.is_root():
            handle, self._handle = self._handle, None
            assert handle is not None
            winreg.CloseKey(handle)

    # iterating over the key/value pairs (items) in the key, similar to a dict.

    def items_typed(self) -> Iterator[tuple[str, tuple[Any, int]]]:
        """Iterates over the values in the key, returning (name, (value, type)) tuples."""
        assert self._handle is not None
        i = 0
        while True:
            try:
                name, value, type = winreg.EnumValue(self._handle, i)
                yield (name, (value, type))
                i += 1
            except OSError:
                break

    def items(self) -> Iterator[tuple[str, Any]]:
        """Iterates over the values in the key, returning (name, value) typles"""
        for name, (value, _) in self.items_typed():
            yield (name, value)

    def keys(self) -> Iterator[str]:
        """iterates of the item names in the key"""
        for itemname, _ in self.items_typed():
            yield itemname

    def values(self) -> Iterator[Any]:
        """iterates of the item values in the key"""
        for _, (value, _) in self.items_typed():
            yield value

    def values_typed(self) -> Iterator[tuple[Any, int]]:
        """iterates of the item values in the key, returning (value, type) tuples."""
        for _, value in self.items_typed():
            yield value

    def subkeys(self) -> Iterator[Key]:
        """Iterates over the subkeys in the key"""
        assert self._handle is not None
        i = 0
        while True:
            try:
                name = winreg.EnumKey(self._handle, i)
                yield Key(self, name)
                i += 1
            except OSError:
                break

    def iterdir(self) -> Iterator[Key]:
        """Iterates over child subkeys (pathlib-style alias for `subkeys`)."""
        return self.subkeys()

    def walk(
        self,
        topdown: bool = True,
        onerror: Callable[[OSError], None] | None = None,
        max_depth: int | None = None,
    ) -> Iterator[tuple[Key, list[str], list[str]]]:
        """Walks the key tree, yielding (key, subkey_names, value_names).

        Semantics are similar to `os.walk`:
        - `topdown=True` yields a parent before children and allows pruning by
          mutating `subkey_names` in-place.
        - `topdown=False` yields children before parent.
        """
        if max_depth is not None and max_depth < 0:
            raise ValueError("max_depth must be >= 0")

        def _walk(node: Key, depth: int) -> Iterator[tuple[Key, list[str], list[str]]]:
            with node.open() as opened:
                subkey_names = [subkey.name for subkey in opened.subkeys()]
                value_names = list(opened.keys())

                if topdown:
                    yield opened.dup(), subkey_names, value_names

                if max_depth is None or depth < max_depth:
                    for subkey_name in list(subkey_names):
                        subkey = opened.subkey(subkey_name)
                        try:
                            yield from _walk(subkey, depth + 1)
                        except KeyError:
                            continue
                        except OSError as e:
                            if onerror is not None:
                                onerror(e)
                            continue

                if not topdown:
                    yield opened.dup(), subkey_names, value_names

        return _walk(self, 0)

    def get_typed(self, name: str, default: Any = None) -> tuple[Any, int]:
        """Gets a value from the key, returning (value, type).

        Prefer dict-style access (`key[name]`) when the type is not needed.
        """
        assert self._handle is not None
        try:
            return winreg.QueryValueEx(self._handle, name)
        except FileNotFoundError as e:
            raise KeyError(name) from e

    def set_typed(self, name: str | None, value: Any, type: int = winreg.REG_SZ) -> None:
        """Sets a value in the key, with an explicit registry type.

        Prefer dict-style assignment (`key[name] = value`) for common types.
        """
        assert self._handle is not None
        name = name or ""
        winreg.SetValueEx(self._handle, name, 0, type, value)

    def value_del(self, name: str | None) -> None:
        assert self._handle is not None
        name = name or ""
        winreg.DeleteValue(self._handle, name)

    def get(self, name: str, default: Any = None) -> Any:
        """Gets a value from the key"""
        try:
            return self[name]
        except KeyError:
            return default

    def __getitem__(self, name: str) -> Any:
        """Get a value from the key"""
        assert self._handle is not None
        try:
            v, t = winreg.QueryValueEx(self._handle, name)
            if t == getattr(winreg, "REG_BINARY", 3) and v is None:
                v = b""
            return v
        except FileNotFoundError as e:
            raise KeyError(name) from e

    def __setitem__(self, name: str | None, value: Any) -> None:
        """Sets a value in the key. We assume a string"""
        name = name or ""
        if isinstance(value, tuple):
            return self.set_typed(name, *value)
        elif isinstance(value, int):
            return self.set_typed(name, value, getattr(winreg, "REG_DWORD", 4))
        elif isinstance(value, bytes):
            return self.set_typed(name, value, getattr(winreg, "REG_BINARY", 3))
        elif value is None:
            return self.set_typed(name, None, getattr(winreg, "REG_NONE", 0))
        # default handling
        return self.set_typed(name, value, getattr(winreg, "REG_SZ", 1))

    def __delitem__(self, name: str | None) -> None:
        """Deletes a value from the key"""
        assert self._handle is not None
        name = name or ""
        try:
            winreg.DeleteValue(self._handle, name)
        except FileNotFoundError as e:
            raise KeyError(name) from e

    def __enter__(self) -> Key:
        """Enter context manager.  Raises RuntimeError if the key is not open"""
        if not self.is_open():
            raise RuntimeError("Key is not open")
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def delete(self, tree: bool = False, missing_ok: bool = True) -> None:
        """Deletes the key, optionally recursively."""
        if self.is_open():
            raise ValueError("Cannot delete open key")
        if missing_ok and not self.exists():
            return
        if tree:
            with self.open():
                for subkey in list(self.subkeys()):
                    subkey.delete(tree=True)
        h, n = self._hkey_name()
        winreg.DeleteKey(h, n)

    def print(self, tree: bool = False, indent: int = 4, level: int = 0) -> None:
        """Prints the key to stdout"""
        print(" " * level * indent + f"key: '{self.name}'")
        with self.open() as key:
            for name, value in key.items():
                print(" " * (level + 1) * indent + f"val: '{name}' = {value})")
            if not tree:
                for sub in key.subkeys():
                    print(" " * (level + 1) * indent + f"key: '{sub.name}'")
            else:
                for sub in key.subkeys():
                    sub.print(tree=True, indent=indent, level=level + 1)

    def as_dict(self) -> dict[str, dict[str, dict[str, Any]] | dict[str, Any]]:
        """Returns the key and subkeys as a dictionary"""
        with self.open() as key:
            return {
                "keys": {sub.name: sub.as_dict() for sub in key.subkeys()},
                "values": {name: value for name, value in key.items()},
            }

    def from_dict(self, data: dict[str, Any], remove: bool = False) -> None:
        """Sets the key and subkeys from a dictionary"""
        with self.open(create=True) as key:
            for name, value in data["values"].items():
                if isinstance(value, tuple):
                    key.set_typed(name, *value)
                else:
                    key[name] = value
            for subname, subdata in data["keys"].items():
                with key.create(subname) as subkey:
                    subkey.from_dict(subdata, remove=remove)

            if remove:
                for sub in key.subkeys():
                    if sub.name not in data["keys"]:
                        sub.delete(tree=True)
                for name in key.keys():
                    if name not in data["values"]:
                        del key[name]


# instantiate global root keys
classes_root = Key.classes_root()
current_user = Key.current_user()
local_machine = Key.local_machine()
users = Key.users()
current_config = Key.current_config()
