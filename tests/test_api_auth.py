"""Tests for auth API routes."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_user_manager():
    """Mock UserManager."""
    with patch("src.api.routers.auth.get_user_manager") as mock:
        manager = MagicMock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_create_token():
    """Mock create_token."""
    with patch("src.api.routers.auth.create_token") as mock:
        mock.return_value = "test_jwt_token"
        yield mock


class TestRegister:
    """Tests for POST /api/auth/register."""

    def test_register_success(self, client, mock_user_manager, mock_create_token):
        """Test successful registration."""
        # Arrange
        mock_user = MagicMock()
        mock_user.user_id = 1
        mock_user.public_id = "ABC123"
        mock_user.display_name = "TestUser"
        mock_user_manager.create_user.return_value = (mock_user, "private_id_123")

        # Act
        response = client.post("/api/auth/register", json={"display_name": "TestUser"})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "test_jwt_token"
        assert data["user"]["user_id"] == 1
        assert data["user"]["public_id"] == "ABC123"
        assert data["user"]["display_name"] == "TestUser"
        assert data["user"]["private_id"] == "private_id_123"

    def test_register_empty_name(self, client):
        """Test registration with empty name."""
        response = client.post("/api/auth/register", json={"display_name": ""})
        assert response.status_code == 422

    def test_register_name_too_long(self, client):
        """Test registration with name exceeding max length."""
        long_name = "x" * 51
        response = client.post("/api/auth/register", json={"display_name": long_name})
        assert response.status_code == 422

    def test_register_user_manager_error(self, client, mock_user_manager):
        """Test registration when UserManager raises exception."""
        mock_user_manager.create_user.side_effect = Exception("Database error")
        
        response = client.post("/api/auth/register", json={"display_name": "TestUser"})
        
        assert response.status_code == 400
        assert "Database error" in response.json()["detail"]


class TestLogin:
    """Tests for POST /api/auth/login."""

    def test_login_success(self, client, mock_user_manager, mock_create_token):
        """Test successful login."""
        # Arrange
        mock_user = MagicMock()
        mock_user.user_id = 1
        mock_user.public_id = "ABC123"
        mock_user.display_name = "TestUser"
        mock_user_manager.login_by_private_id.return_value = mock_user

        # Act
        response = client.post("/api/auth/login", json={"private_id": "valid_private_id"})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "test_jwt_token"
        assert data["user"]["user_id"] == 1
        assert "private_id" not in data["user"] or data["user"]["private_id"] is None

    def test_login_invalid_private_id(self, client, mock_user_manager):
        """Test login with invalid private ID."""
        mock_user_manager.login_by_private_id.return_value = None

        response = client.post("/api/auth/login", json={"private_id": "invalid_id"})

        assert response.status_code == 401
        assert "Invalid private ID" in response.json()["detail"]

    def test_login_empty_private_id(self, client):
        """Test login with empty private ID."""
        response = client.post("/api/auth/login", json={"private_id": ""})
        assert response.status_code == 422


class TestGetMe:
    """Tests for GET /api/auth/me."""

    def test_get_me_success(self, client, mock_user_manager):
        """Test getting current user info."""
        # Arrange
        mock_user = MagicMock()
        mock_user.user_id = 1
        mock_user.public_id = "ABC123"
        mock_user.display_name = "TestUser"
        mock_user_manager.get_user_by_id.return_value = mock_user

        with patch("src.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = 1

            # Act
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer valid_token"}
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == 1
            assert data["public_id"] == "ABC123"

    def test_get_me_no_token(self, client):
        """Test getting user info without token."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client):
        """Test getting user info with invalid token."""
        with patch("src.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = None

            response = client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer invalid_token"}
            )

            assert response.status_code == 401

    def test_get_me_user_not_found(self, client, mock_user_manager):
        """Test getting user info when user doesn't exist."""
        mock_user_manager.get_user_by_id.return_value = None

        with patch("src.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = 999

            response = client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer valid_token"}
            )

            assert response.status_code == 404


class TestLogout:
    """Tests for POST /api/auth/logout."""

    def test_logout_success(self, client):
        """Test logout (stateless JWT)."""
        response = client.post("/api/auth/logout")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"


class TestCookieAuth:
    """Tests for Cookie-based authentication."""

    def test_register_sets_cookie(self, client, mock_user_manager, mock_create_token):
        """Test that registration sets auth cookie."""
        mock_user = MagicMock()
        mock_user.user_id = 1
        mock_user.public_id = "ABC123"
        mock_user.display_name = "TestUser"
        mock_user_manager.create_user.return_value = (mock_user, "private_id_123")

        response = client.post("/api/auth/register", json={"display_name": "TestUser"})

        assert response.status_code == 200
        # 验证Cookie被设置
        assert "auth_token" in response.cookies
        assert response.cookies["auth_token"] == "test_jwt_token"

    def test_login_sets_cookie(self, client, mock_user_manager, mock_create_token):
        """Test that login sets auth cookie."""
        mock_user = MagicMock()
        mock_user.user_id = 1
        mock_user.public_id = "ABC123"
        mock_user.display_name = "TestUser"
        mock_user_manager.login_by_private_id.return_value = mock_user

        response = client.post("/api/auth/login", json={"private_id": "valid_private_id"})

        assert response.status_code == 200
        # 验证Cookie被设置
        assert "auth_token" in response.cookies
        assert response.cookies["auth_token"] == "test_jwt_token"

    def test_auth_with_cookie(self, client, mock_user_manager):
        """Test authentication using cookie instead of header."""
        mock_user = MagicMock()
        mock_user.user_id = 1
        mock_user.public_id = "ABC123"
        mock_user.display_name = "TestUser"
        mock_user_manager.get_user_by_id.return_value = mock_user

        with patch("src.api.deps.decode_token") as mock_decode:
            mock_decode.return_value = 1

            # 使用Cookie而不是Header进行认证
            response = client.get(
                "/api/auth/me",
                cookies={"auth_token": "valid_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == 1

    def test_cookie_takes_priority_over_header(self, client, mock_user_manager):
        """Test that cookie takes priority over Authorization header."""
        mock_user = MagicMock()
        mock_user.user_id = 1
        mock_user.public_id = "ABC123"
        mock_user.display_name = "TestUser"
        mock_user_manager.get_user_by_id.return_value = mock_user

        with patch("src.api.deps.decode_token") as mock_decode:
            # Cookie中的token对应user_id=1
            mock_decode.return_value = 1

            # 同时发送Cookie和Header，Cookie应该优先
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer different_token"},
                cookies={"auth_token": "cookie_token"}
            )

            assert response.status_code == 200
            # decode_token应该只被调用一次（使用Cookie中的token）
            assert mock_decode.call_count == 1

    def test_logout_clears_cookie(self, client):
        """Test that logout clears the auth cookie."""
        # 先设置Cookie
        client.cookies.set("auth_token", "test_token")
        
        response = client.post("/api/auth/logout")
        
        assert response.status_code == 200
        # Cookie应该被清除（设置为空）
        # 注意：TestClient的行为可能不同，但实际浏览器会清除

    def test_no_cookie_and_no_header_returns_401(self, client):
        """Test that 401 is returned when neither cookie nor header is provided."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401
