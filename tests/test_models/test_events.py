import numpy as np
import pytest

from hyptraj.models.parameters import EnvironmentParams
from hyptraj.simulation.events import make_ground_event


def test_ground_event_is_zero_at_sea_level():
    env = EnvironmentParams()
    event = make_ground_event(env)

    state = np.array([env.earth_radius, 0.0, 1000.0, 0.0])

    assert event(0.0, state) == pytest.approx(0.0, abs=1e-12)


def test_ground_event_is_positive_above_sea_level():
    env = EnvironmentParams()
    event = make_ground_event(env)

    state = np.array([env.earth_radius + 1000.0, 0.0, 1000.0, 0.0])

    assert event(0.0, state) > 0.0


def test_ground_event_is_terminal_descending():
    env = EnvironmentParams()
    event = make_ground_event(env)

    assert event.terminal is True
    assert event.direction == -1
