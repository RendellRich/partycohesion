"""Make the app's modules (chart_utils, flip_utils, ui) importable from the tests."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
