"""Tests for friends API routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# API tests - friends endpoints
pytestmark = pytest.mark.api

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_user_manager():
    """Mock UserManager."""
    with patch("src.api.routers.friends.get_user_manager") as mock:
        manager = MagicMock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def auth_headers():
    """Create auth headers."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_auth():
    """Mock authentication."""
    with patch("src.api.deps.decode_token") as mock:
        mock.return_value = 1
        yield mock


class TestSendFriendRequest:
    """Tests for POST /api/friends/request."""

    def test_send_request_success(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test sending a friend request."""
        mock_user_manager.send_friend_request.return_value = "请求已发送"

        response = client.post(
            "/api/friends/request",
            json={"to_public_id": "ABC123"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "请求已发送" in data["message"]

    def test_send_request_to_self(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test sending request to self."""
        mock_user_manager.send_friend_request.return_value = "不能添加自己为好友"

        response = client.post(
            "/api/friends/request",
            json={"to_public_id": "OWN123"},
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_send_request_already_friends(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test sending request to existing friend."""
        mock_user_manager.send_friend_request.return_value = "已经是好友了"

        response = client.post(
            "/api/friends/request",
            json={"to_public_id": "FRIEND123"},
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_send_request_user_not_found(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test sending request to non-existent user."""
        mock_user_manager.send_friend_request.return_value = "Error: User not found"

        response = client.post(
            "/api/friends/request",
            json={"to_public_id": "INVALID123"},
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_send_request_no_auth(self, client):
        """Test sending request without authentication."""
        response = client.post("/api/friends/request", json={"to_public_id": "ABC123"})

        assert response.status_code == 401

    def test_send_request_empty_public_id(self, client, mock_auth, auth_headers):
        """Test sending request with empty public ID."""
        response = client.post(
            "/api/friends/request", json={"to_public_id": ""}, headers=auth_headers
        )

        assert response.status_code == 422


class TestRespondToRequest:
    """Tests for POST /api/friends/respond."""

    def test_accept_request_success(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test accepting a friend request."""
        mock_user_manager.respond_to_friend_request.return_value = "已接受好友请求"

        response = client.post(
            "/api/friends/respond",
            json={"request_id": 1, "accept": True},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "已接受" in response.json()["message"]

    def test_reject_request_success(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test rejecting a friend request."""
        mock_user_manager.respond_to_friend_request.return_value = "已拒绝好友请求"

        response = client.post(
            "/api/friends/respond",
            json={"request_id": 1, "accept": False},
            headers=auth_headers,
        )

        assert response.status_code == 200

    def test_respond_unauthorized(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test responding to request not owned by user."""
        mock_user_manager.respond_to_friend_request.return_value = "无权操作此请求"

        response = client.post(
            "/api/friends/respond",
            json={"request_id": 999, "accept": True},
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_respond_no_auth(self, client):
        """Test responding without authentication."""
        response = client.post("/api/friends/respond", json={"request_id": 1, "accept": True})

        assert response.status_code == 401


class TestGetFriends:
    """Tests for GET /api/friends."""

    def test_get_friends_success(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test getting friends list."""
        mock_user_manager.get_friends.return_value = [
            {"user_id": 2, "public_id": "ABC123", "display_name": "Friend1"},
            {"user_id": 3, "public_id": "DEF456", "display_name": "Friend2"},
        ]

        response = client.get("/api/friends", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["display_name"] == "Friend1"

    def test_get_friends_empty(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test getting empty friends list."""
        mock_user_manager.get_friends.return_value = []

        response = client.get("/api/friends", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_get_friends_no_auth(self, client):
        """Test getting friends without authentication."""
        response = client.get("/api/friends")
        assert response.status_code == 401


class TestGetPendingRequests:
    """Tests for GET /api/friends/requests."""

    def test_get_pending_requests_success(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test getting pending friend requests."""
        mock_user_manager.get_pending_friend_requests.return_value = [
            {
                "request_id": 1,
                "from_user_id": 2,
                "from_public_id": "ABC123",
                "from_display_name": "Someone",
                "created_at": "2024-01-01T12:00:00",
            }
        ]

        response = client.get("/api/friends/requests", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["request_id"] == 1
        assert data[0]["from_user"]["public_id"] == "ABC123"

    def test_get_pending_requests_empty(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test getting empty pending requests."""
        mock_user_manager.get_pending_friend_requests.return_value = []

        response = client.get("/api/friends/requests", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_get_pending_requests_no_auth(self, client):
        """Test getting requests without authentication."""
        response = client.get("/api/friends/requests")
        assert response.status_code == 401


class TestRemoveFriend:
    """Tests for DELETE /api/friends/{friend_user_id}."""

    def test_remove_friend_success(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test removing a friend."""
        mock_user_manager.remove_friend.return_value = True

        response = client.delete("/api/friends/2", headers=auth_headers)

        assert response.status_code == 200
        assert "removed" in response.json()["message"].lower()

    def test_remove_friend_not_found(self, client, mock_user_manager, mock_auth, auth_headers):
        """Test removing non-existent friend."""
        mock_user_manager.remove_friend.return_value = False

        response = client.delete("/api/friends/999", headers=auth_headers)

        assert response.status_code == 404

    def test_remove_friend_no_auth(self, client):
        """Test removing friend without authentication."""
        response = client.delete("/api/friends/2")
        assert response.status_code == 401
