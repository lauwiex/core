"""Setup some common test helper things."""
import asyncio
import functools
import logging
import os
from unittest.mock import patch, MagicMock

import pytest
import requests_mock as _requests_mock

from homeassistant import util, setup
from homeassistant.util import location
from homeassistant.components import mqtt

from .common import async_test_home_assistant, mock_coro
from .test_util.aiohttp import mock_aiohttp_client
from .mock.zwave import SIGNAL_VALUE_CHANGED, SIGNAL_NODE, SIGNAL_NOTIFICATION

if os.environ.get('UVLOOP') == '1':
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


def test_real(func):
    """Force a function to require a keyword _test_real to be passed in."""
    @functools.wraps(func)
    def guard_func(*args, **kwargs):
        real = kwargs.pop('_test_real', None)

        if not real:
            raise Exception('Forgot to mock or pass "_test_real=True" to %s',
                            func.__name__)

        return func(*args, **kwargs)

    return guard_func


# Guard a few functions that would make network connections
location.detect_location_info = test_real(location.detect_location_info)
location.elevation = test_real(location.elevation)
util.get_local_ip = lambda: '127.0.0.1'


@pytest.fixture(autouse=True)
def verify_cleanup():
    """Verify that the test has cleaned up resources correctly."""
    yield

    from tests import common
    assert common.INST_COUNT < 2


@pytest.fixture
def hass(loop):
    """Fixture to provide a test instance of HASS."""
    hass = loop.run_until_complete(async_test_home_assistant(loop))

    yield hass

    loop.run_until_complete(hass.async_stop())


@pytest.fixture
def requests_mock():
    """Fixture to provide a requests mocker."""
    with _requests_mock.mock() as m:
        yield m


@pytest.fixture
def aioclient_mock():
    """Fixture to mock aioclient calls."""
    with mock_aiohttp_client() as mock_session:
        yield mock_session


@pytest.fixture
def mqtt_mock(loop, hass):
    """Fixture to mock MQTT."""
    with patch('homeassistant.components.mqtt.MQTT') as mock_mqtt:
        mock_mqtt().async_connect.return_value = mock_coro(True)
        assert loop.run_until_complete(setup.async_setup_component(
            hass, mqtt.DOMAIN, {
                mqtt.DOMAIN: {
                    mqtt.CONF_BROKER: 'mock-broker',
                }
            }))
        client = mock_mqtt()
        client.reset_mock()
        return client


@pytest.fixture
def mock_openzwave():
    """Mock out Open Z-Wave."""
    base_mock = MagicMock()
    libopenzwave = base_mock.libopenzwave
    libopenzwave.__file__ = 'test'
    base_mock.network.ZWaveNetwork.SIGNAL_VALUE_CHANGED = SIGNAL_VALUE_CHANGED
    base_mock.network.ZWaveNetwork.SIGNAL_NODE = SIGNAL_NODE
    base_mock.network.ZWaveNetwork.SIGNAL_NOTIFICATION = SIGNAL_NOTIFICATION

    with patch.dict('sys.modules', {
        'libopenzwave': libopenzwave,
        'openzwave.option': base_mock.option,
        'openzwave.network': base_mock.network,
        'openzwave.group': base_mock.group,
    }):
        yield base_mock
