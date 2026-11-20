"""Config flow and setup tests, run inside a real Home Assistant test harness.

Bluetooth itself is mocked: discovery results and the GATT reads are patched.
Skipped unless pytest-homeassistant-custom-component is installed:

    uv run --with pytest-homeassistant-custom-component pytest
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cloud_ro.const import (
    CHAR_CLOCK,
    CHAR_FIRMWARE,
    CHAR_LIVE,
    CHAR_USAGE,
    CONF_POLL_INTERVAL,
    DOMAIN,
    SERVICE_UUID,
)
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .test_parser import CLOCK, FIRMWARE, LIVE, USAGE

ADDRESS = "D4:12:34:56:78:9A"


def _service_info(name: str | None = "AB123-CLOUDRO") -> BluetoothServiceInfoBleak:
    return BluetoothServiceInfoBleak(
        name=name or ADDRESS,
        address=ADDRESS,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[SERVICE_UUID],
        source="local",
        device=BLEDevice(ADDRESS, name, {}),
        advertisement=AdvertisementData(
            local_name=name,
            manufacturer_data={},
            service_data={},
            service_uuids=[SERVICE_UUID],
            tx_power=None,
            rssi=-60,
            platform_data=(),
        ),
        time=0,
        connectable=True,
        tx_power=None,
    )


@pytest.fixture(autouse=True)
def _setup(enable_custom_integrations, enable_bluetooth):
    """Load custom integrations and a mocked Bluetooth stack for every test."""


@pytest.fixture
def mock_unit():
    """Patch the BLE connection so reads return captured payloads."""
    client = AsyncMock()
    client.read_gatt_char.side_effect = lambda uuid: {
        CHAR_LIVE: bytearray(LIVE),
        CHAR_FIRMWARE: bytearray(FIRMWARE),
        CHAR_CLOCK: bytearray(CLOCK),
        CHAR_USAGE: bytearray(USAGE),
    }[uuid]
    with (
        patch(
            "custom_components.cloud_ro.coordinator.bluetooth.async_ble_device_from_address",
            return_value=BLEDevice(ADDRESS, "AB123-CL", {}),
        ),
        patch(
            "custom_components.cloud_ro.coordinator.establish_connection",
            return_value=client,
        ),
    ):
        yield client


async def test_bluetooth_discovery(hass, mock_unit):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=_service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cloud RO AB123"
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


async def test_truncated_name_still_gives_serial(hass, mock_unit):
    """Advertisements can carry the shortened name "<serial>-CL"."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=_service_info("AB123-CL")
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["title"] == "Cloud RO AB123"


async def test_user_flow_without_advertised_name(hass, mock_unit):
    """The unit is matched by service UUID even when no name is seen."""
    with patch(
        "custom_components.cloud_ro.config_flow.async_discovered_service_info",
        return_value=[_service_info(name=None)],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Cloud RO {ADDRESS}"


async def test_user_flow_nothing_found(hass):
    with patch(
        "custom_components.cloud_ro.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_setup_creates_sensors_and_disconnects(hass, mock_unit):
    # The harness defaults to metric, where HA would show the total in litres.
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = MockConfigEntry(
        domain=DOMAIN, title="Cloud RO AB123", unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = {s.entity_id: s.state for s in hass.states.async_all("sensor")}
    assert states["sensor.cloud_ro_ab123_tds_inlet"] == "373"
    assert states["sensor.cloud_ro_ab123_tds_filtered"] == "4"
    assert states["sensor.cloud_ro_ab123_tds_remineralized"] == "28"
    assert float(states["sensor.cloud_ro_ab123_total_water"]) == pytest.approx(231.98, abs=0.01)
    assert states["sensor.cloud_ro_ab123_battery"] == "99"
    assert states["sensor.cloud_ro_ab123_tank_level"] == "98"
    assert float(states["sensor.cloud_ro_ab123_water_this_month"]) == pytest.approx(14.45, abs=0.01)
    assert len(states) == 9
    assert hass.states.get("binary_sensor.cloud_ro_ab123_tank_filling").state == "off"
    mock_unit.disconnect.assert_awaited_once()


async def test_failed_poll_keeps_last_reading(hass, mock_unit):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Cloud RO AB123", unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Phone app grabs the connection: the unit stops advertising.
    with patch(
        "custom_components.cloud_ro.coordinator.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    assert hass.states.get("sensor.cloud_ro_ab123_tds_inlet").state == "373"


async def test_options_change_poll_interval(hass, mock_unit):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Cloud RO AB123", unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == timedelta(minutes=5)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_POLL_INTERVAL: 30}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # The entry reloads with a new coordinator on the new interval.
    assert entry.options == {CONF_POLL_INTERVAL: 30}
    assert entry.runtime_data.update_interval == timedelta(minutes=30)


async def test_goes_unavailable_once_reading_is_stale(hass, mock_unit):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Cloud RO AB123", unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator._last_success -= 2 * 60 * 60  # last good read was two hours ago
    with patch(
        "custom_components.cloud_ro.coordinator.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert hass.states.get("sensor.cloud_ro_ab123_tds_inlet").state == "unavailable"
