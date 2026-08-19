"""Put the package on the path so `pytest` works from the backend directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import pytest  # noqa: E402


@pytest.fixture(scope="session")
def artifacts_root():
    """The written artifacts. Tests that read them skip when a stage has not run."""
    return Path(__file__).resolve().parent.parent / "artifacts"
