"""Network utilities for ping and Wake-on-LAN."""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


async def send_wol_packet(mac_address: str) -> bool:
    """
    Send Wake-on-LAN magic packet to the specified MAC address.

    Args:
        mac_address: MAC address in format XX:XX:XX:XX:XX:XX

    Returns:
        True if WoL packet was sent successfully, False otherwise
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "wakeonlan",
            mac_address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"WoL packet sent to {mac_address}")
            return True
        else:
            logger.error(f"Failed to send WoL packet: {stderr.decode().strip()}")
            return False
    except FileNotFoundError:
        logger.error("wakeonlan command not found. Install with: apt-get install wakeonlan")
        return False
    except Exception as e:
        logger.error(f"Error sending WoL packet: {e}")
        return False


async def ping_host(ip_address: str, timeout: int = 1) -> tuple[bool, Optional[int]]:
    """
    Ping a host to check if it's online.

    Args:
        ip_address: IP address to ping
        timeout: Ping timeout in seconds

    Returns:
        Tuple of (is_online, response_time_ms)
    """
    try:
        start_time = time.time()
        process = await asyncio.create_subprocess_exec(
            "ping",
            "-c",
            "1",
            "-W",
            str(timeout),
            ip_address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        elapsed_ms = int((time.time() - start_time) * 1000)

        if process.returncode == 0:
            logger.debug(f"Ping to {ip_address} successful ({elapsed_ms}ms)")
            return True, elapsed_ms
        else:
            logger.debug(f"Ping to {ip_address} failed")
            return False, None
    except Exception as e:
        logger.error(f"Error pinging {ip_address}: {e}")
        return False, None


async def wait_for_ping(ip_address: str, timeout: int = 120, check_interval: int = 2) -> bool:
    """
    Wait for a host to respond to ping.

    Args:
        ip_address: IP address to ping
        timeout: Maximum time to wait in seconds
        check_interval: Time between ping attempts in seconds

    Returns:
        True if host responded within timeout, False otherwise
    """
    logger.info(f"Waiting for {ip_address} to respond to ping (timeout: {timeout}s)...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        is_online, _ = await ping_host(ip_address)
        if is_online:
            elapsed = int(time.time() - start_time)
            logger.info(f"{ip_address} is online (took {elapsed}s)")
            return True

        await asyncio.sleep(check_interval)

    logger.warning(f"{ip_address} did not respond within {timeout}s")
    return False
