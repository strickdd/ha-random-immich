"""The Immich Random Image integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .hub import ImmichRandomHub

PLATFORMS: list[Platform] = [Platform.IMAGE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Immich Random Image from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    hub = ImmichRandomHub(
        host=entry.data[CONF_HOST],
        api_key=entry.data[CONF_API_KEY],
        album_ids=entry.options.get("album_ids", entry.data.get("album_ids", [])),
        verify_ssl=entry.options.get(
            "verify_ssl", entry.data.get("verify_ssl", True)
        ),
    )

    if not await hub.authenticate():
        raise HomeAssistantError("Failed to authenticate with Immich")

    # Store scan interval for the image platform to use
    scan_interval = entry.options.get(
        "scan_interval",
        entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "hub": hub,
        "scan_interval": int(scan_interval),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update — reload the entry."""
    await hass.config_entries.async_reload(entry.entry_id)
