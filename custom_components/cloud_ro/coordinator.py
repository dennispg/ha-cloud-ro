"""Polling coordinator for the Cloud RO integration."""

from __future__ import annotations

from datetime import timedelta
import logging
import time

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHAR_FIRMWARE,
    CHAR_LIVE,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MIN_STALE_TIME,
)
from .parser import CloudROData, parse_firmware, parse_live

_LOGGER = logging.getLogger(__name__)

type CloudROConfigEntry = ConfigEntry[CloudROCoordinator]


class CloudROCoordinator(DataUpdateCoordinator[CloudROData]):
    """Connect to the unit, read it once, and disconnect."""

    config_entry: CloudROConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CloudROConfigEntry) -> None:
        """Initialize the coordinator."""
        interval = timedelta(
            minutes=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=interval,
        )
        self.address: str = entry.data[CONF_ADDRESS]
        self._stale_after = max(MIN_STALE_TIME, 3 * interval).total_seconds()
        self._last_success: float | None = None

    async def _async_update_data(self) -> CloudROData:
        try:
            data = await self._read()
        except (BleakError, TimeoutError, ValueError, UpdateFailed) as err:
            if (
                self._last_success is not None
                and time.monotonic() - self._last_success < self._stale_after
            ):
                _LOGGER.debug(
                    "Poll of %s failed, keeping last reading: %s", self.address, err
                )
                return self.data
            raise UpdateFailed(f"Could not read {self.address}: {err}") from err
        self._last_success = time.monotonic()
        return data

    async def _read(self) -> CloudROData:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            # Not advertising: out of range, or the phone app is connected to it.
            raise UpdateFailed("device is not advertising")

        client = await establish_connection(
            BleakClientWithServiceCache, ble_device, self.config_entry.title
        )
        try:
            live = await client.read_gatt_char(CHAR_LIVE)
            firmware = parse_firmware(await client.read_gatt_char(CHAR_FIRMWARE))
        finally:
            await client.disconnect()
        return parse_live(bytes(live), firmware)
