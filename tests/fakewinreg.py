# This file contains a fake implementation of the winreg module for testing purposes.
# It simulates the behavior of the Windows Registry for unit tests.

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Final, TypeAlias

# difference between Windows epoch (1601-01-01) and Unix epoch (1970-01-01)
# in nanoseconds: 11644473600 seconds
_WINDOWS_EPOCH_DIFF_NS: int = 11644473600 * 1_000_000_000


def time_ns_to_filetime(ns: int) -> int:
    """Convert a time in nanoseconds since Unix epoch to Windows FILETIME
    (100-ns intervals since 1601-01-01).
    """
    return (ns + _WINDOWS_EPOCH_DIFF_NS) // 100


def filetime_to_time_ns(filetime: int) -> int:
    """Convert a Windows FILETIME integer back to nanoseconds since Unix epoch."""
    return filetime * 100 - _WINDOWS_EPOCH_DIFF_NS


HKEY_CLASSES_ROOT: int = 2147483648
HKEY_CURRENT_USER: int = 2147483649
HKEY_LOCAL_MACHINE: int = 2147483650
HKEY_USERS: int = 2147483651
HKEY_PERFORMANCE_DATA: int = 2147483652
HKEY_CURRENT_CONFIG: int = 2147483653
HKEY_DYN_DATA: int = 2147483654

KEY_ALL_ACCESS: Final = 983103
KEY_WRITE: Final = 131078
KEY_READ: Final = 131097
KEY_EXECUTE: Final = 131097
KEY_QUERY_VALUE: Final = 1
KEY_SET_VALUE: Final = 2
KEY_CREATE_SUB_KEY: Final = 4
KEY_ENUMERATE_SUB_KEYS: Final = 8
KEY_NOTIFY: Final = 16
KEY_CREATE_LINK: Final = 32

KEY_WOW64_64KEY: Final = 256
KEY_WOW64_32KEY: Final = 512

REG_BINARY: Final = 3
REG_DWORD: Final = 4
REG_DWORD_LITTLE_ENDIAN: Final = 4
REG_DWORD_BIG_ENDIAN: Final = 5
REG_EXPAND_SZ: Final = 2
REG_LINK: Final = 6
REG_MULTI_SZ: Final = 7
REG_NONE: Final = 0
REG_QWORD: Final = 11
REG_QWORD_LITTLE_ENDIAN: Final = 11
REG_RESOURCE_LIST: Final = 8
REG_FULL_RESOURCE_DESCRIPTOR: Final = 9
REG_RESOURCE_REQUIREMENTS_LIST: Final = 10
REG_SZ: Final = 1

REG_CREATED_NEW_KEY: Final = 1  # undocumented
REG_LEGAL_CHANGE_FILTER: Final = 268435471  # undocumented
REG_LEGAL_OPTION: Final = 31  # undocumented
REG_NOTIFY_CHANGE_ATTRIBUTES: Final = 2  # undocumented
REG_NOTIFY_CHANGE_LAST_SET: Final = 4  # undocumented
REG_NOTIFY_CHANGE_NAME: Final = 1  # undocumented
REG_NOTIFY_CHANGE_SECURITY: Final = 8  # undocumented
REG_NO_LAZY_FLUSH: Final = 4  # undocumented
REG_OPENED_EXISTING_KEY: Final = 2  # undocumented
REG_OPTION_BACKUP_RESTORE: Final = 4  # undocumented
REG_OPTION_CREATE_LINK: Final = 2  # undocumented
REG_OPTION_NON_VOLATILE: Final = 0  # undocumented
REG_OPTION_OPEN_LINK: Final = 8  # undocumented
REG_OPTION_RESERVED: Final = 0  # undocumented
REG_OPTION_VOLATILE: Final = 1  # undocumented
REG_REFRESH_HIVE: Final = 2  # undocumented
REG_WHOLE_HIVE_VOLATILE: Final = 1  # undocumented


class HKEYType:
    """Lightweight handle object returned by CreateKeyEx/OpenKeyEx.

    The object exposes Close(), truthiness, and context-manager support
    (closes on __exit__).
    """

    def __init__(self, name: str, access: int):
        self.name = name
        self.access = access

    def Close(self) -> None:
        # idempotent close
        if getattr(self, "name", None) is None:
            return
        self.name = None

    def __bool__(self) -> bool:
        return self.name is not None

    def check_access(self, required: int) -> None:
        if (self.access & required) != required:
            # Use PermissionError to mirror real permission-denied semantics
            raise PermissionError("Access denied")

    def __enter__(self) -> "HKEYType":
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: Any
    ) -> bool | None:
        self.Close()


_KeyType: TypeAlias = HKEYType | int

# A simple alias for registry value types; keep flexible for tests
RegType: TypeAlias = int


@dataclass
class KeyEntry:
    """Represents a registry key entry stored in the fake registry.

    values maps value-name ("" for default) to a tuple (type, value).
    last_modified is present for parity with real registry but left as 0 for now.
    """

    values: dict[str, tuple[int, Any]] = field(default_factory=dict)
    # store the creation time in nanoseconds for precise conversion later
    last_modified: int = field(default_factory=lambda: time.time_ns())

    def set_value(self, name: str, val_type: int, value: Any) -> None:
        # store default value under empty string
        self.values[name] = (val_type, value)
        self.touch()

    def delete_value(self, name: str) -> bool:
        if name in self.values:
            del self.values[name]
            self.touch()
            return True
        return False

    def touch(self) -> None:
        """Update the last_modified timestamp to the current time."""
        self.last_modified = time.time_ns()


class FakeWinReg:
    """a simple dict based registry. Contains keys. Each key has a dict of values,
    including the default value with the empty-string name.
    """

    def __init__(self) -> None:
        # registry maps full key names to KeyEntry objects; use defaultdict so
        # accessing a missing key auto-creates a KeyEntry instance.
        self.registry: dict[str, KeyEntry] = defaultdict(KeyEntry)

    def reset(self) -> None:
        self.registry.clear()

    def create_key(self, key: str) -> dict[str, tuple[int, Any]]:
        # split the key into parts and ensure each part exists
        parts = key.split("\\")
        # ensure each segment exists (defaultdict will create entries)
        for i in range(1, len(parts) + 1):
            name = "\\".join(parts[:i])
            _ = self.registry[name]
        # touch the parent key (the segment before the last) if it exists
        parent = self.get_parent_entry(key)
        if parent is not None:
            parent.touch()

    def delete_key(self, key: str) -> None:
        if key in self.registry:
            parent = self.get_parent_entry(key)
            del self.registry[key]
            if parent is not None:
                parent.touch()

    def get_parent_entry(self, key: str) -> KeyEntry | None:
        """Get the parent KeyEntry of the given key, or None if it has no parent."""
        parts = key.split("\\")
        if len(parts) <= 1:
            return None
        parent_name = "\\".join(parts[:-1])
        return self.registry.get(parent_name)

    def has_children(self, key: str) -> bool:
        return any(k.startswith(f"{key}\\") for k in self.registry)

    def has_entry(self, key: str) -> bool:
        return key in self.registry

    def get_entry(self, key: str) -> KeyEntry:
        return self.registry[key]

    def get_value(self, key: str) -> dict[str, tuple[int, Any]] | None:
        # Return the values dict for compatibility with existing callers
        entry = self.registry.get(key)
        return entry.values if entry is not None else None

    def check_key(self, key: _KeyType, required: int | None = None) -> None:
        """Validate handle and optionally required access.

        Accepts either an HKEYType handle or a predefined int root. If
        `required` is provided and the key is an HKEYType, perform the
        access check on the handle.
        """
        if isinstance(key, int):
            # accept known predefined root constants
            if key in (
                HKEY_CLASSES_ROOT,
                HKEY_CURRENT_USER,
                HKEY_LOCAL_MACHINE,
                HKEY_USERS,
                HKEY_CURRENT_CONFIG,
            ):
                return
            raise OSError("key must be an opened key")
        if not key.name:
            raise OSError("key is closed")
        if required is not None:
            key.check_access(required)

    def create_name(self, key: _KeyType, sub_key: str | None) -> str:
        if isinstance(key, int):
            try:
                key_name = {
                    HKEY_CLASSES_ROOT: "HKEY_CLASSES_ROOT",
                    HKEY_CURRENT_USER: "HKEY_CURRENT_USER",
                    HKEY_LOCAL_MACHINE: "HKEY_LOCAL_MACHINE",
                    HKEY_USERS: "HKEY_USERS",
                    HKEY_CURRENT_CONFIG: "HKEY_CURRENT_CONFIG",
                }[key]
            except KeyError:
                raise OSError("Invalid predefined key") from None
        else:
            self.check_key(key)
            if not sub_key:
                raise OSError("sub_key must be provided when key is not a predefined key")
            key_name = key.name
        full_key_name = f"{key_name}\\{sub_key}" if sub_key else key_name
        return full_key_name

    def get_subkeys(self, key: str) -> list[str]:
        prefix = f"{key}\\"
        return [k[len(prefix) :] for k in self.registry if k.startswith(prefix) and "\\" not in k[len(prefix) :]]

    # the api methods

    def CloseKey(self, key: _KeyType) -> None:
        """Close a key handle; safe to call multiple times."""
        if isinstance(key, int):
            # can't close a predefined key
            return
        key.Close()

    def CreateKey(self, key: _KeyType, sub_key: str | None) -> HKEYType:
        return self.CreateKeyEx(key, sub_key, 0, KEY_ALL_ACCESS)

    def CreateKeyEx(self, key: _KeyType, sub_key: str | None, reserved: int = 0, access: int = KEY_WRITE) -> HKEYType:
        full_key_name = self.create_name(key, sub_key)
        if isinstance(key, HKEYType):
            key.check_access(KEY_CREATE_SUB_KEY)
        self.create_key(full_key_name)
        return HKEYType(full_key_name, access)

    def OpenKey(self, key: _KeyType, sub_key: str, reserved: int = 0, access: int = KEY_READ) -> HKEYType:
        return self.OpenKeyEx(key, sub_key, reserved, access)

    def OpenKeyEx(self, key: _KeyType, sub_key: str, reserved: int = 0, access: int = KEY_READ) -> HKEYType:
        full_key_name = self.create_name(key, sub_key)
        if not self.has_entry(full_key_name):
            raise FileNotFoundError("The system cannot find the file specified.")
        return HKEYType(full_key_name, access)

    def SetValueEx(self, key: _KeyType, value_name: str | None, reserved: int, type: RegType, value: Any, /) -> None:
        self.check_key(key, KEY_SET_VALUE)
        entry = self.get_entry(key.name)
        if value_name is None:
            value_name = ""
            if type is not REG_SZ:
                raise OSError("Default value must be a string")
        entry.set_value(value_name, type, value)

    def SetValue(self, key: _KeyType, sub_key: str, type: int, value: str, /) -> None:
        self.check_key(key, KEY_SET_VALUE)
        if type is not REG_SZ:
            raise OSError("Default value must be a string")
        if not sub_key:
            entry = self.get_entry(key.name)
        else:
            with self.CreateKey(key, sub_key) as sub:
                entry = self.get_entry(sub.name)
        entry.set_value("", type, value)

    def QueryValue(self, key: _KeyType, sub_key: str | None, /) -> str:
        self.check_key(key, KEY_QUERY_VALUE)
        if sub_key:
            with self.OpenKey(key, sub_key) as sub:
                values = self.get_entry(sub.name).values
        else:
            values = self.get_entry(key.name).values
        if "" not in values:
            # return the empty string
            return ""
        t, v = values[""]
        assert t is REG_SZ
        return v

    def QueryValueEx(self, key: _KeyType, name: str, /) -> tuple[Any, int]:
        self.check_key(key, KEY_QUERY_VALUE)
        values = self.get_entry(key.name).values
        if not name:
            name = ""
        if name not in values:
            raise FileNotFoundError("The system cannot find the file specified.")
        return values[name][1], values[name][0]

    def QueryInfoKey(self, key: _KeyType) -> tuple[int, int, int]:
        self.check_key(key, KEY_QUERY_VALUE | KEY_ENUMERATE_SUB_KEYS)
        subkeys = self.get_subkeys(key.name)
        entry = self.get_entry(key.name)
        values = entry.values
        num_subkeys = len(subkeys)
        num_values = len(values) if values is not None else 0
        # Return the stored last_modified timestamp for the key converted to
        # Windows FILETIME units: 100-nanosecond intervals since 1601-01-01.
        if entry is None:
            filetime = 0
        else:
            ns = entry.last_modified
            filetime = time_ns_to_filetime(ns)
        return (num_subkeys, num_values, filetime)

    def DeleteValue(self, key: _KeyType, value_name: str) -> None:
        self.check_key(key, KEY_SET_VALUE)
        entry = self.get_entry(key.name)
        if not entry.delete_value(value_name):
            raise FileNotFoundError("The system cannot find the value specified.")

    def DeleteKey(self, key: _KeyType, sub_key: str) -> None:
        return self.DeleteKeyEx(key, sub_key, KEY_WOW64_64KEY, 0)

    def DeleteKeyEx(self, key: _KeyType, sub_key: str, access=KEY_WOW64_64KEY, reserved: int = 0) -> None:
        self.check_key(key)
        full_key_name = self.create_name(key, sub_key)
        if self.has_children(full_key_name):
            raise PermissionError("The system cannot delete a key that has subkeys.")
        self.delete_key(full_key_name)

    def EnumKey(self, key: _KeyType, index: int, /) -> str:
        self.check_key(key, KEY_ENUMERATE_SUB_KEYS)
        # resolve the base name: HKEYType has .name, int roots need mapping
        if isinstance(key, HKEYType):
            base_name = key.name
        else:
            base_name = self.create_name(key, None)
        subkeys = sorted(self.get_subkeys(base_name))
        try:
            return subkeys[index]
        except IndexError:
            raise OSError("The system cannot find the file specified.") from None

    def EnumValue(self, key: _KeyType, index: int, /) -> tuple[str, Any, int]:
        self.check_key(key)
        if isinstance(key, HKEYType):
            key.check_access(KEY_QUERY_VALUE)
        values = self.get_entry(key.name).values
        value_names = sorted(values.keys(), key=lambda x: (x == "", x))
        try:
            name = value_names[index]
            t, v = values[name]
            return (name if name != "" else "", v, t)
        except IndexError:
            raise OSError("The system cannot find the file specified.") from None


FakeWinRegInstance = FakeWinReg()


def reset():
    FakeWinRegInstance.registry.clear()


apis = [
    "CloseKey",
    "CreateKey",
    "CreateKeyEx",
    "OpenKey",
    "OpenKeyEx",
    "SetValue",
    "SetValueEx",
    "QueryInfoKey",
    "QueryValue",
    "QueryValueEx",
    "DeleteValue",
    "DeleteKey",
    "EnumKey",
    "EnumValue",
]
for api in apis:
    globals()[api] = getattr(FakeWinRegInstance, api)

__all__ = ["HKEYType", "RegType"] + apis
