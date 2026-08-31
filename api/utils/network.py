"""Network utilities for ping and Wake-on-LAN."""

import asyncio
import logging
import socket
import time
from typing import Optional

logger = logging.getLogger(__name__)


async def send_wol_packet(mac_address: str, target_ip: str = "") -> bool:
    """
    Send Wake-on-LAN magic packet to the specified MAC address.

    Uses a directed subnet broadcast (x.x.x.255) bound to the node's LAN IP
    so the packet reaches the physical wire even under Cilium eBPF.
    Limited broadcast (255.255.255.255) is dropped by Cilium with hostNetwork pods.

    Args:
        mac_address: MAC address in format XX:XX:XX:XX:XX:XX
        target_ip:   IP of target PC — used to discover which local interface to bind.
                     Falls back to INADDR_ANY if not provided.

    Returns:
        True if WoL packet was sent successfully, False otherwise
    """
    try:
        mac_bytes = bytes.fromhex(mac_address.replace(":", "").replace("-", ""))
        magic = b"\xff" * 6 + mac_bytes * 16

        local_ip = ""
        if target_ip:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                    probe.connect((target_ip, 9))
                    local_ip = probe.getsockname()[0]
            except Exception:
                pass

        if local_ip and local_ip != "0.0.0.0":
            broadcast = ".".join(local_ip.split(".")[:3]) + ".255"
        else:
            broadcast = "255.255.255.255"
            local_ip = ""

        # Tracked separately from local_ip itself so the log line below never
        # reads the address (CodeQL flags any use of it as clear-text logging
        # of private data, even a truthiness check).
        bound_to_interface = bool(local_ip)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            if local_ip:
                sock.bind((local_ip, 0))
            sock.sendto(magic, (broadcast, 9))

        broadcast_mode = "directed subnet broadcast" if bound_to_interface else "limited broadcast"
        bind_mode = "bound to source interface" if bound_to_interface else "INADDR_ANY"
        logger.info(f"WoL packet sent to {mac_address} via {broadcast_mode} ({bind_mode})")
        return True

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
