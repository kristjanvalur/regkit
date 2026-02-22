import sys
import time

import pytest

from tests import fakewinreg as fake


def test_key_basic_operations(sandbox_key):
    root = sandbox_key

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

    sub = root.subkey("UnitTest")
    assert sub.exists()


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


def test_subkeys_and_enum(sandbox_key):
    root = sandbox_key
    # create nested keys
    a = root.create("A")
    b = a.create("B")
    c = b.create("C")
    a.close()
    b.close()
    c.close()

    # enumerate subkeys from the sandbox root
    with root.open() as r:
        names = {s.name for s in r.subkeys()}
        assert "A" in names

    sub = root.subkey("A")
    assert sub.exists()


def test_iterdir_alias_matches_subkeys(sandbox_key):
    root = sandbox_key

    with root.create("IterA"):
        pass
    with root.create("IterB"):
        pass

    with root.open() as key:
        subkeys_names = {sub.name for sub in key.subkeys()}
        iterdir_names = {sub.name for sub in key.iterdir()}

    assert iterdir_names == subkeys_names


def test_query_info_key_timestamps(sandbox_key):
    import src.winregkit.registry as registry_module

    with sandbox_key.create("TS") as key:
        # Integration check: modifying values through Key should be reflected
        # in the backend's key last-write timestamp (QueryInfoKey FILETIME).
        _, _, ft0 = registry_module.winreg.QueryInfoKey(key.handle)

        ft1 = ft0
        for _ in range(10):
            time.sleep(0.01)
            key["tsv"] = "v"
            _, _, ft1 = registry_module.winreg.QueryInfoKey(key.handle)
            if ft1 > ft0:
                break

        assert ft1 > ft0


def test_handle_property_requires_open_key(sandbox_key):
    leaf = sandbox_key.subkey("Handle")

    with pytest.raises(RuntimeError):
        _ = leaf.handle

    with leaf.open(create=True) as key:
        assert key.handle

    with pytest.raises(RuntimeError):
        _ = leaf.handle


def test_parent_for_root_is_none():
    from src.winregkit.registry import Key

    root = Key.current_user()
    assert root.parent is None


def test_parents_for_root_is_empty_tuple():
    from src.winregkit.registry import Key

    root = Key.current_user()
    assert root.parents() == ()


def test_parent_for_nested_key_returns_lexical_parent(sandbox_key):
    key = sandbox_key.subkey("Parent", "Child", "Leaf")

    parent = key.parent
    assert parent is not None
    assert parent.name == "Child"
    assert parent.parts[-2:] == ("Parent", "Child")

    grandparent = parent.parent
    assert grandparent is not None
    assert grandparent.name == "Parent"


def test_parents_for_nested_key_returns_ordered_ancestors(sandbox_key):
    key = sandbox_key.subkey("Parent", "Child", "Leaf")

    ancestors = key.parents()

    assert len(ancestors) >= 3
    assert ancestors[0].name == "Child"
    assert ancestors[0].parts[-2:] == ("Parent", "Child")
    assert ancestors[1].name == "Parent"
    assert ancestors[1].parts[-1] == "Parent"
    assert ancestors[2].parts == sandbox_key.parts


def test_key_ordering_is_case_insensitive_by_path(sandbox_key):
    key_a = sandbox_key.subkey("Ordering", "Alpha")
    key_b = sandbox_key.subkey("ordering", "beta")
    key_c = sandbox_key.subkey("ORDERING", "Gamma")

    sorted_names = [key.name for key in sorted([key_c, key_b, key_a])]
    assert sorted_names == ["Alpha", "beta", "Gamma"]


def test_key_equality_is_case_insensitive_by_path(sandbox_key):
    key_upper = sandbox_key.subkey("CASE", "Path")
    key_lower = sandbox_key.subkey("case", "path")

    assert key_upper == key_lower


def test_key_equality_and_hash_are_root_alias_insensitive(sandbox_key):
    from src.winregkit.registry import Key

    rel_parts = sandbox_key.parts[1:]
    key_alias = Key.from_parts(("HKCU", *rel_parts, "AliasEq"))
    key_full = Key.from_parts(("HKEY_CURRENT_USER", *rel_parts, "aliaseq"))

    assert key_alias == key_full
    assert hash(key_alias) == hash(key_full)


def test_canonical_path_and_parts_use_canonical_root_alias(sandbox_key):
    from src.winregkit.registry import Key

    rel_parts = sandbox_key.parts[1:]
    key = Key.from_parts(("HKCU", *rel_parts, "Canon"))

    canonical_parts = key.canonical_parts()
    assert canonical_parts[0] == "HKEY_CURRENT_USER"
    assert canonical_parts[-1] == "Canon"
    assert key.canonical_path() == "\\".join(canonical_parts)


def test_canonical_path_for_raw_handle_ignores_first_label():
    from src.winregkit.registry import Key

    key_foo = Key(100, "foo")
    key_bar = Key(100, "bar")

    assert key_foo == key_bar
    assert hash(key_foo) == hash(key_bar)
    assert key_foo.canonical_path() == key_bar.canonical_path()
    assert key_foo.canonical_parts() == key_bar.canonical_parts()


def test_parts_include_root_and_subkeys(sandbox_key):
    from src.winregkit.registry import Key

    key = sandbox_key.subkey("Parts", "Leaf")

    parts = key.parts
    assert parts[0] == "HKEY_CURRENT_USER"
    assert parts[-2:] == ("Parts", "Leaf")

    rebuilt = Key.from_parts(parts)
    assert rebuilt.parts == parts
    assert rebuilt.name == "Leaf"


def test_parts_for_root_only_contains_root_token():
    from src.winregkit.registry import Key

    root = Key.current_user()
    assert root.parts == ("HKEY_CURRENT_USER",)


def test_from_parts_accepts_alias_and_roundtrips():
    from src.winregkit.registry import Key

    key = Key.from_parts(("HKCU", "Software", "winregkit-tests"))
    assert key.parts == ("HKCU", "Software", "winregkit-tests")


def test_from_parts_invalid_input_raises_value_error():
    from src.winregkit.registry import Key

    with pytest.raises(ValueError):
        Key.from_parts(())

    with pytest.raises(ValueError):
        Key.from_parts(("", "Software"))

    with pytest.raises(ValueError):
        Key.from_parts(("NOT_A_ROOT", "Software"))


def test_from_path_with_full_root_name(sandbox_key):
    from src.winregkit.registry import Key

    with sandbox_key.create("FromPath", "Full") as key:
        key["value"] = "ok"

    sandbox_relative_path = "\\".join(sandbox_key.parts[1:])
    key_from_path = Key.from_path(f"HKEY_CURRENT_USER\\{sandbox_relative_path}\\FromPath\\Full")
    with key_from_path.open() as key:
        assert key["value"] == "ok"


def test_from_path_with_root_alias(sandbox_key):
    from src.winregkit.registry import Key

    with sandbox_key.create("FromPath", "Alias") as key:
        key["value"] = "ok"

    sandbox_relative_path = "\\".join(sandbox_key.parts[1:])
    key_from_path = Key.from_path(f"HKCU\\{sandbox_relative_path}\\FromPath\\Alias")
    with key_from_path.open() as key:
        assert key["value"] == "ok"


def test_from_path_root_only_returns_open_root():
    from src.winregkit.registry import Key

    root = Key.from_path("HKCU")
    assert root.is_open()
    assert root.is_root()


def test_from_path_invalid_paths_raise_value_error():
    from src.winregkit.registry import Key

    with pytest.raises(ValueError):
        Key.from_path("")

    with pytest.raises(ValueError):
        Key.from_path("   ")

    with pytest.raises(ValueError):
        Key.from_path("NOT_A_ROOT\\Software")


def test_key_int_parent_with_name_is_opened_and_named():
    import src.winregkit.registry as registry_module

    key = registry_module.Key(registry_module.winreg.HKEY_CURRENT_USER, "Software")
    assert key.is_open()
    assert key.name == "Software"


def test_subkey_traversal_with_subkey_chain(sandbox_key):
    root = sandbox_key

    with root.create("Traversal", "Level1", "Level2") as key:
        key["marker"] = "ok"

    via_subkey = root.subkey("Traversal").subkey("Level1").subkey("Level2")
    with via_subkey.open() as key:
        assert key["marker"] == "ok"


def test_subkey_traversal_with_open_extra_args(sandbox_key):
    root = sandbox_key

    with root.create("Traversal", "Level1", "Level2") as key:
        key["marker"] = "ok"

    with root.open("Traversal", "Level1", "Level2") as key:
        assert key["marker"] == "ok"


def test_subkey_traversal_with_backslash_paths(sandbox_key):
    root = sandbox_key

    with root.create("Traversal", "Level1", "Level2") as key:
        key["marker"] = "ok"

    with root.open(r"Traversal\Level1\Level2") as key:
        assert key["marker"] == "ok"

    with root.open("Traversal", r"Level1\Level2") as key:
        assert key["marker"] == "ok"


def test_joinpath_alias_matches_subkey_chain(sandbox_key):
    root = sandbox_key

    with root.create("JoinPath", "A", "B") as key:
        key["marker"] = "ok"

    via_joinpath = root.joinpath("JoinPath").joinpath("A", "B")
    with via_joinpath.open() as key:
        assert key["marker"] == "ok"


def test_truediv_operator_matches_subkey_chain(sandbox_key):
    root = sandbox_key

    with root.create("DivPath", "A", "B") as key:
        key["marker"] = "ok"

    via_div = root / "DivPath" / "A" / "B"
    with via_div.open() as key:
        assert key["marker"] == "ok"


def test_walk_topdown_yields_root_first_with_expected_names(sandbox_key):
    root = sandbox_key.subkey("WalkTop")

    with root.open(create=True, write=True) as key:
        key["root_val"] = "rv"
    with root.create("A") as key:
        key["a_val"] = "a"
    with root.create("B"):
        pass

    walked = list(root.walk(topdown=True))
    first_key, first_subkeys, first_values = walked[0]

    assert first_key.name == root.name
    assert set(first_subkeys) == {"A", "B"}
    assert set(first_values) == {"root_val"}


def test_walk_topdown_pruning_skips_branch(sandbox_key):
    root = sandbox_key.subkey("WalkPrune")

    with root.open(create=True):
        pass
    with root.create("Keep", "Leaf"):
        pass
    with root.create("Skip", "Leaf"):
        pass

    visited = []
    for key, subkey_names, _ in root.walk(topdown=True):
        visited.append(key.name)
        if key.name == root.name:
            subkey_names[:] = [name for name in subkey_names if name != "Skip"]

    assert "Keep" in visited
    assert "Leaf" in visited
    assert "Skip" not in visited


def test_walk_bottomup_yields_parent_last(sandbox_key):
    root = sandbox_key.subkey("WalkBottom")

    with root.open(create=True):
        pass
    with root.create("Child", "Grandchild"):
        pass

    walked = list(root.walk(topdown=False))
    assert walked[-1][0].name == root.name


def test_walk_max_depth_zero_yields_only_root(sandbox_key):
    root = sandbox_key.subkey("WalkDepth")

    with root.open(create=True, write=True) as key:
        key["root_val"] = "rv"
    with root.create("Child"):
        pass

    walked = list(root.walk(max_depth=0))
    assert len(walked) == 1
    key, subkeys, values = walked[0]
    assert key.name == root.name
    assert set(subkeys) == {"Child"}
    assert set(values) == {"root_val"}


def test_walk_missing_start_key_raises_keyerror_when_iterating(sandbox_key):
    missing = sandbox_key.subkey("WalkMissing")
    walker = missing.walk()

    with pytest.raises(KeyError):
        next(walker)


def test_walk_negative_max_depth_raises_valueerror(sandbox_key):
    root = sandbox_key.subkey("WalkNegativeDepth")

    with pytest.raises(ValueError):
        root.walk(max_depth=-1)


def test_open_missing_key_raises_keyerror(sandbox_key):
    root = sandbox_key
    key_ref = root.subkey("OpenFlags", "Case")

    with pytest.raises(KeyError):
        key_ref.open()


def test_open_create_true_creates_key(sandbox_key):
    root = sandbox_key
    key_ref = root.subkey("OpenFlags", "Case")

    with key_ref.open(create=True) as key:
        key["created"] = "yes"

    with key_ref.open() as key:
        assert key["created"] == "yes"


def test_open_read_only_rejects_write(sandbox_key):
    root = sandbox_key
    key_ref = root.subkey("OpenFlags", "Case")

    with key_ref.open(create=True) as key:
        key["created"] = "yes"

    with key_ref.open() as read_only:
        assert read_only["created"] == "yes"
        with pytest.raises(PermissionError):
            read_only["should_fail"] = "no"


def test_open_write_true_allows_write(sandbox_key):
    root = sandbox_key
    key_ref = root.subkey("OpenFlags", "Case")

    with key_ref.open(create=True) as key:
        key["created"] = "yes"

    with key_ref.open(write=True) as writable:
        writable["updated"] = "ok"

    with key_ref.open() as key:
        assert key["updated"] == "ok"


def test_open_handle_on_open_key_raises_runtimeerror(sandbox_key):
    root = sandbox_key
    key_ref = root.subkey("OpenFlags", "Case")

    with key_ref.open(create=True):
        pass

    with key_ref.open() as key:
        with pytest.raises(RuntimeError):
            key.open_handle()


def test_create_creates_or_opens_and_preserves_values(sandbox_key):
    root = sandbox_key

    with root.create("CreateMethod", "Child") as created:
        created["alpha"] = 1

    with root.open("CreateMethod", "Child") as opened:
        assert opened["alpha"] == 1

    with root.create("CreateMethod", "Child") as created_again:
        created_again["beta"] = 2

    with root.open("CreateMethod", "Child") as opened:
        assert opened["alpha"] == 1
        assert opened["beta"] == 2


def test_create_accepts_backslash_path(sandbox_key):
    root = sandbox_key

    with root.create(r"CreateMethod\Nested\Leaf") as nested:
        nested["leaf"] = "v"

    with root.open("CreateMethod", "Nested", "Leaf") as nested_open:
        assert nested_open["leaf"] == "v"


def test_value_set_and_get_untyped(sandbox_key):
    root = sandbox_key

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


def test_value_typed_set_and_get(sandbox_key):
    root = sandbox_key

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


def test_value_iteration_methods(sandbox_key):
    root = sandbox_key

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


def test_value_get_default_and_missing_typed(sandbox_key):
    root = sandbox_key

    with root.create("Values") as key:
        key["count"] = 3

    with root.open("Values") as key:
        assert key.get("missing", "fallback") == "fallback"
        assert key.get_typed("count") == (3, fake.REG_DWORD)
        with pytest.raises(KeyError):
            key.get_typed("missing")


def test_value_deletion_methods(sandbox_key):
    root = sandbox_key

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
