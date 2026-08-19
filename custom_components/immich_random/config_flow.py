"""Config flow for the Immich Random Image integration."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ALBUM_IDS,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .hub import CannotConnect, ImmichRandomHub, InvalidAuth

_LOGGER = logging.getLogger(__name__)


def _normalize_host(host: str) -> str:
    """Normalize a host URL.

    Handles:
      - Bare hostnames (e.g. hass.local) -> https://hass.local
      - localhost / 127.0.0.1 / 172.x private IPs
      - Full domain names (e.g. https://pics.sasquatch.dev)
      - Trailing slashes stripped
    """
    if not host.startswith("http://") and not host.startswith("https://"):
        host = "https://" + host
    return host.rstrip("/")


async def validate_input(hass, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input and return normalized data."""
    url = _normalize_host(data[CONF_HOST])
    api_key = data[CONF_API_KEY]
    verify_ssl = data.get(CONF_VERIFY_SSL, True)

    hub = ImmichRandomHub(host=url, api_key=api_key, verify_ssl=verify_ssl)
    if not await hub.authenticate():
        raise InvalidAuth

    hostname = urlparse(url).hostname

    return {
        "title": f"Immich @ {hostname}",
        "data": {
            CONF_HOST: url,
            CONF_API_KEY: api_key,
            CONF_VERIFY_SSL: verify_ssl,
        },
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Immich Random Image."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: host, API key, SSL toggle."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                result = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=result["title"], data=result["data"]
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlowHandler":
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for selecting albums and adjusting settings."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        hub = ImmichRandomHub(
            host=self.config_entry.data[CONF_HOST],
            api_key=self.config_entry.data[CONF_API_KEY],
            verify_ssl=self.config_entry.options.get(
                CONF_VERIFY_SSL, self.config_entry.data.get(CONF_VERIFY_SSL, True)
            ),
        )

        albums = await hub.list_all_albums()
        album_map = {album["id"]: album["albumName"] for album in albums}

        current_albums = self.config_entry.options.get(
            CONF_ALBUM_IDS, self.config_entry.data.get(CONF_ALBUM_IDS, [])
        )
        # Filter out any album IDs that no longer exist
        current_albums = [a for a in current_albums if a in album_map]

        schema_dict: dict = {
            vol.Optional(
                CONF_VERIFY_SSL,
                default=self.config_entry.options.get(
                    CONF_VERIFY_SSL,
                    self.config_entry.data.get(CONF_VERIFY_SSL, True),
                ),
            ): bool,
            vol.Optional(
                "scan_interval",
                default=self.config_entry.options.get(
                    "scan_interval", DEFAULT_SCAN_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=86400)),
        }

        if album_map:
            schema_dict[
                vol.Optional(CONF_ALBUM_IDS, default=current_albums)
            ] = cv.multi_select(album_map)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
