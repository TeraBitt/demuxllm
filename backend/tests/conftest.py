"""Put the package on the path so `pytest` works from the backend directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
