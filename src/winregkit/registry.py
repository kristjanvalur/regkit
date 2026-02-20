"""helper classes for registry operations"""

from __future__ import annotations

import ntpath
import winreg
from typing import Any, Iterator, Optional, Tuple, Union

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


class Key:
    """A key in the registry.

    Usage style:
    - Use root factories (`current_user`, `local_machine`, ...)
    - Navigate with `subkey(...)`
    - Open with `open(...)` or `create(...)` in a context manager
    - Read/write values via dict-style access (`key[name]`)
    """

    @classmethod
    def _create_root_key(cls, root: int, *subkeys: str) -> Key:
        """Creates a key object for a root key"""
        key = cls(root, *subkeys)
        # an actual root key is always open and has
        # the handle set to the root constant
        if not subkeys:
            key._handle = root
        return key

    @classmethod
    def classes_root(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_CLASSES_ROOT"""
        return cls._create_root_key(winreg.HKEY_CLASSES_ROOT, *subkeys)

    @classmethod
    def current_user(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_CURRENT_USER"""
        return cls._create_root_key(winreg.HKEY_CURRENT_USER, *subkeys)

    @classmethod
    def local_machine(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_LOCAL_MACHINE"""
        return cls._create_root_key(winreg.HKEY_LOCAL_MACHINE, *subkeys)

    @classmethod
    def users(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_USERS"""
        return cls._create_root_key(winreg.HKEY_USERS, *subkeys)

    @classmethod
    def current_config(cls, *subkeys: str) -> Key:
        """Returns a key object for HKEY_CURRENT_CONFIG"""
        return cls._create_root_key(winreg.HKEY_CURRENT_CONFIG, *subkeys)

    def __init__(
        self,
        parent: Key | int,
        *names: str,
    ) -> None:
        """Create a new key object.  The key is not opened or created."""
        self._parent = parent
        if any(not n for n in names):
            raise ValueError("Key names cannot be empty")
        self.name = ntpath.join(*names) if names else ""
        self._handle: Optional[HKeyTypeAlias] = None

    def __del__(self) -> None:
        """Destructor to ensure the key is closed"""
        self.close()

    def _hkey_name(self) -> Tuple[Any, str]:
        """returns a handle and name for the key.  Used internally."""
        if isinstance(self._parent, Key):
            if self._parent.is_open():
                return self._parent._handle, self.name
            h, n = self._parent._hkey_name()
            return h, join_names(n, self.name)
        return self._parent, self.name

    def _hkey_fullname(self) -> Tuple[Any, str]:
        """returns a top level handle and full name for the key.  Used internally."""
        if isinstance(self._parent, Key):
            h, n = self._parent._hkey_fullname()
            return h, join_names(n, self.name)
        return self._parent, self.name

    def __repr__(self) -> str:
        """Returns a string representation of the key"""
        h, n = self._hkey_fullname()
        return f"Key<{handle_to_str(h)}:{n!r}>"

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
        result = Key(self._parent, self.name)
        if self.is_root():
            result._handle = self._handle
        return result

    def __call__(self, *subkeys: str) -> Key:
        """Compatibility shorthand for `subkey(...)`."""
        return self.subkey(*subkeys)

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

    def get_typed(self, name: str, default: Any = None) -> tuple[Any, int]:
        """Gets a value from the key, returning (value, type).

        Prefer dict-style access (`key[name]`) when the type is not needed.
        """
        assert self._handle is not None
        try:
            return winreg.QueryValueEx(self._handle, name)
        except FileNotFoundError as e:
            raise KeyError(name) from e

    def set_typed(self, name: str, value: Any, type: int = winreg.REG_SZ) -> None:
        """Sets a value in the key, with an explicit registry type.

        Prefer dict-style assignment (`key[name] = value`) for common types.
        """
        assert self._handle is not None
        winreg.SetValueEx(self._handle, name, 0, type, value)

    def value_del(self, name: str) -> None:
        assert self._handle is not None
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

    def __setitem__(self, name: str, value: Any) -> None:
        """Sets a value in the key. We assume a string"""
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

    def __delitem__(self, name: str) -> None:
        """Deletes a value from the key"""
        assert self._handle is not None
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
