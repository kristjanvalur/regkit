import sys
import time

import pytest

from tests import fakewinreg as fake


@pytest.mark.usefixtures("require_fake_winreg")
def test_key_basic_operations():
    from src.winregkit.registry import Key

    # use current_user root
    root = Key.current_user()

    # create a subkey and set a value
    with root.create("UnitTest") as k:
        k["alpha"] = "A"
        k["beta"] = 2

        assert k["alpha"] == "A"
        assert k.get("gamma", "X") == "X"

        # ensure items enumerates
        items = dict(k.items())
        assert "alpha" in items and "beta" in items

    # reopen and read values
    with root.open("UnitTest") as k2:
        assert k2["alpha"] == "A"
        assert k2.get_typed("beta")[0] == 2

    # test deletion of value
    # open for write to allow deletion
    with root.open("UnitTest", write=True) as k3:
        del k3["alpha"]
        with pytest.raises(KeyError):
            _ = k3["alpha"]

    # cleanup: reset fake registry to avoid relying on Key.delete tree behavior
    fake.reset()
    sub = root.subkey("UnitTest")
    assert not sub.exists()


def test_parametrized_open_create_write_roundtrip(sandbox_key):
    leaf = sandbox_key.subkey("Roundtrip")

    with pytest.raises(KeyError):
        leaf.open()

    with leaf.open(create=True) as created:
        created["alpha"] = "A"

    with leaf.open(write=True) as writable:
        writable["beta"] = "B"

    with leaf.open() as opened:
        assert opened["alpha"] == "A"
        assert opened["beta"] == "B"


def test_parametrized_value_iteration_and_get(sandbox_key):
    with sandbox_key.create("Values") as key:
        key["name"] = "winregkit"
        key["enabled"] = 1

    with sandbox_key.open("Values") as key:
        assert key.get("missing", "fallback") == "fallback"
        items = dict(key.items())
        assert items["name"] == "winregkit"
        assert items["enabled"] == 1
        assert set(key.keys()) == set(items.keys())
        assert set(key.values()) == set(items.values())


@pytest.mark.usefixtures("require_fake_winreg")
def test_subkeys_and_enum():
    from src.winregkit.registry import Key

    root = Key.current_user()
    # create nested keys
    a = root.create("A")
    b = a.create("B")
    c = b.create("C")
    a.close()
    b.close()
    c.close()

    # enumerate subkeys from root (root is already a root handle)
    with root as r:
        names = {s.name for s in r.subkeys()}
        assert "A" in names

    # cleanup
    fake.reset()
    sub = root.subkey("A")
    assert not sub.exists()


@pytest.mark.usefixtures("require_fake_winreg")
def test_query_info_key_timestamps():
    from src.winregkit.registry import Key

    root = Key.current_user()
    with root.create("TS") as k:
        # capture filetime via fake QueryInfoKey
        nsub, nval, ft0 = fake.QueryInfoKey(k._handle)
        # set a value and ensure timestamp increases
        time.sleep(0.001)
        k["tsv"] = "v"
        nsub, nval, ft1 = fake.QueryInfoKey(k._handle)
        assert ft1 > ft0

    # cleanup
    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_subkey_traversal_with_subkey_chain():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create("Traversal", "Level1", "Level2") as key:
        key["marker"] = "ok"

    via_subkey = root.subkey("Traversal").subkey("Level1").subkey("Level2")
    with via_subkey.open() as key:
        assert key["marker"] == "ok"

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_subkey_traversal_with_open_extra_args():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create("Traversal", "Level1", "Level2") as key:
        key["marker"] = "ok"

    with root.open("Traversal", "Level1", "Level2") as key:
        assert key["marker"] == "ok"

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_subkey_traversal_with_backslash_paths():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create("Traversal", "Level1", "Level2") as key:
        key["marker"] = "ok"

    with root.open(r"Traversal\Level1\Level2") as key:
        assert key["marker"] == "ok"

    with root.open("Traversal", r"Level1\Level2") as key:
        assert key["marker"] == "ok"

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_open_missing_key_raises_keyerror():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()
    key_ref = root.subkey("OpenFlags", "Case")

    with pytest.raises(KeyError):
        key_ref.open()

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_open_create_true_creates_key():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()
    key_ref = root.subkey("OpenFlags", "Case")

    with key_ref.open(create=True) as key:
        key["created"] = "yes"

    with key_ref.open() as key:
        assert key["created"] == "yes"

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_open_read_only_rejects_write():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()
    key_ref = root.subkey("OpenFlags", "Case")

    with key_ref.open(create=True) as key:
        key["created"] = "yes"

    with key_ref.open() as read_only:
        assert read_only["created"] == "yes"
        with pytest.raises(PermissionError):
            read_only["should_fail"] = "no"

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_open_write_true_allows_write():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()
    key_ref = root.subkey("OpenFlags", "Case")

    with key_ref.open(create=True) as key:
        key["created"] = "yes"

    with key_ref.open(write=True) as writable:
        writable["updated"] = "ok"

    with key_ref.open() as key:
        assert key["updated"] == "ok"

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_open_handle_on_open_key_raises_runtimeerror():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()
    key_ref = root.subkey("OpenFlags", "Case")

    with key_ref.open(create=True):
        pass

    with key_ref.open() as key:
        with pytest.raises(RuntimeError):
            key.open_handle()

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_create_creates_or_opens_and_preserves_values():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create("CreateMethod", "Child") as created:
        created["alpha"] = 1

    with root.open("CreateMethod", "Child") as opened:
        assert opened["alpha"] == 1

    with root.create("CreateMethod", "Child") as created_again:
        created_again["beta"] = 2

    with root.open("CreateMethod", "Child") as opened:
        assert opened["alpha"] == 1
        assert opened["beta"] == 2

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_create_accepts_backslash_path():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create(r"CreateMethod\Nested\Leaf") as nested:
        nested["leaf"] = "v"

    with root.open("CreateMethod", "Nested", "Leaf") as nested_open:
        assert nested_open["leaf"] == "v"

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_value_set_and_get_untyped():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create("Values") as key:
        key["text"] = "hello"
        key["count"] = 3
        key["blob"] = b"\x00\x01"
        key["none"] = None
        key["tuple_set"] = ("tuple", fake.REG_SZ)
        key.set_typed("expand", "%PATH%", fake.REG_EXPAND_SZ)

    with root.open("Values") as key:
        assert key["text"] == "hello"
        assert key["count"] == 3
        assert key["blob"] == b"\x00\x01"
        assert key["none"] is None
        assert key["tuple_set"] == "tuple"

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_value_typed_set_and_get():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create("Values") as key:
        key["count"] = 3
        key["blob"] = b"\x00\x01"
        key["none"] = None
        key.set_typed("expand", "%PATH%", fake.REG_EXPAND_SZ)

    with root.open("Values") as key:
        assert key.get_typed("count") == (3, fake.REG_DWORD)
        assert key.get_typed("blob") == (b"\x00\x01", fake.REG_BINARY)
        assert key.get_typed("none") == (None, fake.REG_NONE)
        assert key.get_typed("expand") == ("%PATH%", fake.REG_EXPAND_SZ)

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_value_iteration_methods():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create("Values") as key:
        key["text"] = "hello"
        key["count"] = 3
        key["blob"] = b"\x00\x01"

    with root.open("Values") as key:
        items = dict(key.items())
        typed_items = dict(key.items_typed())
        assert set(key.keys()) == set(items.keys())
        assert len(list(key.values())) == len(items)
        assert len(list(key.values_typed())) == len(typed_items)

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_value_get_default_and_missing_typed():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create("Values") as key:
        key["count"] = 3

    with root.open("Values") as key:
        assert key.get("missing", "fallback") == "fallback"
        assert key.get_typed("count") == (3, fake.REG_DWORD)
        with pytest.raises(KeyError):
            key.get_typed("missing")

    fake.reset()


@pytest.mark.usefixtures("require_fake_winreg")
def test_value_deletion_methods():
    from src.winregkit.registry import Key

    fake.reset()
    root = Key.current_user()

    with root.create("Values") as key:
        key["text"] = "hello"
        key["count"] = 3

    with root.open("Values", write=True) as key:
        key.value_del("text")
        with pytest.raises(KeyError):
            _ = key["text"]

        del key["count"]
        with pytest.raises(KeyError):
            _ = key["count"]

    fake.reset()


@pytest.mark.skipif(sys.platform != "win32", reason="real winreg tests require Windows")
@pytest.mark.usefixtures("require_real_winreg")
class TestKeyRealReadOnly:
    def test_enumerate_root_subkeys(self):
        from src.winregkit.registry import Key

        with Key.current_user() as root:
            names = [sub.name for sub in root.subkeys()]
            assert isinstance(names, list)

    def test_iterate_values_and_types(self):
        from src.winregkit.registry import Key

        with Key.current_user() as root:
            items_typed = list(root.items_typed())
            values_typed = list(root.values_typed())

            assert len(items_typed) == len(values_typed)

            if items_typed:
                name, (value, value_type) = items_typed[0]
                fetched_value, fetched_type = root.get_typed(name)
                assert fetched_value == value
                assert fetched_type == value_type

    def test_open_first_subkey_and_enumerate(self):
        from src.winregkit.registry import Key

        with Key.current_user() as root:
            first_subkey = next(root.subkeys(), None)
            if first_subkey is None:
                pytest.skip("No subkeys found under HKCU")

            with root.open(first_subkey.name) as sub:
                _ = list(sub.subkeys())
                _ = list(sub.items())
                _ = list(sub.items_typed())

    def test_depth_first_hkcu_snapshot_is_tree_like(self):
        from src.winregkit.registry import Key

        max_keys = 100
        visited = 0
        typed_value_iterations = []

        def walk(parent, key_name):
            nonlocal visited
            node = {"name": key_name, "values": [], "children": []}
            try:
                with parent.open(key_name) as key:
                    for name, (value, value_type) in key.items_typed():
                        node["values"].append(name)
                        typed_value_iterations.append((name, value, value_type))
                    if visited >= max_keys:
                        return node

                    for sub in key.subkeys():
                        if visited >= max_keys:
                            break
                        visited += 1
                        try:
                            child = walk(key, sub.name)
                        except (PermissionError, OSError, KeyError):
                            continue
                        node["children"].append(child)
            except (PermissionError, OSError, KeyError):
                return node

            return node

        with Key.current_user() as root:
            snapshot = {"name": "HKEY_CURRENT_USER", "values": [], "children": []}
            for name, (value, value_type) in root.items_typed():
                snapshot["values"].append(name)
                typed_value_iterations.append((name, value, value_type))
            for sub in root.subkeys():
                if visited >= max_keys:
                    break
                visited += 1
                try:
                    snapshot["children"].append(walk(root, sub.name))
                except (PermissionError, OSError, KeyError):
                    continue

        assert visited > 0
        assert isinstance(snapshot["children"], list)

        stack = list(snapshot["children"])
        seen_nested = False
        while stack:
            node = stack.pop()
            assert isinstance(node.get("children"), list)
            assert isinstance(node.get("values"), list)
            if node["children"]:
                seen_nested = True
            stack.extend(node["children"])

        assert typed_value_iterations
        assert seen_nested or any(node["values"] for node in snapshot["children"])
