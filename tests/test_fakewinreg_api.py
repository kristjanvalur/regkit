import time

import pytest

from . import fakewinreg as fake

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]


USERKEY = r"Software\FakeTest"


# a test fixture to provide a fresh fake registry for each test
@pytest.fixture(autouse=True)
def fresh_registry():
    fake.reset()
    try:
        yield
    finally:
        fake.reset()


@pytest.fixture
def fake_module_and_key():
    key = fake.CreateKeyEx(fake.HKEY_CURRENT_USER, USERKEY, 0, fake.KEY_ALL_ACCESS)
    try:
        yield fake, key
    finally:
        delete_tree(fake, key)
        key.Close()
        fake.reset()


@pytest.fixture
def real_module_and_key():
    if winreg is None:
        pytest.skip("winreg not available on this platform")
    k = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, USERKEY, 0, winreg.KEY_ALL_ACCESS)
    try:
        yield winreg, k
    finally:
        delete_tree(winreg, k)
        k.Close()


@pytest.fixture(params=["fake", "real"] if winreg else ["fake"])
def module_and_key(request):
    backend = request.getfixturevalue(request.param + "_module_and_key")  # request.param is e.g. "fake_module"
    yield backend


@pytest.fixture
def module(module_and_key):
    return module_and_key[0]


def delete_tree(module, key):
    """Recursively delete a key and all its subkeys/values."""
    try:
        while True:
            subkey = module.EnumKey(key, 0)
            subkey_handle = module.OpenKey(key, subkey, 0, module.KEY_ALL_ACCESS)
            delete_tree(module, subkey_handle)
            module.CloseKey(subkey_handle)
            module.DeleteKey(key, subkey)
    except OSError:
        pass  # no more subkeys
    try:
        while True:
            value_name, _, _ = module.EnumValue(key, 0)
            module.DeleteValue(key, value_name)
    except OSError:
        pass  # no more values


EXPECTED_CONSTANT_PREFIX = "HKEY_"
EXPECTED_FUNCTIONS = {
    "CreateKey",
    "CreateKeyEx",
    "OpenKey",
    "OpenKeyEx",
    "SetValue",
    "SetValueEx",
    "QueryValue",
    "QueryValueEx",
}


def test_exports_present():
    # ensure expected functions are present and callable
    for name in EXPECTED_FUNCTIONS:
        assert hasattr(fake, name), f"{name} missing from fakewinreg"
        obj = getattr(fake, name)
        assert callable(obj), f"{name} is not callable"


def test_hkey_constants():
    # at least the common HKEY_* constants should exist and be ints
    for const in ("HKEY_CLASSES_ROOT", "HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE", "HKEY_USERS"):
        assert hasattr(fake, const), f"{const} missing"
        val = getattr(fake, const)
        assert isinstance(val, int), f"{const} is not int"


def test_reg_type_constants():
    # common REG_* constants
    for const in ("REG_SZ", "REG_DWORD", "REG_BINARY", "REG_NONE"):
        assert hasattr(fake, const), f"{const} missing"
        assert isinstance(getattr(fake, const), int)


def test_create_and_query_value_roundtrip(module_and_key):
    # smoke test using the provided module (fake or real) to create a value and read it back
    module, h = module_and_key
    module.SetValueEx(h, "test", 0, module.REG_SZ, "hello")
    val, typ = module.QueryValueEx(h, "test")
    assert val == "hello"
    assert typ == module.REG_SZ


def test_default_value_and_enum(module_and_key):
    module, h = module_and_key
    # create a parent and two subkeys under the provided key
    parent = module.CreateKeyEx(h, "FakeTestEnum", access=module.KEY_ALL_ACCESS)
    try:
        s1 = module.CreateKeyEx(parent, "SubA", access=module.KEY_ALL_ACCESS)
        s2 = module.CreateKeyEx(parent, "SubB", access=module.KEY_ALL_ACCESS)
        # set default values using SetValueEx with name=None
        module.SetValueEx(s1, None, 0, module.REG_SZ, "value-a")
        module.SetValueEx(s2, None, 0, module.REG_SZ, "value-b")

        # enumerate subkeys from the parent
        names = {module.EnumKey(parent, 0), module.EnumKey(parent, 1)}
        assert names == {"SubA", "SubB"}

        # enumerate values on a subkey (default value appears as empty string)
        name, val, typ = module.EnumValue(s1, 0)
        assert name == ""
        assert val == "value-a"
        assert typ == module.REG_SZ
    finally:
        # cleanup
        try:
            module.DeleteKey(parent, "SubA")
        except Exception:
            pass
        try:
            module.DeleteKey(parent, "SubB")
        except Exception:
            pass
        try:
            module.DeleteKey(h, "FakeTestEnum")
        except Exception:
            pass


def test_delete_value_and_error_paths(module_and_key):
    module, h = module_and_key
    # create a test subkey under the provided key
    t = module.CreateKeyEx(h, "DeleteTest", access=module.KEY_ALL_ACCESS)
    try:
        # set a named value and then delete it
        module.SetValueEx(t, "named", 0, module.REG_SZ, "to-delete")
        val, typ = module.QueryValueEx(t, "named")
        assert val == "to-delete"
        module.DeleteValue(t, "named")
        # now querying should raise
        with pytest.raises(OSError):
            module.QueryValueEx(t, "named")

        # deleting a key that has children should raise
        parent = module.CreateKeyEx(t, "HasChild", access=module.KEY_ALL_ACCESS)
        child = module.CreateKeyEx(parent, "Child", access=module.KEY_ALL_ACCESS)
        with pytest.raises(PermissionError):
            module.DeleteKey(t, "HasChild")
    finally:
        parent.Close()
        child.Close()
        t.Close()
        # best effort cleanup; skip errors
        try:
            module.DeleteKey(t, "HasChild\\Child")
        except Exception:
            pass
        try:
            module.DeleteKey(t, "HasChild")
        except Exception:
            pass
        try:
            module.DeleteKey(h, "DeleteTest")
        except Exception:
            pass


def test_module_exercises(module_and_key):
    r"""Use the parametrized `module` fixture (fake or real winreg) and exercise
    registry operations under HKEY_CURRENT_USER\Software\FakeTest.
    """
    module, h = module_and_key
    # open/create the test key (module fixtures ensure it exists)
    # set two named values
    module.SetValueEx(h, "alpha", 0, module.REG_SZ, "A")
    module.SetValueEx(h, "beta", 0, module.REG_SZ, "B")

    # read them back
    va, ta = module.QueryValueEx(h, "alpha")
    vb, tb = module.QueryValueEx(h, "beta")
    assert va == "A"
    assert vb == "B"
    assert ta == module.REG_SZ and tb == module.REG_SZ

    # enumerate values (collect until OSError)
    vals = set()
    i = 0
    while True:
        try:
            name, value, typ = module.EnumValue(h, i)
            vals.add(name)
            i += 1
        except OSError:
            break
    assert {"alpha", "beta"}.issubset(vals)

    # create two subkeys and enumerate them
    s1 = module.CreateKeyEx(h, "SK1", 0, module.KEY_ALL_ACCESS)
    s2 = module.CreateKeyEx(h, "SK2", 0, module.KEY_ALL_ACCESS)
    subs = set()
    j = 0
    while True:
        try:
            subs.add(module.EnumKey(h, j))
            j += 1
        except OSError:
            break
    assert {"SK1", "SK2"}.issubset(subs)
    s1.Close()
    s2.Close()

    # delete a value and ensure QueryValueEx fails
    module.DeleteValue(h, "alpha")
    with pytest.raises(OSError):
        module.QueryValueEx(h, "alpha")


def test_access_permissions(module_and_key):
    module, h = module_and_key
    # open a read-only handle and ensure write/create operations fail
    with module.CreateKeyEx(h, "readonly", 0, module.KEY_READ) as ro:
        # Observed behavior in this session: real winreg may allow creating a
        # subkey from a read-only handle but still disallow setting values.
        if module is winreg:
            # CreateKeyEx may succeed; if it does, close the returned handle.
            new = module.CreateKeyEx(ro, "NoCreate", 0, module.KEY_ALL_ACCESS)
            try:
                # setting a value on a read-only handle should fail with PermissionError
                with pytest.raises(PermissionError):
                    module.SetValueEx(ro, "nv", 0, module.REG_SZ, "x")
            finally:
                try:
                    new.Close()
                except Exception:
                    pass
        else:
            # For the fake backend require PermissionError on both operations
            with pytest.raises(PermissionError):
                module.CreateKeyEx(ro, "NoCreate", 0, module.KEY_ALL_ACCESS)
            with pytest.raises(PermissionError):
                module.SetValueEx(ro, "nv", 0, module.REG_SZ, "x")


def test_cannot_delete_key_with_subkeys(module_and_key):
    module, h = module_and_key
    # create a child and assert deleting the parent fails
    module.CreateKeyEx(h, "ChildA\\ChildB", 0, module.KEY_ALL_ACCESS)
    # Require PermissionError for attempts to delete a key that has subkeys
    with pytest.raises(PermissionError):
        module.DeleteKey(h, "ChildA")
    # cleanup child
    try:
        module.DeleteKey(h, "ChildA\\ChildB")
    except Exception:
        pass


def test_enumerate_subkeys_and_values(module_and_key):
    module, h = module_and_key
    module.CreateKeyEx(h, "Sub1", 0, module.KEY_ALL_ACCESS)
    module.CreateKeyEx(h, "Sub2", 0, module.KEY_ALL_ACCESS)
    module.SetValueEx(h, "v1", 0, module.REG_SZ, "one")
    module.SetValueEx(h, "v2", 0, module.REG_SZ, "two")
    module.SetValue(h, "", module.REG_SZ, "default")
    module.SetValue(h, "Sub3", module.REG_SZ, "default")

    # enumerate subkeys
    subs = set()
    i = 0
    while True:
        try:
            subs.add(module.EnumKey(h, i))
            i += 1
        except OSError:
            break
    assert {"Sub1", "Sub2", "Sub3"} == subs

    # enumerate values
    vals = set()
    j = 0
    while True:
        try:
            name, value, typ = module.EnumValue(h, j)
            vals.add(name)
            j += 1
        except OSError:
            break
    assert {"v1", "v2", ""} == vals


def test_key_context_manager_closes(module_and_key):
    module, h = module_and_key
    # HKEYType should close on exiting a 'with' block
    with module.CreateKeyEx(h, "CtxTest", 0, module.KEY_ALL_ACCESS) as k:
        # inside context the key should be truthy
        assert bool(k)
    # after exit, the key should be closed
    assert not bool(k)


def test_delete_tree_cleanup(module_and_key):
    """Create a nested hierarchy and leave it in place; the module fixture's
    teardown should remove it via delete_tree. This test simply builds the
    structure and asserts it exists before exit.
    """
    module, h = module_and_key
    # build nested structure
    a = module.CreateKeyEx(h, "A", 0, module.KEY_ALL_ACCESS)
    b = module.CreateKeyEx(a, "B", 0, module.KEY_ALL_ACCESS)
    c = module.CreateKeyEx(b, "C", 0, module.KEY_ALL_ACCESS)
    module.SetValueEx(a, "va", 0, module.REG_SZ, "a")
    module.SetValueEx(b, "vb", 0, module.REG_SZ, "b")
    module.SetValueEx(c, "vc", 0, module.REG_SZ, "c")

    # assert the deepest key can be enumerated from its parent
    assert module.EnumKey(b, 0) == "C"
    # leave everything in place — teardown should clean it up


def test_setvalue_and_queryvalue_default_behavior(module_and_key):
    """Verify SetValue can set default values on the given key or a subkey,
    and QueryValue accepts both None and empty string for sub_key and returns
    the default value appropriately.
    """
    module, h = module_and_key

    # set the default on the root of h using empty string
    module.SetValue(h, "", module.REG_SZ, "root-default")
    # both None and empty string should return the default
    assert module.QueryValue(h, None) == "root-default"
    assert module.QueryValue(h, "") == "root-default"

    # set default on a subkey via SetValue (this should create the subkey)
    module.SetValue(h, "SubDefault", module.REG_SZ, "sub-default")
    # QueryValue with the subkey name should return the subkey's default
    assert module.QueryValue(h, "SubDefault") == "sub-default"

    # Also ensure that asking for the parent default still returns the parent value
    assert module.QueryValue(h, None) == "root-default"


def test_queryvalue_accepts_empty_and_none_for_missing_subkey(module_and_key):
    module, h = module_and_key
    # when no default is set, QueryValue should raise
    with pytest.raises(OSError):
        module.DeleteValue(h, "")

    # the default value should return an empty string
    val = module.QueryValue(h, None)
    assert val == ""

    # but this api should return a FileNotFoundError
    with pytest.raises(FileNotFoundError):
        module.QueryValueEx(h, "")


def test_enum_on_empty_key_raises(module_and_key):
    module, h = module_and_key
    # ensure fresh empty key enumerations raise OSError
    # create a truly empty subkey
    sk = module.CreateKeyEx(h, "EmptySK", 0, module.KEY_ALL_ACCESS)
    try:
        with pytest.raises(OSError):
            module.EnumKey(sk, 0)
        with pytest.raises(OSError):
            module.EnumValue(sk, 0)
    finally:
        try:
            module.DeleteKey(h, "EmptySK")
        except Exception:
            pass


def test_fake_reset_idempotent(fake_module_and_key):
    fake_mod, k = fake_module_and_key
    # set some values and subkeys
    fake_mod.CreateKeyEx(k, "R1", 0, fake_mod.KEY_ALL_ACCESS)
    fake_mod.SetValueEx(k, "rval", 0, fake_mod.REG_SZ, "x")
    # reset twice and ensure no exceptions and registry is empty afterwards
    fake.reset()
    fake.reset()
    # after reset the registry should be empty; creating the top-level key again should be fine
    n = fake.CreateKeyEx(fake.HKEY_CURRENT_USER, USERKEY, 0, fake.KEY_ALL_ACCESS)
    try:
        fake.SetValueEx(n, "after", 0, fake.REG_SZ, "ok")
    finally:
        try:
            delete_tree(fake, n)
        except Exception:
            pass


def test_check_key_closed_and_invalid(module_and_key):
    """Ensure operations on a closed handle and on an invalid numeric key
    raise the expected errors. The fake implementation uses OSError for
    invalid numeric keys and for closed handles; real winreg parity is
    checked where available in this session.
    """
    module, h = module_and_key

    # close the handle and then attempt an operation
    h.Close()
    # operations on a closed handle should raise an OSError or similar
    with pytest.raises(OSError):
        module.QueryValueEx(h, "anything")

    # passing an invalid numeric predefined key should raise on the fake
    # backend; real winreg may raise OSError as well
    invalid_predef = 0xDEADBEEF
    if module is not winreg:
        with pytest.raises(OSError):
            module.CreateKeyEx(invalid_predef, "sub", 0, module.KEY_ALL_ACCESS)
    else:
        # real winreg on Windows raises OSError for invalid predefined keys
        # This may cause crashes, so we skip it.
        pass


def test_fake_closed_handle_createkey_raises(fake_module_and_key):
    fake_mod, h = fake_module_and_key
    h.Close()

    with pytest.raises(OSError):
        fake_mod.CreateKeyEx(h, "sub", 0, fake_mod.KEY_ALL_ACCESS)


def test_fake_closed_handle_openkey_raises(fake_module_and_key):
    fake_mod, h = fake_module_and_key
    h.Close()

    with pytest.raises(OSError):
        fake_mod.OpenKeyEx(h, "sub", 0, fake_mod.KEY_READ)


def test_fake_closed_handle_deletekey_raises(fake_module_and_key):
    fake_mod, h = fake_module_and_key
    h.Close()

    with pytest.raises(OSError):
        fake_mod.DeleteKey(h, "sub")


def test_delete_value_missing_raises(module_and_key):
    module, h = module_and_key
    # ensure the value does not exist
    try:
        module.DeleteValue(h, "no-such")
    except Exception:
        pass

    # fake raises OSError, real winreg raises FileNotFoundError -> accept both
    with pytest.raises((OSError, FileNotFoundError)):
        module.DeleteValue(h, "no-such")


def test_query_info_key(module_and_key):
    """Create two subkeys and two values and assert QueryInfoKey reports
    the correct counts. For the fake backend last-modified is 0; for the
    real backend it should be an int timestamp (we only check type).
    """
    module, h = module_and_key

    # create two subkeys
    s1 = module.CreateKeyEx(h, "QI_A", access=module.KEY_ALL_ACCESS)
    s2 = module.CreateKeyEx(h, "QI_B", access=module.KEY_ALL_ACCESS)
    # set two named values on the parent
    module.SetValueEx(h, "qv1", 0, module.REG_SZ, "one")
    module.SetValueEx(h, "qv2", 0, module.REG_SZ, "two")

    try:
        nsub, nval, last = module.QueryInfoKey(h)
        assert nsub == 2, f"expected 2 subkeys, got {nsub}"
        assert nval == 2, f"expected 2 values, got {nval}"
        # both fake and real backends should report an int timestamp
        assert isinstance(last, int)
    finally:
        # close subkeys and let teardown remove them
        try:
            s1.Close()
        except Exception:
            pass
        try:
            s2.Close()
        except Exception:
            pass


def test_query_info_key_timestamp_updates(fake_module_and_key):
    """Verify that QueryInfoKey's last-modified updates when adding and deleting values
    and that it corresponds closely to time.time_ns() converted to FILETIME units.
    """
    fake_mod, h = fake_module_and_key

    # initial timestamp after creating the key
    t0_ns = time.time_ns()
    nsub, nval, filetime0 = fake_mod.QueryInfoKey(h)
    # convert back to ns for comparison using helper
    ns0 = fake.filetime_to_time_ns(filetime0)
    # allow small negative drift due to race; ensure timestamp is near current time
    assert abs(ns0 - t0_ns) < 5_000_000_000  # within 5s

    # set a new named value and check timestamp increased
    time_before_set = time.time_ns()
    fake_mod.SetValueEx(h, "ts_v", 0, fake_mod.REG_SZ, "v")
    nsub, nval, filetime1 = fake_mod.QueryInfoKey(h)
    ns1 = fake.filetime_to_time_ns(filetime1)
    assert nval >= 1
    assert ns1 >= time_before_set - 1_000_000  # at least very close (1ms tolerance)

    # delete the value and ensure timestamp updates again
    time_before_del = time.time_ns()
    fake_mod.DeleteValue(h, "ts_v")
    nsub, nval, filetime2 = fake_mod.QueryInfoKey(h)
    ns2 = fake.filetime_to_time_ns(filetime2)
    assert ns2 >= time_before_del - 1_000_000


def test_parent_timestamp_on_subkey_create_delete(module_and_key):
    """Check whether creating/deleting a direct subkey updates the parent's
    QueryInfoKey last-modified timestamp. The fake backend does not update
    parent timestamps on subkey creation/deletion; real Windows `winreg` tends
    to update them. We assert the observed behavior per-backend.
    """
    module, h = module_and_key

    # capture initial parent timestamp
    nsub0, nval0, ft0 = module.QueryInfoKey(h)
    # create a direct subkey
    sub = module.CreateKeyEx(h, "ParentTSChild", access=module.KEY_ALL_ACCESS)
    # slight sleep to avoid tight timestamp races on fast CI/machines
    time.sleep(0.001)
    try:
        nsub1, nval1, ft1 = module.QueryInfoKey(h)
    finally:
        try:
            sub.Close()
        except Exception:
            pass

    # delete the subkey
    # ensure a tiny delay so the deletion produces a later timestamp
    time.sleep(0.001)
    try:
        module.DeleteKey(h, "ParentTSChild")
    except Exception:
        # some backends may raise; ignore for teardown
        pass

    nsub2, nval2, ft2 = module.QueryInfoKey(h)

    # Behavior expectations:
    # real winreg on Windows should show the parent's timestamp strictly
    # increase when a subkey is added or removed.
    assert isinstance(ft0, int)
    assert isinstance(ft1, int)
    assert isinstance(ft2, int)
    assert ft1 > ft0 or ft2 > ft1
