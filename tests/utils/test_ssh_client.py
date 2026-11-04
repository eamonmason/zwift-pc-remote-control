"""Tests for how PowerShell scripts are sent over SSH."""

import base64
from unittest.mock import AsyncMock

import pytest

from api.utils.ssh_client import SSHClient


@pytest.fixture
def ssh():
    """SSHClient with `execute` mocked, so tests can inspect the command sent."""
    client = SSHClient(host="192.168.1.100", username="testuser", key_path="/tmp/test_key")
    client.execute = AsyncMock(return_value=("output", "", 0))
    return client


def sent_script(ssh) -> str:
    """Decode the script out of the command that was sent."""
    command = ssh.execute.call_args.args[0]
    return base64.b64decode(command.split()[-1]).decode("utf-16-le")


@pytest.mark.asyncio
async def test_multiline_script_is_sent_on_one_line(ssh):
    """cmd.exe stops at the first newline, which silently drops the whole script."""
    await ssh.execute_powershell("\n    Write-Output 'a'\n    Write-Output 'b'\n")

    command = ssh.execute.call_args.args[0]
    assert "\n" not in command
    assert "-EncodedCommand" in command


@pytest.mark.asyncio
async def test_script_reaches_powershell_unchanged(ssh):
    """Quotes and newlines survive, with no escaping for cmd.exe to get wrong."""
    script = """$a = "double"\n$b = 'single'\nWrite-Output "$a $b" """

    await ssh.execute_powershell(script)

    assert script in sent_script(ssh)


@pytest.mark.asyncio
async def test_progress_output_is_silenced(ssh):
    """Otherwise PowerShell writes CLIXML progress records to stderr."""
    await ssh.execute_powershell("Write-Output 'a'")

    assert sent_script(ssh).startswith("$ProgressPreference = 'SilentlyContinue'")


@pytest.mark.asyncio
async def test_timeout_and_result_are_passed_through(ssh):
    """The caller's timeout still applies and the result comes back untouched."""
    result = await ssh.execute_powershell("Write-Output 'a'", timeout=7)

    assert ssh.execute.call_args.args[1] == 7
    assert result == ("output", "", 0)
