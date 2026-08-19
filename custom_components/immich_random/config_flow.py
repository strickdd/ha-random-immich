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
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for editing connection settings and selecting albums."""

    def __init__(self) -> None:
        """Initialize options."""
        self._albums_changed = False

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options: host, API key, SSL, albums, scan interval."""
        if user_input is not None:
            # Validate the connection with the new settings
            try:
                url = _normalize_host(user_input[CONF_HOST])
                hub = ImmichRandomHub(
                    host=url,
                    api_key=user_input[CONF_API_KEY],
                    verify_ssl=user_input.get(CONF_VERIFY_SSL, True),
                )
                if not await hub.authenticate():
                    _LOGGER.warning("Options flow: authentication failed")
                    return self.async_show_form(
                        step_id="init",
                        errors={"base": "invalid_auth"},
                        data_schema=self._build_schema(
                            await self._get_albums(
                                user_input[CONF_API_KEY],
                                url,
                                user_input.get(CONF_VERIFY_SSL, True),
                            ),
                            user_input,
                        ),
                    )
            except CannotConnect:
                return self.async_show_form(
                    step_id="init",
                    errors={"base": "cannot_connect"},
                    data_schema=self._build_schema(
                        [],
                        user_input,
                    ),
                )

            # Normalize the host
            user_input[CONF_HOST] = url

            # Check if album selection changed
            old_albums = set(self.config_entry.options.get(
                CONF_ALBUM_IDS, self.config_entry.data.get(CONF_ALBUM_IDS, [])
            ))
            new_albums = set(user_input.get(CONF_ALBUM_IDS, []))
            self._albums_changed = old_albums != new_albums

            # Update data fields (host, API key) and options
            new_data = dict(self.config_entry.data)
            new_data[CONF_HOST] = user_input[CONF_HOST]
            new_data[CONF_API_KEY] = user_input[CONF_API_KEY]
            new_data[CONF_VERIFY_SSL] = user_input.get(CONF_VERIFY_SSL, True)

            # Build options dict (everything except host and API key)
            options = {
                CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, True),
                "scan_interval": user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                CONF_ALBUM_IDS: user_input.get(CONF_ALBUM_IDS, []),
            }

            # Update the config entry data (host, API key, verify_ssl)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
                options=options,
            )

            # If albums changed, force a refresh
            if self._albums_changed:
                _LOGGER.info("Album selection changed, forcing image refresh")
                # Trigger entity update via the hub
                entry_data = self.hass.data.get(DOMAIN, {}).get(
                    self.config_entry.entry_id
                )
                if entry_data and "hub" in entry_data:
                    hub = entry_data["hub"]
                    # Update the hub's album_ids so the next poll uses the new albums
                    hub.album_ids = options[CONF_ALBUM_IDS]
                    hub.verify_ssl = options[CONF_VERIFY_SSL]

            return self.async_create_entry(title="", data=options)

        # Build the form with current values
        host = self.config_entry.data.get(CONF_HOST, "")
        api_key = self.config_entry.data.get(CONF_API_KEY, "")
        verify_ssl = self.config_entry.options.get(
            CONF_VERIFY_SSL, self.config_entry.data.get(CONF_VERIFY_SSL, True)
        )
        scan_interval = self.config_entry.options.get(
            "scan_interval", DEFAULT_SCAN_INTERVAL
        )
        current_albums = self.config_entry.options.get(
            CONF_ALBUM_IDS, self.config_entry.data.get(CONF_ALBUM_IDS, [])
        )

        # Fetch albums for the picker
        try:
            albums = await self._get_albums(api_key, host, verify_ssl)
        except Exception:
            _LOGGER.warning("Failed to fetch albums for options flow")
            albums = []

        album_map = {album["id"]: album["albumName"] for album in albums}
        current_albums = [a for a in current_albums if a in album_map]

        schema_dict: dict = {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_API_KEY, default=api_key): str,
            vol.Optional(CONF_VERIFY_SSL, default=verify_ssl): bool,
            vol.Optional(
                "scan_interval",
                default=scan_interval,
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

    async def _get_albums(
        self, api_key: str, host: str, verify_ssl: bool
    ) -> list[dict]:
        """Fetch the list of albums from Immich."""
        url = _normalize_host(host)
        hub = ImmichRandomHub(host=url, api_key=api_key, verify_ssl=verify_ssl)
        return await hub.list_all_albums()
