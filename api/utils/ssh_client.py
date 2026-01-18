"""Async SSH client wrapper using asyncssh."""

import asyncio
import logging
import os
import time

import asyncssh

logger = logging.getLogger(__name__)


class SSHClient:
    """Async SSH client for remote command execution."""

    def __init__(
        self,
        host: str,
        username: str,
        key_path: str = "~/.ssh/id_rsa",
        connect_timeout: int = 10,
    ):
        """
        Initialize SSH client.

        Args:
            host: Remote host IP or hostname
            username: SSH username
            key_path: Path to SSH private key
            connect_timeout: Connection timeout in seconds
        """
        self.host = host
        self.username = username
        self.key_path = os.path.expanduser(key_path)
        self.connect_timeout = connect_timeout

    async def execute(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
        """
        Execute a command via SSH.

        Args:
            command: Command to execute
            timeout: Command execution timeout in seconds

        Returns:
            Tuple of (stdout, stderr, return_code)

        Raises:
            asyncssh.Error: If SSH connection or command execution fails
        """
        try:
            # SECURITY WARNING: Host key verification is DISABLED
            # This makes the connection vulnerable to Man-in-the-Middle attacks.
            # Acceptable ONLY because:
            # 1. Local network environment (home LAN)
            # 2. Static IP reduces spoofing risk
            # 3. SSH public key authentication (not password)
            # For production: Enable host key verification
            async with asyncssh.connect(
                self.host,
                username=self.username,
                client_keys=[self.key_path],
                known_hosts=None,  # Disable host key checking (local network)
                connect_timeout=self.connect_timeout,
            ) as conn:
                logger.debug(f"Executing SSH command: {command[:100]}...")
                result = await asyncio.wait_for(conn.run(command, check=False), timeout=timeout)

                stdout = result.stdout.strip() if result.stdout else ""
                stderr = result.stderr.strip() if result.stderr else ""
                return_code = result.exit_status if result.exit_status is not None else -1

                if return_code != 0:
                    logger.warning(f"SSH command failed (exit {return_code}): {stderr}")
                else:
                    logger.debug("SSH command successful")

                return stdout, stderr, return_code

        except asyncio.TimeoutError:
            logger.error(f"SSH command timed out after {timeout}s")
            raise
        except asyncssh.Error as e:
            logger.error(f"SSH error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error executing SSH command: {e}")
            raise

    async def execute_powershell(self, script: str, timeout: int = 30) -> tuple[str, str, int]:
        """
        Execute a PowerShell script via SSH.

        Args:
            script: PowerShell script to execute
            timeout: Command execution timeout in seconds

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        # Escape quotes and wrap in powershell command
        escaped_script = script.replace('"', '\\"')
        command = f'powershell -command "{escaped_script}"'
        return await self.execute(command, timeout)

    async def is_available(self) -> bool:
        """
        Check if SSH is available on the host.

        Returns:
            True if SSH connection succeeds, False otherwise
        """
        try:
            # SECURITY WARNING: Host key verification is DISABLED
            # This makes the connection vulnerable to Man-in-the-Middle attacks.
            # Acceptable ONLY because:
            # 1. Local network environment (home LAN)
            # 2. Static IP reduces spoofing risk
            # 3. SSH public key authentication (not password)
            # For production: Enable host key verification
            async with asyncssh.connect(
                self.host,
                username=self.username,
                client_keys=[self.key_path],
                known_hosts=None,  # Disable host key checking (local network)
                connect_timeout=self.connect_timeout,
            ) as conn:
                # Just test connection
                await conn.run("echo test", check=False)
                logger.debug(f"SSH connection to {self.host} successful")
                return True
        except Exception as e:
            logger.debug(f"SSH not available on {self.host}: {e}")
            return False

    async def wait_for_availability(self, timeout: int = 60, check_interval: int = 2) -> bool:
        """
        Wait for SSH to become available.

        Args:
            timeout: Maximum time to wait in seconds
            check_interval: Time between connection attempts in seconds

        Returns:
            True if SSH became available within timeout, False otherwise
        """
        logger.info(f"Waiting for SSH on {self.host} (timeout: {timeout}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if await self.is_available():
                elapsed = int(time.time() - start_time)
                logger.info(f"SSH available on {self.host} (took {elapsed}s)")
                return True

            await asyncio.sleep(check_interval)

        logger.warning(f"SSH did not become available within {timeout}s")
        return False
