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
    UnitOfPressure,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CloudROConfigEntry
from .entity import CloudROEntity
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
        key="month_water",
        translation_key="month_water",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda d: d.month_gallons,
    ),
    CloudROSensorDescription(
        key="tank_level",
        translation_key="tank_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.tank_level,
    ),
    CloudROSensorDescription(
        key="tank_water",
        translation_key="tank_water",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: d.tank_gallons,
    ),
    CloudROSensorDescription(
        key="tank_pressure",
        translation_key="tank_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.tank_pressure,
    ),
    # Not every board reports a percentage, so this is off unless enabled by
    # hand. The "Battery" binary sensor (from the voltage) is the one to use.
    CloudROSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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


class CloudROSensor(CloudROEntity, SensorEntity):
    """A single value read from the unit."""

    entity_description: CloudROSensorDescription

    @property
    def native_value(self) -> float | int | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)
