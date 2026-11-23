"""Binary sensors for the Cloud RO integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CloudROConfigEntry
from .entity import CloudROEntity
from .parser import CloudROData


@dataclass(frozen=True, kw_only=True)
class CloudROBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Cloud RO binary sensor."""

    value_fn: Callable[[CloudROData], bool]


BINARY_SENSORS: tuple[CloudROBinarySensorDescription, ...] = (
    CloudROBinarySensorDescription(
        key="tank_filling",
        translation_key="tank_filling",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.filling,
    ),
    CloudROBinarySensorDescription(
        key="outlet_valve",
        translation_key="outlet_valve",
        device_class=BinarySensorDeviceClass.OPENING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.outlet_open,
    ),
    # On means low, judged by voltage the way the Cloud app does.
    CloudROBinarySensorDescription(
        key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.battery_low,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudROConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cloud RO binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        CloudROBinarySensor(coordinator, desc) for desc in BINARY_SENSORS
    )


class CloudROBinarySensor(CloudROEntity, BinarySensorEntity):
    """An on/off state read from the unit."""

    entity_description: CloudROBinarySensorDescription

    @property
    def is_on(self) -> bool:
        """Return the current state."""
        return self.entity_description.value_fn(self.coordinator.data)
