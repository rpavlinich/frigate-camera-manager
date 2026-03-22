"""Unit tests for FrigateApiClient — all HTTP calls are mocked."""

import pytest
from unittest.mock import MagicMock, patch

from frigate_camera_manager.client import FrigateApiClient


@pytest.fixture
def client():
    return FrigateApiClient(
        base_url="http://frigate.test:5000",
        token="test-token",
    )


def mock_response(json_data=None, content=b"", status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.content = content
    r.text = str(json_data)
    r.raise_for_status = MagicMock()
    return r


class TestFrigateApiClient:
    def test_auth_header_with_token(self, client):
        headers = client._headers()
        assert headers["Authorization"] == "Bearer test-token"

    def test_auth_basic_fallback(self):
        c = FrigateApiClient(base_url="http://test", username="u", password="p")
        auth = c._auth()
        assert auth is not None
        assert auth.username == "u"

    def test_auth_none_without_creds(self):
        c = FrigateApiClient(base_url="http://test")
        assert c._auth() is None

    @patch("frigate_camera_manager.client.requests.get")
    def test_list_cameras(self, mock_get, client):
        mock_get.return_value = mock_response({"front_yard": {"enabled": True, "detect": {}}})
        result = client.list_cameras()
        assert "front_yard" in result
        mock_get.assert_called_once()

    @patch("frigate_camera_manager.client.requests.get")
    def test_get_snapshot(self, mock_get, client):
        mock_get.return_value = mock_response(content=b"\xff\xd8\xff")  # JPEG magic bytes
        data = client.get_camera_snapshot("front_yard")
        assert data == b"\xff\xd8\xff"

    @patch("frigate_camera_manager.client.requests.get")
    def test_get_events_filters(self, mock_get, client):
        mock_get.return_value = mock_response([])
        client.get_events(camera="front_yard", limit=10, after=1000.0, before=2000.0)
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["params"]["camera"] == "front_yard"
        assert call_kwargs["params"]["limit"] == 10

    @patch("frigate_camera_manager.client.requests.get")
    def test_get_version(self, mock_get, client):
        mock_get.return_value = mock_response("0.14.0")
        v = client.get_version()
        assert v == "0.14.0"

    @patch("frigate_camera_manager.client.requests.get")
    def test_raise_on_error(self, mock_get, client):
        r = MagicMock()
        r.raise_for_status.side_effect = Exception("404")
        mock_get.return_value = r
        with pytest.raises(Exception):
            client.list_cameras()
