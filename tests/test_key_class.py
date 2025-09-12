import time

import pytest

from tests import fakewinreg as fake

import importlib


@pytest.fixture(autouse=True)
def monkey_winreg(monkeypatch):
    """Monkeypatch the winreg module used by winregkit to the fake implementation."""
    # ensure winregkit.registry imports the fake winreg
    import src.winregkit.registry as registry_module  # typed import for reloading

    # patch the module-level winreg reference
    monkeypatch.setattr(registry_module, "winreg", fake)

    # rebuild root_keys mapping inside the registry module
    # clear and re-populate
    registry_module.root_keys.clear()
    for key, val in getattr(fake, "__dict__", {}).items():
        if key.startswith("HKEY_"):
            registry_module.root_keys[val] = key

    yield


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
    with root.opened("UnitTest") as k2:
        assert k2["alpha"] == "A"
        assert k2.value_get("beta")[0] == 2

    # test deletion of value
    # open for write to allow deletion
    with root.opened("UnitTest", write=True) as k3:
        del k3["alpha"]
        with pytest.raises(KeyError):
            _ = k3["alpha"]

    # cleanup: reset fake registry to avoid relying on Key.delete tree behavior
    fake.reset()
    sub = root.subkey("UnitTest")
    assert not sub.exists()


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
