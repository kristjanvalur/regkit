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
