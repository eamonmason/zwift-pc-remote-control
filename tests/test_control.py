"""Tests for control endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from api.models import ServiceStatus, Task, TaskStatus


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_start_zwift(client):
    """Test start Zwift endpoint."""
    with patch("api.routers.control.task_manager") as mock_task_manager:
        # Mock task creation - return a proper Task object
        test_task_id = uuid4()
        mock_task = Task(task_id=test_task_id, status=TaskStatus.PENDING, task_type="start")
        mock_task_manager.create_task.return_value = mock_task

        response = client.post("/api/v1/control/start")

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["task_id"] == str(test_task_id)
        assert "message" in data
        assert "estimated_duration_seconds" in data
        assert data["estimated_duration_seconds"] == 180


@pytest.mark.asyncio
async def test_stop_pc(client):
    """Stop returns a task ID: cutting mains can outlast any HTTP timeout."""
    with patch("api.routers.control.task_manager") as mock_task_manager:
        test_task_id = uuid4()
        mock_task = Task(task_id=test_task_id, status=TaskStatus.PENDING, task_type="stop")
        mock_task_manager.create_task.return_value = mock_task

        response = client.post("/api/v1/control/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_id"] == str(test_task_id)
        assert "estimated_duration_seconds" in data
        mock_task_manager.create_task.assert_called_once_with("stop")


@pytest.mark.asyncio
async def test_stop_pc_offline_is_not_rejected(client):
    """A PC already off the network (mid Windows Update) is not rejected.

    Ping going quiet is not proof the machine is off, and its mains still need
    cutting once the update finishes, so the sequence is scheduled either way.
    The decision to actually cut power lives in the sequence, not here.
    """
    with (
        patch("api.routers.control.task_manager") as mock_task_manager,
        patch("api.services.task_manager.ping_host") as mock_ping,
    ):
        mock_ping.return_value = (False, None)
        test_task_id = uuid4()
        mock_task = Task(task_id=test_task_id, status=TaskStatus.PENDING, task_type="stop")
        mock_task_manager.create_task.return_value = mock_task

        response = client.post("/api/v1/control/stop")

        assert response.status_code == 200
        assert response.json()["task_id"] == str(test_task_id)


@pytest.mark.asyncio
async def test_wake_pc(client):
    """Test wake PC endpoint."""
    with patch("api.routers.control.task_manager") as mock_task_manager:
        # Mock task creation - return a proper Task object
        test_task_id = uuid4()
        mock_task = Task(task_id=test_task_id, status=TaskStatus.PENDING, task_type="wake")
        mock_task_manager.create_task.return_value = mock_task

        response = client.post("/api/v1/control/wake")

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["task_id"] == str(test_task_id)
        assert "message" in data
        assert "estimated_duration_seconds" in data
        assert data["estimated_duration_seconds"] == 60


def test_get_task_not_found(client):
    """Test getting task status for non-existent task."""
    with patch("api.routers.control.task_manager") as mock_task_manager:
        mock_task_manager.get_task.return_value = None

        # Use a valid UUID format
        non_existent_uuid = uuid4()
        response = client.get(f"/api/v1/control/tasks/{non_existent_uuid}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_toggle_sunshine_stop_when_running(client):
    """Test toggle Sunshine when service is currently running (should stop)."""
    with (
        patch("api.routers.control.StatusChecker") as mock_status_checker_class,
        patch("api.routers.control.PCControlService") as mock_pc_control_class,
    ):
        # Mock PC online and SSH available
        mock_status_checker = AsyncMock()
        mock_pc_status = AsyncMock()
        mock_pc_status.online = True
        mock_pc_status.ssh_available = True
        mock_status_checker.check_pc_online = AsyncMock(return_value=mock_pc_status)

        # Mock Sunshine currently running
        mock_service_status_before = ServiceStatus(
            name="SunshineService", running=True, status="Running"
        )

        # Mock Sunshine stopped after toggle
        mock_service_status_after = ServiceStatus(
            name="SunshineService", running=False, status="Stopped"
        )

        mock_status_checker.check_sunshine_status = AsyncMock(
            side_effect=[mock_service_status_before, mock_service_status_after]
        )
        mock_status_checker_class.return_value = mock_status_checker

        # Mock PC control - stop_sunshine succeeds
        mock_pc_control = AsyncMock()
        mock_pc_control.stop_sunshine = AsyncMock(return_value=True)
        mock_pc_control_class.return_value = mock_pc_control

        response = client.post("/api/v1/control/sunshine/toggle")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "stopped" in data["message"].lower()
        assert data["service_status"]["running"] is False
        mock_pc_control.stop_sunshine.assert_called_once()


@pytest.mark.asyncio
async def test_toggle_sunshine_start_when_stopped(client):
    """Test toggle Sunshine when service is currently stopped (should start)."""
    with (
        patch("api.routers.control.StatusChecker") as mock_status_checker_class,
        patch("api.routers.control.PCControlService") as mock_pc_control_class,
    ):
        # Mock PC online and SSH available
        mock_status_checker = AsyncMock()
        mock_pc_status = AsyncMock()
        mock_pc_status.online = True
        mock_pc_status.ssh_available = True
        mock_status_checker.check_pc_online = AsyncMock(return_value=mock_pc_status)

        # Mock Sunshine currently stopped
        mock_service_status_before = ServiceStatus(
            name="SunshineService", running=False, status="Stopped"
        )

        # Mock Sunshine running after toggle
        mock_service_status_after = ServiceStatus(
            name="SunshineService", running=True, status="Running"
        )

        mock_status_checker.check_sunshine_status = AsyncMock(
            side_effect=[mock_service_status_before, mock_service_status_after]
        )
        mock_status_checker_class.return_value = mock_status_checker

        # Mock PC control - start_sunshine succeeds
        mock_pc_control = AsyncMock()
        mock_pc_control.start_sunshine = AsyncMock(return_value=True)
        mock_pc_control_class.return_value = mock_pc_control

        response = client.post("/api/v1/control/sunshine/toggle")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "started" in data["message"].lower()
        assert data["service_status"]["running"] is True
        mock_pc_control.start_sunshine.assert_called_once()


@pytest.mark.asyncio
async def test_toggle_sunshine_pc_offline(client):
    """Test toggle Sunshine when PC is offline."""
    with patch("api.routers.control.StatusChecker") as mock_status_checker_class:
        # Mock PC offline
        mock_status_checker = AsyncMock()
        mock_pc_status = AsyncMock()
        mock_pc_status.online = False
        mock_status_checker.check_pc_online = AsyncMock(return_value=mock_pc_status)
        mock_status_checker_class.return_value = mock_status_checker

        response = client.post("/api/v1/control/sunshine/toggle")

        assert response.status_code == 503
        assert "offline" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_toggle_sunshine_ssh_unavailable(client):
    """Test toggle Sunshine when SSH is unavailable."""
    with patch("api.routers.control.StatusChecker") as mock_status_checker_class:
        # Mock PC online but SSH unavailable
        mock_status_checker = AsyncMock()
        mock_pc_status = AsyncMock()
        mock_pc_status.online = True
        mock_pc_status.ssh_available = False
        mock_status_checker.check_pc_online = AsyncMock(return_value=mock_pc_status)
        mock_status_checker_class.return_value = mock_status_checker

        response = client.post("/api/v1/control/sunshine/toggle")

        assert response.status_code == 503
        assert "ssh" in response.json()["detail"].lower()
