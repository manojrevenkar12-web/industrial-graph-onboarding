import warnings

import pytest

from igo.lab import simulate


@pytest.fixture(scope="session")
def plant():
    return simulate.plant("dev", 11)


@pytest.fixture(scope="session")
def onboarded():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return simulate.onboard("dev", 11, "platform", simulate.designs()["platform"])
