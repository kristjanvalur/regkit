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
        "--fake-winreg",
        action="store_true",
        default=False,
        help="Use tests.fakewinreg as winreg on Windows too.",
    )


@pytest.fixture
def using_fake_winreg(request: pytest.FixtureRequest) -> bool:
    return sys.platform != "win32" or bool(request.config.getoption("--fake-winreg"))


@pytest.fixture(autouse=True)
def patch_winreg(monkeypatch: pytest.MonkeyPatch, using_fake_winreg: bool) -> None:
    if using_fake_winreg:
        backend = fakewinreg
    else:
        import winreg as backend

    monkeypatch.setitem(sys.modules, "winreg", backend)

    import src.winregkit.registry as registry_module

    monkeypatch.setattr(registry_module, "winreg", backend)


@pytest.fixture
def require_fake_winreg(using_fake_winreg: bool) -> None:
    if not using_fake_winreg:
        pytest.skip("Requires fake winreg backend; rerun with --fake-winreg on Windows")


@pytest.fixture
def require_real_winreg(using_fake_winreg: bool) -> None:
    if using_fake_winreg:
        pytest.skip("Requires real winreg backend; run without --fake-winreg")


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
def fake_user_key(using_fake_winreg: bool):
    if not using_fake_winreg:
        pytest.skip("Fake registry fixture requires fake backend")

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
def real_user_key(using_fake_winreg: bool):
    if sys.platform != "win32":
        pytest.skip("Real registry fixture requires Windows")
    if using_fake_winreg:
        pytest.skip("Real registry fixture requires real winreg backend")

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
    return request.getfixturevalue(request.param)
