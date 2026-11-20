"""Base entity for the Cloud RO integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CloudROCoordinator


class CloudROEntity(CoordinatorEntity[CloudROCoordinator]):
    """An entity belonging to one Cloud RO unit."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: CloudROCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

        title = coordinator.config_entry.title
        serial = title.removeprefix("Cloud RO ")
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=title,
            manufacturer="Cloud Water Filters",
            model="Cloud RO",
            # Only a real serial if the unit's advertised name was seen.
            serial_number=None if ":" in serial else serial,
            sw_version=coordinator.data.firmware,
        )
