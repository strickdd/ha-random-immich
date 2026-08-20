"""Tests for the ImmichRandomHub API calls using mocks."""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# Stub homeassistant before importing
_ha_stubs = [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.selector",
    "homeassistant.components",
    "homeassistant.components.image",
    "homeassistant.data_entry_flow",
]
for name in _ha_stubs:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()

# homeassistant.exceptions must have a real HomeAssistantError class
# so that our custom exception classes (CannotConnect, etc.) are real Exceptions
class HomeAssistantError(Exception):
    pass

sys.modules["homeassistant.exceptions"].HomeAssistantError = HomeAssistantError

from custom_components.immich_random.hub import (  # noqa: E402
    CannotConnect,
    ImmichRandomHub,
)


def mock_response(status=200, json_data=None, text="", content_type="image/jpeg"):
    """Create a mock aiohttp response context manager."""
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.content_type = content_type
    if json_data is not None:
        mock_resp.json = AsyncMock(return_value=json_data)
    mock_resp.text = AsyncMock(return_value=text)
    mock_resp.read = AsyncMock(return_value=b"fake-image-bytes")
    return mock_resp


# ── Authenticate ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authenticate_success():
    """Test successful authentication via validateToken."""
    hub = ImmichRandomHub(host="https://immich.local", api_key="test-key")
    mock_resp = mock_response(200, {"authStatus": True})
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_resp)

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        result = await hub.authenticate()
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_invalid_auth():
    """Test authentication fails with 401."""
    hub = ImmichRandomHub(host="https://immich.local", api_key="bad-key")
    mock_resp = mock_response(401, text="Unauthorized")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_resp)

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        result = await hub.authenticate()
    assert result is False


@pytest.mark.asyncio
async def test_authenticate_auth_status_false():
    """Test authentication fails when authStatus is False."""
    hub = ImmichRandomHub(host="https://immich.local", api_key="test-key")
    mock_resp = mock_response(200, {"authStatus": False})
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_resp)

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        result = await hub.authenticate()
    assert result is False


# ── Get random image ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_random_image_no_albums():
    """Test random image request without album filter."""
    hub = ImmichRandomHub(host="https://immich.local", api_key="test-key")
    mock_resp = mock_response(200, [{"id": "asset-1", "originalFileName": "photo.jpg"}])
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    captured_payload = {}

    class FakePost:
        def __init__(self, url, **kwargs):
            captured_payload.update(kwargs)
        async def __aenter__(self):
            return mock_resp
        async def __aexit__(self, *args):
            return None

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = FakePost

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        result = await hub.get_random_image()

    assert result is not None
    assert result["id"] == "asset-1"
    json_payload = captured_payload.get("json", {})
    assert "albumIds" not in json_payload


@pytest.mark.asyncio
async def test_get_random_image_with_albums():
    """Test random image request with album filter."""
    hub = ImmichRandomHub(
        host="https://immich.local",
        api_key="test-key",
        album_ids=["album-1", "album-2"],
    )
    mock_resp = mock_response(200, [{"id": "asset-1", "originalFileName": "photo.jpg"}])
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    captured_payload = {}

    class FakePost:
        def __init__(self, url, **kwargs):
            captured_payload.update(kwargs)
        async def __aenter__(self):
            return mock_resp
        async def __aexit__(self, *args):
            return None

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = FakePost

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        result = await hub.get_random_image()

    assert result is not None
    assert result["id"] == "asset-1"
    json_payload = captured_payload.get("json", {})
    assert json_payload["albumIds"] == ["album-1", "album-2"]


@pytest.mark.asyncio
async def test_get_random_image_empty_results():
    """Test handling of empty results from the random endpoint."""
    hub = ImmichRandomHub(host="https://immich.local", api_key="test-key")
    mock_resp = mock_response(200, [])
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_resp)

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        result = await hub.get_random_image()

    assert result is None


@pytest.mark.asyncio
async def test_get_random_image_api_error():
    """Test handling of API error (non-200 status)."""
    hub = ImmichRandomHub(host="https://immich.local", api_key="test-key")
    mock_resp = mock_response(500, text="Internal Server Error")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_resp)

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        result = await hub.get_random_image()

    assert result is None


# ── Download asset ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_asset_success():
    """Test successful asset download."""
    hub = ImmichRandomHub(host="https://immich.local", api_key="test-key")
    mock_resp = mock_response(200)
    mock_resp.read = AsyncMock(return_value=b"image-bytes")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_resp)

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        result = await hub.download_asset("asset-1")

    assert result == b"image-bytes"


@pytest.mark.asyncio
async def test_download_asset_not_found():
    """Test asset download returns None for 404."""
    hub = ImmichRandomHub(host="https://immich.local", api_key="test-key")
    mock_resp = mock_response(404, text="Not Found")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_resp)

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        result = await hub.download_asset("missing-asset")

    assert result is None


# ── Connection errors ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authenticate_connection_error():
    """Test that connection errors raise CannotConnect."""
    hub = ImmichRandomHub(host="https://immich.local", api_key="test-key")

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))

    with patch.object(ImmichRandomHub, "_session", return_value=mock_session):
        with pytest.raises(CannotConnect):
            await hub.authenticate()
