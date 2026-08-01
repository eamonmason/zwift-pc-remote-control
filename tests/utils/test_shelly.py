"""Tests for the Shelly Gen2 plug client."""

from unittest.mock import patch

import httpx
import pytest

from api.utils import shelly

PLUG_IP = "192.168.1.175"

# A realistic Gen2 Switch.GetStatus body. Note the embedded control characters:
# real plugs emit these and they break strict JSON parsing unless stripped.
STATUS_ON = '{"id":0,\x00"source":"HTTP_in","output":true,\x1f"apower":63.4,"voltage":242.1}'
STATUS_OFF = '{"id":0,"source":"HTTP_in","output":false,"apower":0.8,"voltage":242.1}'


def mock_shelly(handler):
    """Patch httpx.AsyncClient so RPC calls hit the given handler instead of the LAN."""
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    return patch("api.utils.shelly.httpx.AsyncClient", factory)


def responder(text: str, status_code: int = 200):
    """Build a handler returning a fixed body, recording the URLs it was called with."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(status_code, text=text)

    return handler, calls


@pytest.mark.asyncio
async def test_get_status_strips_control_characters():
    """Control characters in the response body must not break parsing."""
    handler, calls = responder(STATUS_ON)

    with mock_shelly(handler):
        status = await shelly.get_status(PLUG_IP)

    assert status == {
        "id": 0,
        "source": "HTTP_in",
        "output": True,
        "apower": 63.4,
        "voltage": 242.1,
    }
    assert calls == [f"http://{PLUG_IP}/rpc/Switch.GetStatus?id=0"]


@pytest.mark.asyncio
async def test_get_switch_state_on_and_off():
    """Switch state is read from the "output" field."""
    handler, _ = responder(STATUS_ON)
    with mock_shelly(handler):
        assert await shelly.get_switch_state(PLUG_IP) is True

    handler, _ = responder(STATUS_OFF)
    with mock_shelly(handler):
        assert await shelly.get_switch_state(PLUG_IP) is False


@pytest.mark.asyncio
async def test_get_power_reads_apower():
    """Power draw is read from the "apower" field."""
    handler, _ = responder(STATUS_ON)

    with mock_shelly(handler):
        assert await shelly.get_power(PLUG_IP) == 63.4


@pytest.mark.asyncio
async def test_get_power_none_when_not_metered():
    """A plug that does not report apower yields None rather than a bogus zero."""
    handler, _ = responder('{"id":0,"output":true}')

    with mock_shelly(handler):
        assert await shelly.get_power(PLUG_IP) is None


@pytest.mark.asyncio
async def test_unreachable_plug_returns_none():
    """Transport errors are swallowed - callers decide whether that is fatal."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    with mock_shelly(handler):
        assert await shelly.get_status(PLUG_IP) is None
        assert await shelly.get_switch_state(PLUG_IP) is None
        assert await shelly.get_power(PLUG_IP) is None
        assert await shelly.is_reachable(PLUG_IP) is False
        assert await shelly.set_switch(PLUG_IP, True) is False


@pytest.mark.asyncio
async def test_http_error_treated_as_unreachable():
    """A non-2xx response is not a usable reading."""
    handler, _ = responder("unauthorized", status_code=401)

    with mock_shelly(handler):
        assert await shelly.get_status(PLUG_IP) is None


@pytest.mark.asyncio
async def test_malformed_json_treated_as_unreachable():
    """A body that is not JSON at all must not raise out of the client."""
    handler, _ = responder("<html>captive portal</html>")

    with mock_shelly(handler):
        assert await shelly.get_status(PLUG_IP) is None


@pytest.mark.asyncio
async def test_set_switch_builds_expected_urls():
    """Switch.Set is called with a lowercase boolean, as the device expects."""
    handler, calls = responder('{"was_on":false}')

    with mock_shelly(handler):
        assert await shelly.set_switch(PLUG_IP, True) is True
        assert await shelly.set_switch(PLUG_IP, False) is True

    assert calls == [
        f"http://{PLUG_IP}/rpc/Switch.Set?id=0&on=true",
        f"http://{PLUG_IP}/rpc/Switch.Set?id=0&on=false",
    ]


@pytest.mark.asyncio
async def test_wait_for_switch_state_returns_when_confirmed():
    """Waiting stops as soon as the plug reports the expected state."""
    bodies = [STATUS_OFF, STATUS_OFF, STATUS_ON]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=bodies.pop(0) if bodies else STATUS_ON)

    with mock_shelly(handler), patch("api.utils.shelly.asyncio.sleep") as mock_sleep:
        assert await shelly.wait_for_switch_state(PLUG_IP, True, timeout=30, check_interval=3)

    assert mock_sleep.await_count == 2


@pytest.mark.asyncio
async def test_wait_for_switch_state_times_out():
    """A plug stuck in the wrong state fails the wait rather than hanging forever."""
    handler, _ = responder(STATUS_OFF)

    with mock_shelly(handler), patch("api.utils.shelly.asyncio.sleep"):
        confirmed = await shelly.wait_for_switch_state(PLUG_IP, True, timeout=0, check_interval=3)

    assert confirmed is False
