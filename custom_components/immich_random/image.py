"""Image platform for the Immich Random Image integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .hub import ImmichRandomHub

_LOGGER = logging.getLogger(__name__)


def _get_scan_interval(config_entry: ConfigEntry) -> timedelta:
    """Get the scan interval from config entry options."""
    seconds = config_entry.options.get(
        "scan_interval",
        config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL),
    )
    return timedelta(seconds=int(seconds))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Immich Random image platform."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    hub: ImmichRandomHub = entry_data["hub"]

    _LOGGER.info(
        "Setting up Immich Random Image entity (host=%s, albums=%d, verify_ssl=%s)",
        hub.host,
        len(hub.album_ids),
        hub.verify_ssl,
    )

    async_add_entities([ImmichRandomImageEntity(hass, hub, config_entry)])


class ImmichRandomImageEntity(ImageEntity):
    """Image entity that displays a random image from Immich.

    Supports:
      - Fully random image from the entire library (no album_ids)
      - Random image from a single album (one album_id)
      - Random image from multiple albums (multiple album_ids)
    """

    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        hub: ImmichRandomHub,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(hass=hass, verify_ssl=hub.verify_ssl)
        self._hub = hub
        self._config_entry = config_entry
        album_ids = hub.album_ids
        if album_ids:
            if len(album_ids) == 1:
                self._attr_unique_id = f"immich_random_album_{album_ids[0]}"
                self._attr_name = "Immich Random Album Image"
            else:
                self._attr_unique_id = (
                    f"immich_random_albums_{'_'.join(album_ids[:3])}"
                )
                self._attr_name = "Immich Random Multi-Album Image"
        else:
            self._attr_unique_id = "immich_random"
            self._attr_name = "Immich Random Image"
        self._current_image: bytes | None = None
        self._attr_extra_state_attributes = {}

    @property
    def scan_interval(self) -> timedelta:
        """Return the scan interval for this entity."""
        return _get_scan_interval(self._config_entry)

    async def async_update(self) -> None:
        """Fetch a new random image."""
        _LOGGER.debug("Fetching new random image from %s", self._hub.host)

        asset = await self._hub.get_random_image()
        if not asset:
            _LOGGER.warning("No random image returned from Immich")
            return

        asset_id = asset.get("id")
        if not asset_id:
            _LOGGER.warning("Random image returned without an asset ID")
            return

        _LOGGER.debug(
            "Got random image: id=%s, file=%s",
            asset_id,
            asset.get("originalFileName", "?"),
        )

        image_bytes = await self._hub.download_asset(asset_id)
        if not image_bytes:
            _LOGGER.warning("Failed to download image %s from Immich", asset_id)
            return

        self._current_image = image_bytes
        self._attr_image_last_updated = datetime.now()
        self._attr_extra_state_attributes["media_filename"] = asset.get(
            "originalFileName", ""
        )
        self._attr_extra_state_attributes["media_localdatetime"] = asset.get(
            "localDateTime", ""
        )
        self._attr_extra_state_attributes["media_width"] = asset.get("width", "")
        self._attr_extra_state_attributes["media_height"] = asset.get("height", "")

        _LOGGER.info(
            "Updated Immich random image: %s (%sx%s, %s)",
            asset.get("originalFileName", "?"),
            asset.get("width", "?"),
            asset.get("height", "?"),
            asset.get("localDateTime", "?"),
        )

    async def async_image(self) -> bytes | None:
        """Return the current image bytes."""
        if not self._current_image:
            _LOGGER.debug("No cached image, triggering async_update")
            await self.async_update()
        return self._current_image
