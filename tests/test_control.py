"""Tests for control endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from api.models import Task, TaskStatus


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
async def test_stop_pc_offline(client):
    """Test stop endpoint when PC is offline."""
    with patch("api.routers.control.ping_host") as mock_ping:
        # Mock PC offline
        mock_ping.return_value = (False, None)

        response = client.post("/api/v1/control/stop")

        assert response.status_code == 400
        assert "not online" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stop_pc_online(client):
    """Test stop endpoint when PC is online."""
    with (
        patch("api.routers.control.ping_host") as mock_ping,
        patch("api.routers.control.PCControlService") as mock_pc_control,
    ):
        # Mock PC online
        mock_ping.return_value = (True, 5)

        # Mock shutdown success
        mock_service = AsyncMock()
        mock_service.shutdown_pc = AsyncMock(return_value=True)
        mock_pc_control.return_value = mock_service

        response = client.post("/api/v1/control/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "shutdown" in data["message"].lower()


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
