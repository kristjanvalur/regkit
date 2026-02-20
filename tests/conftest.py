import sys
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
        monkeypatch.setitem(sys.modules, "winreg", fakewinreg)


@pytest.fixture
def require_fake_winreg(using_fake_winreg: bool) -> None:
    if not using_fake_winreg:
        pytest.skip("Requires fake winreg backend; rerun with --fake-winreg on Windows")


@pytest.fixture
def require_real_winreg(using_fake_winreg: bool) -> None:
    if using_fake_winreg:
        pytest.skip("Requires real winreg backend; run without --fake-winreg")
