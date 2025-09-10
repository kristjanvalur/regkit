import sys
from pathlib import Path

# add the package src directory to sys.path so pytest can import it
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
