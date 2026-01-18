"""Tests for status endpoints."""

from unittest.mock import AsyncMock, patch

import pytest

from api.models import PCStatus, ZwiftStatus


@pytest.mark.asyncio
async def test_get_pc_status_online(client):
    """Test PC status endpoint when PC is online."""
    with patch("api.routers.status.status_checker") as mock_checker:
        # Mock PC online with SSH available
        mock_checker.check_pc_online = AsyncMock(
            return_value=PCStatus(
                online=True,
                ssh_available=True,
                ip_address="192.168.1.194",
                response_time_ms=5,
            )
        )

        response = client.get("/api/v1/status/pc")

        assert response.status_code == 200
        data = response.json()
        assert data["online"] is True
        assert data["ssh_available"] is True
        assert data["ip_address"] == "192.168.1.194"
        assert data["response_time_ms"] == 5


@pytest.mark.asyncio
async def test_get_pc_status_offline(client):
    """Test PC status endpoint when PC is offline."""
    with patch("api.routers.status.status_checker") as mock_checker:
        # Mock PC offline
        mock_checker.check_pc_online = AsyncMock(
            return_value=PCStatus(
                online=False,
                ssh_available=False,
                ip_address="192.168.1.194",
                response_time_ms=None,
            )
        )

        response = client.get("/api/v1/status/pc")

        assert response.status_code == 200
        data = response.json()
        assert data["online"] is False
        assert data["ssh_available"] is False


@pytest.mark.asyncio
async def test_get_zwift_status_pc_offline(client):
    """Test Zwift status endpoint when PC is offline."""
    with patch("api.routers.status.status_checker") as mock_checker:
        # Mock PC offline
        mock_checker.check_pc_online = AsyncMock(
            return_value=PCStatus(
                online=False,
                ssh_available=False,
                ip_address="192.168.1.194",
                response_time_ms=None,
            )
        )

        response = client.get("/api/v1/status/zwift")

        assert response.status_code == 503
        assert "offline" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_zwift_status_ssh_unavailable(client):
    """Test Zwift status endpoint when PC is online but SSH is unavailable."""
    with patch("api.routers.status.status_checker") as mock_checker:
        # Mock PC online but SSH unavailable
        mock_checker.check_pc_online = AsyncMock(
            return_value=PCStatus(
                online=True,
                ssh_available=False,
                ip_address="192.168.1.194",
                response_time_ms=5,
            )
        )

        response = client.get("/api/v1/status/zwift")

        assert response.status_code == 503
        assert "ssh" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_zwift_status_running(client):
    """Test Zwift status endpoint when Zwift is running."""
    with patch("api.routers.status.status_checker") as mock_checker:
        # Mock PC online with SSH available
        mock_checker.check_pc_online = AsyncMock(
            return_value=PCStatus(
                online=True,
                ssh_available=True,
                ip_address="192.168.1.194",
                response_time_ms=5,
            )
        )

        # Mock Zwift running
        mock_checker.check_zwift_running = AsyncMock(
            return_value=ZwiftStatus(
                running=True,
                process_id=12345,
                cpu_usage=4500.0,
                memory_mb=1024,
            )
        )

        response = client.get("/api/v1/status/zwift")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        assert data["process_id"] == 12345
        assert data["cpu_usage"] == 4500.0
        assert data["memory_mb"] == 1024


@pytest.mark.asyncio
async def test_get_full_status(client):
    """Test full status endpoint."""
    with patch("api.routers.status.status_checker") as mock_checker:
        # Mock full status
        from api.models import FullStatus, ServiceStatus

        mock_checker.check_full_status = AsyncMock(
            return_value=FullStatus(
                pc=PCStatus(
                    online=True,
                    ssh_available=True,
                    ip_address="192.168.1.194",
                    response_time_ms=5,
                ),
                zwift=ZwiftStatus(
                    running=True,
                    process_id=12345,
                ),
                sunshine=ServiceStatus(
                    name="SunshineService",
                    running=False,
                    status="Stopped",
                ),
                obs=ZwiftStatus(running=False),
            )
        )

        response = client.get("/api/v1/status/full")

        assert response.status_code == 200
        data = response.json()
        assert data["pc"]["online"] is True
        assert data["pc"]["ssh_available"] is True
        assert data["zwift"]["running"] is True
        assert data["sunshine"]["running"] is False
