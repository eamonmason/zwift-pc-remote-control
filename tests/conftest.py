"""Pytest configuration and fixtures for API tests."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import app


@pytest.fixture
def test_settings():
    """Create test settings with mock values."""
    return Settings(
        pc_name="test-pc",
        pc_ip="192.168.1.100",
        pc_mac="AA:BB:CC:DD:EE:FF",
        pc_user="testuser",
        api_port=8000,
        log_level="DEBUG",
        wol_timeout=10,
        ssh_timeout=10,
        desktop_timeout=10,
        zwift_timeout=10,
        ssh_key_path="/tmp/test_key",
        ssh_connect_timeout=5,
    )


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_ssh_client():
    """Create mock SSH client."""
    mock = AsyncMock()
    mock.execute = AsyncMock(return_value=("", "", 0))
    mock.execute_powershell = AsyncMock(return_value=("", "", 0))
    mock.is_available = AsyncMock(return_value=True)
    mock.wait_for_availability = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_ping_host():
    """Create mock ping_host function."""

    async def _mock_ping(ip_address: str, timeout: int = 1):
        return True, 5  # is_online, response_time_ms

    return _mock_ping


@pytest.fixture
def mock_send_wol_packet():
    """Create mock send_wol_packet function."""

    async def _mock_wol(mac_address: str):
        return True

    return _mock_wol


@pytest.fixture
def mock_wait_for_ping():
    """Create mock wait_for_ping function."""

    async def _mock_wait(ip_address: str, timeout: int = 120, check_interval: int = 2):
        return True

    return _mock_wait
