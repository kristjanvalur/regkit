import sys
import uuid
from pathlib import Path

import pytest

from tests import fakewinreg

# add the package src directory to sys.path so pytest can import it
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--disable-fake-backend",
        action="store_true",
        default=False,
        help="Disable running tests with tests.fakewinreg backend.",
    )
    parser.addoption(
        "--disable-real-backend",
        action="store_true",
        default=False,
        help="Disable running tests with real winreg backend.",
    )


def _patch_backend(monkeypatch: pytest.MonkeyPatch, backend) -> None:
    monkeypatch.setitem(sys.modules, "winreg", backend)

    import src.winregkit.registry as registry_module

    monkeypatch.setattr(registry_module, "winreg", backend)


@pytest.fixture(autouse=True)
def patch_winreg(monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform == "win32":
        import winreg as backend
    else:
        backend = fakewinreg

    _patch_backend(monkeypatch, backend)


@pytest.fixture
def require_fake_winreg(request: pytest.FixtureRequest) -> None:
    if bool(request.config.getoption("--disable-fake-backend")):
        pytest.skip("Requires fake winreg backend; run without --disable-fake-backend")


@pytest.fixture
def require_real_winreg(request: pytest.FixtureRequest) -> None:
    if sys.platform != "win32":
        pytest.skip("Requires real winreg backend on Windows")
    if bool(request.config.getoption("--disable-real-backend")):
        pytest.skip("Requires real winreg backend; run without --disable-real-backend")


def _delete_subtree(key) -> None:
    try:
        with key.open(write=True) as opened:
            child_names = [sub.name for sub in opened.subkeys()]
    except KeyError:
        return

    for name in child_names:
        _delete_subtree(key.subkey(name))

    key.delete(tree=False, missing_ok=True)


@pytest.fixture
def fake_user_key(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    if bool(request.config.getoption("--disable-fake-backend")):
        pytest.skip("Fake backend disabled")

    _patch_backend(monkeypatch, fakewinreg)

    from src.winregkit.registry import Key

    suffix = uuid.uuid4().hex
    relative_parts = ("Software", "winregkit-tests", suffix)

    with Key.current_user().create(*relative_parts):
        pass

    try:
        yield Key.current_user().subkey(*relative_parts)
    finally:
        _delete_subtree(Key.current_user().subkey(*relative_parts))


@pytest.fixture
def real_user_key(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    if sys.platform != "win32":
        pytest.skip("Real registry fixture requires Windows")
    if bool(request.config.getoption("--disable-real-backend")):
        pytest.skip("Real backend disabled")

    import winreg as real_winreg

    _patch_backend(monkeypatch, real_winreg)

    from src.winregkit.registry import Key

    suffix = uuid.uuid4().hex
    relative_parts = ("Software", "winregkit-tests", suffix)

    with Key.current_user().create(*relative_parts):
        pass

    try:
        yield Key.current_user().subkey(*relative_parts)
    finally:
        _delete_subtree(Key.current_user().subkey(*relative_parts))


@pytest.fixture(params=["fake_user_key", "real_user_key"], ids=["fake", "real"])
def sandbox_key(request: pytest.FixtureRequest):
    fixture_name = request.param
    return request.getfixturevalue(fixture_name)
