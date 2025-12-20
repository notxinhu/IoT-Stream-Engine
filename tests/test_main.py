"""Tests for the main application module."""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, lifespan


class TestMainApp:
    """Test cases for main application."""

    def test_root_endpoint(self):
        """Test root endpoint."""
        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        assert response.json() == {"message": "Welcome to the IoT Stream Engine API"}

    def test_health_check(self):
        """Test health check endpoint."""
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    @patch("app.main.IoTService.get_all_devices")
    def test_get_devices_success(self, mock_get_devices):
        """Test successful devices retrieval."""
        mock_get_devices.return_value = ["device_1", "device_2"]

        client = TestClient(app)
        response = client.get(
            "/devices", headers={"Authorization": "Bearer demo-api-key-123"}
        )

        assert response.status_code == 200
        assert response.json() == ["device_1", "device_2"]
        mock_get_devices.assert_called_once()

    @patch("app.main.IoTService.get_all_devices")
    def test_get_devices_exception(self, mock_get_devices):
        """Test devices retrieval with exception."""
        mock_get_devices.side_effect = Exception("Database error")

        client = TestClient(app)
        response = client.get(
            "/devices", headers={"Authorization": "Bearer demo-api-key-123"}
        )

        assert response.status_code == 500
        assert "Error retrieving devices" in response.json()["detail"]

    # Moving average tests removed as they are specific to telemetry endpoints now
    # and require more complex mocking of the database logic which is covered in test_api_telemetry.py

    @pytest.mark.asyncio
    async def test_lifespan_success(self):
        """Test successful application lifespan."""
        mock_app = Mock()

        async with lifespan(mock_app):
            pass

        # Should not raise any exceptions

    @pytest.mark.asyncio
    async def test_lifespan_with_exception(self):
        """Test application lifespan with exception."""
        mock_app = Mock()

        with pytest.raises(RuntimeError):
            async with lifespan(mock_app):
                raise RuntimeError("Test error")

    def test_cors_middleware(self):
        """Test CORS middleware is configured."""
        client = TestClient(app)

        # Test preflight request
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        # Should not fail due to CORS
        assert response.status_code in [200, 405]  # 405 is also acceptable for OPTIONS

    def test_api_documentation_endpoints(self):
        """Test API documentation endpoints."""
        client = TestClient(app)

        # Test OpenAPI docs
        response = client.get("/docs")
        assert response.status_code == 200

        # Test OpenAPI JSON
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_router_inclusion(self):
        """Test that routers are properly included."""
        client = TestClient(app)

        # Test that telemetry router is included
        response = client.get("/telemetry/ingest")
        # Should not be 404 (even if it's 405 or other error, it means the router is included)
        assert response.status_code != 404

    def test_database_connection_error(self):
        """Test database connection error handling."""
        from sqlalchemy import create_engine, exc

        with pytest.raises(exc.NoSuchModuleError):
            create_engine("invalid://url")


class TestDatabaseSession:
    """Test cases for database session management."""

    def test_engine_configuration(self):
        """Test SQLAlchemy engine configuration."""
        from app.db.session import engine

        # Test that engine is properly configured
        assert engine is not None
        assert hasattr(engine, "pool")
        assert hasattr(engine, "url")

    def test_session_factory_configuration(self):
        """Test session factory configuration."""
        from app.db.session import SessionLocal

        # Test that session factory is properly configured
        assert SessionLocal is not None
        assert hasattr(SessionLocal, "__call__")
