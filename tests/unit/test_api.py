"""
Tests for REST API endpoints.

Tests the FastAPI-based REST API for CoPaw Code.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the API."""
    from api.main import app

    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_returns_200(self, client):
        """Health endpoint should return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_returns_healthy(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_returns_version(self, client):
        """Health endpoint should return version."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_health_check_returns_timestamp(self, client):
        """Health endpoint should return timestamp."""
        response = client.get("/health")
        data = response.json()
        assert "timestamp" in data


class TestVersionEndpoint:
    """Tests for version endpoint."""

    def test_version_returns_200(self, client):
        """Version endpoint should return 200."""
        response = client.get("/version")
        assert response.status_code == 200

    def test_version_returns_correct_info(self, client):
        """Version endpoint should return correct information."""
        response = client.get("/version")
        data = response.json()
        assert data["version"] == "0.1.0"
        assert data["name"] == "CoPaw Code API"
        assert data["author"] == "CoPaw Team"


class TestConfigEndpoint:
    """Tests for config endpoint."""

    def test_config_returns_200(self, client):
        """Config endpoint should return 200."""
        response = client.get("/config")
        assert response.status_code == 200

    def test_config_returns_app_info(self, client):
        """Config endpoint should return app information."""
        response = client.get("/config")
        data = response.json()
        assert "app_name" in data
        assert "version" in data


class TestAgentsEndpoint:
    """Tests for agents endpoint."""

    def test_list_agents_returns_200(self, client):
        """List agents endpoint should return 200."""
        response = client.get("/agents/")
        assert response.status_code == 200

    def test_list_agents_returns_list(self, client):
        """List agents endpoint should return a list."""
        response = client.get("/agents/")
        data = response.json()
        assert isinstance(data, list)

    def test_get_agent_returns_200(self, client):
        """Get specific agent should return 200."""
        response = client.get("/agents/main-agent")
        assert response.status_code == 200

    def test_get_agent_returns_info(self, client):
        """Get specific agent should return agent info."""
        response = client.get("/agents/main-agent")
        data = response.json()
        assert data["name"] == "main-agent"

    def test_get_unknown_agent_returns_404(self, client):
        """Get unknown agent should return 404."""
        response = client.get("/agents/unknown-agent")
        assert response.status_code == 404


class TestToolsEndpoint:
    """Tests for tools endpoint."""

    def test_list_tools_returns_200(self, client):
        """List tools endpoint should return 200."""
        response = client.get("/tools/")
        assert response.status_code == 200

    def test_list_tools_returns_list(self, client):
        """List tools endpoint should return a list."""
        response = client.get("/tools/")
        data = response.json()
        assert isinstance(data, list)

    def test_list_tools_includes_read_file(self, client):
        """List tools should include read_file."""
        response = client.get("/tools/")
        data = response.json()
        tool_names = [t["name"] for t in data]
        assert "read_file" in tool_names

    def test_get_tool_returns_200(self, client):
        """Get specific tool should return 200."""
        response = client.get("/tools/read_file")
        assert response.status_code == 200

    def test_get_tool_returns_info(self, client):
        """Get specific tool should return tool info."""
        response = client.get("/tools/read_file")
        data = response.json()
        assert data["name"] == "read_file"

    def test_get_unknown_tool_returns_404(self, client):
        """Get unknown tool should return 404."""
        response = client.get("/tools/unknown_tool")
        assert response.status_code == 404


class TestSessionsEndpoint:
    """Tests for sessions endpoint."""

    def test_create_session_returns_201(self, client):
        """Create session should return 201."""
        response = client.post("/sessions/", json={})
        assert response.status_code == 201

    def test_create_session_with_name(self, client):
        """Create session with name."""
        response = client.post("/sessions/", json={"name": "Test Session"})
        data = response.json()
        assert data["name"] == "Test Session"

    def test_list_sessions_returns_200(self, client):
        """List sessions should return 200."""
        response = client.get("/sessions/")
        assert response.status_code == 200

    def test_get_session_returns_200(self, client):
        """Get session should return 200."""
        # Create a session first
        create_response = client.post("/sessions/", json={})
        session_id = create_response.json()["id"]

        # Get the session
        response = client.get(f"/sessions/{session_id}")
        assert response.status_code == 200

    def test_delete_session_returns_204(self, client):
        """Delete session should return 204."""
        # Create a session first
        create_response = client.post("/sessions/", json={})
        session_id = create_response.json()["id"]

        # Delete the session
        response = client.delete(f"/sessions/{session_id}")
        assert response.status_code == 204


class TestOpenAPIDocs:
    """Tests for OpenAPI documentation."""

    def test_docs_endpoint_returns_200(self, client):
        """Docs endpoint should return 200."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_endpoint_returns_200(self, client):
        """ReDoc endpoint should return 200."""
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_json_returns_200(self, client):
        """OpenAPI JSON should return 200."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_json_has_info(self, client):
        """OpenAPI JSON should have API info."""
        response = client.get("/openapi.json")
        data = response.json()
        assert "info" in data
        assert data["info"]["title"] == "CoPaw Code API"
