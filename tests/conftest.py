import sys
from pathlib import Path

import pytest

from tests import fakewinreg

# add the package src directory to sys.path so pytest can import it
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def patch_winreg_on_non_windows(monkeypatch):
    if sys.platform != "win32":
        monkeypatch.setitem(sys.modules, "winreg", fakewinreg)
