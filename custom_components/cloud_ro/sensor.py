"""Sensors for the Cloud RO integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CloudROConfigEntry, CloudROCoordinator
from .parser import CloudROData


@dataclass(frozen=True, kw_only=True)
class CloudROSensorDescription(SensorEntityDescription):
    """Describes a Cloud RO sensor."""

    value_fn: Callable[[CloudROData], float | int | None]


SENSORS: tuple[CloudROSensorDescription, ...] = (
    CloudROSensorDescription(
        key="tds_inlet",
        translation_key="tds_inlet",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.tds_inlet,
    ),
    CloudROSensorDescription(
        key="tds_filtered",
        translation_key="tds_filtered",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.tds_filtered,
    ),
    CloudROSensorDescription(
        key="tds_remineralized",
        translation_key="tds_remineralized",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.tds_remineralized,
    ),
    CloudROSensorDescription(
        key="rejection",
        translation_key="rejection",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.rejection,
    ),
    CloudROSensorDescription(
        key="total_water",
        translation_key="total_water",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda d: d.total_gallons,
    ),
    CloudROSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.battery_percent,
    ),
    CloudROSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda d: d.battery_voltage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudROConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cloud RO sensors."""
    coordinator = entry.runtime_data
    async_add_entities(CloudROSensor(coordinator, desc) for desc in SENSORS)


class CloudROSensor(CoordinatorEntity[CloudROCoordinator], SensorEntity):
    """A single value read from the unit."""

    _attr_has_entity_name = True
    entity_description: CloudROSensorDescription

    def __init__(
        self, coordinator: CloudROCoordinator, description: CloudROSensorDescription
    ) -> None:
        """Initialize the sensor."""
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
            # Only a real serial if the unit advertised its "<serial>-CL" name.
            serial_number=None if ":" in serial else serial,
            sw_version=coordinator.data.firmware,
        )

    @property
    def native_value(self) -> float | int | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)
