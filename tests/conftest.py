import pytest

from bodygraph.ephemeris import JplEngine


@pytest.fixture(scope="session")
def de440():
    return JplEngine("de440")


@pytest.fixture(scope="session")
def de421():
    return JplEngine("de421")


@pytest.fixture(scope="session")
def swiss():
    """The optional Swiss Ephemeris add-on. Tests that use it are skipped
    when pyswisseph is not installed."""
    pytest.importorskip("swisseph")
    from contrib.swisseph_engine import SwissEngine
    return SwissEngine()
