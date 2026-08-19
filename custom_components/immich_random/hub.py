"""Hub for the Immich Random Image integration."""
from __future__ import annotations

import logging
import ssl
from urllib.parse import urljoin

import aiohttp

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

_HEADER_API_KEY = "x-api-key"


def _create_ssl_context(verify_ssl: bool) -> ssl.SSLContext | bool:
    """Create an SSL context. If verify_ssl is False, create a context that doesn't verify."""
    if verify_ssl:
        return True  # Use default verification
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class ImmichRandomHub:
    """Immich API hub for fetching random images."""

    def __init__(
        self,
        host: str,
        api_key: str,
        album_ids: list[str] | None = None,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize."""
        self.host = host
        self.api_key = api_key
        self.album_ids = album_ids or []
        self.verify_ssl = verify_ssl
        self._ssl_context = _create_ssl_context(verify_ssl)

    def _session(self) -> aiohttp.ClientSession:
        """Create an aiohttp session with the right SSL settings."""
        connector = aiohttp.TCPConnector(ssl=self._ssl_context)
        return aiohttp.ClientSession(connector=connector)

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        try:
            async with self._session() as session:
                url = urljoin(self.host, "/api/users/me")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error("Auth failed: status=%d", response.status)
                        return False
                    return True
        except aiohttp.ClientError as exception:
            _LOGGER.error("Error connecting to the API: %s", exception)
            raise CannotConnect from exception

    async def get_my_user_info(self) -> dict:
        """Get user info for the config entry title."""
        try:
            async with self._session() as session:
                url = urljoin(self.host, "/api/users/me")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        raise ApiError()
                    return await response.json()
        except aiohttp.ClientError as exception:
            raise CannotConnect from exception

    async def list_all_albums(self) -> list[dict]:
        """List all albums."""
        try:
            async with self._session() as session:
                url = urljoin(self.host, "/api/albums")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        raise ApiError()
                    return await response.json()
        except aiohttp.ClientError as exception:
            raise CannotConnect from exception

    async def get_random_image(self) -> dict | None:
        """Get a random image from Immich using the v3 search/random endpoint.

        If album_ids is set, the random image is picked from those albums.
        Otherwise it's a fully random image from the entire library.
        """
        try:
            async with self._session() as session:
                url = urljoin(self.host, "/api/search/random")
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    _HEADER_API_KEY: self.api_key,
                }
                payload: dict = {"size": 1, "type": "IMAGE"}
                if self.album_ids:
                    payload["albumIds"] = self.album_ids

                async with session.post(
                    url=url, headers=headers, json=payload
                ) as response:
                    if response.status != 200:
                        _LOGGER.error(
                            "Random search failed: status=%d body=%s",
                            response.status,
                            await response.text(),
                        )
                        return None
                    results = await response.json()
                    if not results:
                        _LOGGER.warning("No images returned from random search")
                        return None
                    return results[0]
        except aiohttp.ClientError as exception:
            _LOGGER.error("Error connecting to the API: %s", exception)
            raise CannotConnect from exception

    async def download_asset(self, asset_id: str) -> bytes | None:
        """Download the original image."""
        try:
            async with self._session() as session:
                url = urljoin(self.host, f"/api/assets/{asset_id}/original")
                headers = {_HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error(
                            "Download failed: status=%d", response.status
                        )
                        return None
                    return await response.read()
        except aiohttp.ClientError as exception:
            _LOGGER.error("Error connecting to the API: %s", exception)
            raise CannotConnect from exception

    async def get_asset_info(self, asset_id: str) -> dict | None:
        """Get asset metadata."""
        try:
            async with self._session() as session:
                url = urljoin(self.host, f"/api/assets/{asset_id}")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        return None
                    return await response.json()
        except aiohttp.ClientError as exception:
            raise CannotConnect from exception


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class ApiError(HomeAssistantError):
    """Error to indicate that the API returned an error."""
