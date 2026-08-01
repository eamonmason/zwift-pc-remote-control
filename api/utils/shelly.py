"""Shelly Gen2 (Plus) smart plug client over plain HTTP RPC.

The plug carrying mains for the Zwift PC is a Shelly Plus with auth disabled, so
the whole device surface used here is two endpoints:

    GET http://<ip>/rpc/Switch.GetStatus?id=0
    GET http://<ip>/rpc/Switch.Set?id=0&on=<true|false>

Every function swallows transport errors and returns None/False rather than
raising: callers decide whether an unreachable plug is fatal (it is when waking,
because a de-energised PC cannot answer a WoL packet) or merely a warning (it is
when shutting down, because leaving mains on is always safer than cutting them).
"""

import asyncio
import json
import logging
import re
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Shelly Gen2 responses embed raw control characters, which choke strict JSON
# parsers — including httpx's .json(). Stripping them first is the equivalent of
# the `tr -d '\000-\037'` the cluster power scripts use for the same devices.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f]")

GET_TIMEOUT = 5.0
SET_TIMEOUT = 10.0


async def _rpc(ip_address: str, path: str, timeout: float) -> Optional[dict]:
    """
    Call a Shelly RPC endpoint and return the decoded response.

    Args:
        ip_address: Plug IP address
        path: RPC path, e.g. "Switch.GetStatus?id=0"
        timeout: Request timeout in seconds

    Returns:
        Decoded response dict, or None if the plug could not be read
    """
    url = f"http://{ip_address}/rpc/{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return json.loads(_CONTROL_CHARS.sub("", response.text))
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.debug(f"Shelly RPC {url} failed: {e}")
        return None


async def get_status(ip_address: str) -> Optional[dict]:
    """
    Read the plug's switch status.

    Args:
        ip_address: Plug IP address

    Returns:
        Status dict (contains "output" and, on metering models, "apower"),
        or None if the plug could not be read
    """
    return await _rpc(ip_address, "Switch.GetStatus?id=0", GET_TIMEOUT)


async def is_reachable(ip_address: str) -> bool:
    """
    Check whether the plug answers RPC calls.

    Args:
        ip_address: Plug IP address

    Returns:
        True if the plug responded
    """
    return await get_status(ip_address) is not None


async def get_switch_state(ip_address: str) -> Optional[bool]:
    """
    Read whether the plug's output is energised.

    Args:
        ip_address: Plug IP address

    Returns:
        True if on, False if off, None if the plug could not be read
    """
    status = await get_status(ip_address)
    if status is None:
        return None

    output = status.get("output")
    return output if isinstance(output, bool) else None


async def get_power(ip_address: str) -> Optional[float]:
    """
    Read instantaneous power draw through the plug.

    Args:
        ip_address: Plug IP address

    Returns:
        Watts, or None if the plug could not be read or does not meter
    """
    status = await get_status(ip_address)
    if status is None:
        return None

    power = status.get("apower")
    return float(power) if isinstance(power, (int, float)) else None


async def set_switch(ip_address: str, on: bool) -> bool:
    """
    Switch the plug on or off.

    This is the only mutating call in this module.

    Args:
        ip_address: Plug IP address
        on: True to energise, False to cut power

    Returns:
        True if the plug accepted the command
    """
    flag = "true" if on else "false"
    logger.info(f"Switching plug {ip_address} {'on' if on else 'off'}")
    return await _rpc(ip_address, f"Switch.Set?id=0&on={flag}", SET_TIMEOUT) is not None


async def wait_for_switch_state(
    ip_address: str, on: bool, timeout: int = 30, check_interval: int = 3
) -> bool:
    """
    Wait for the plug to report the expected switch state.

    Args:
        ip_address: Plug IP address
        on: State to wait for
        timeout: Maximum time to wait in seconds
        check_interval: Time between reads in seconds

    Returns:
        True if the plug confirmed the state within the timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        if await get_switch_state(ip_address) is on:
            return True
        await asyncio.sleep(check_interval)

    logger.warning(f"Plug {ip_address} did not report {'on' if on else 'off'} within {timeout}s")
    return False
