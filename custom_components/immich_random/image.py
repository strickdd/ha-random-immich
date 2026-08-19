"""Image platform for the Immich Random Image integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import ImmichRandomHub

SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Immich Random image platform."""
    hub = ImmichRandomHub(
        host=config_entry.data[CONF_HOST],
        api_key=config_entry.data[CONF_API_KEY],
        album_ids=config_entry.options.get(
            "album_ids", config_entry.data.get("album_ids", [])
        ),
        verify_ssl=config_entry.options.get(
            "verify_ssl", config_entry.data.get("verify_ssl", True)
        ),
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
                self._attr_unique_id = f"immich_random_albums_{'_'.join(album_ids[:3])}"
                self._attr_name = "Immich Random Multi-Album Image"
        else:
            self._attr_unique_id = "immich_random"
            self._attr_name = "Immich Random Image"
        self._current_image: bytes | None = None
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Fetch a new random image."""
        asset = await self._hub.get_random_image()
        if not asset:
            _LOGGER.warning("No random image returned")
            return

        asset_id = asset.get("id")
        if not asset_id:
            return

        image_bytes = await self._hub.download_asset(asset_id)
        if not image_bytes:
            _LOGGER.warning("Failed to download image %s", asset_id)
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

    async def async_image(self) -> bytes | None:
        """Return the current image bytes."""
        if not self._current_image:
            await self.async_update()
        return self._current_image
