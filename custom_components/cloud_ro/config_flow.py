"""Config flow for the Cloud RO integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    NAME_SUFFIX,
    SERVICE_UUID,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=MIN_POLL_INTERVAL,
                    max=MAX_POLL_INTERVAL,
                    step=1,
                    unit_of_measurement=UnitOfTime.MINUTES,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Coerce(int),
        )
    }
)


def _is_cloud_ro(info: BluetoothServiceInfoBleak) -> bool:
    return SERVICE_UUID in info.service_uuids or info.name.endswith(NAME_SUFFIX)


def _title(info: BluetoothServiceInfoBleak) -> str:
    """Use the advertised name ("<serial>-CL") when there is one."""
    if info.name.endswith(NAME_SUFFIX):
        return f"Cloud RO {info.name.removesuffix(NAME_SUFFIX)}"
    return f"Cloud RO {info.address}"


class CloudROConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cloud RO."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CloudROOptionsFlow:
        """Return the options flow."""
        return CloudROOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a unit found by Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": _title(discovery_info)}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered unit."""
        assert self._discovery_info is not None
        title = _title(self._discovery_info)
        if user_input is not None:
            return self.async_create_entry(
                title=title, data={CONF_ADDRESS: self._discovery_info.address}
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders={"name": title}
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick from units currently advertising."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered[address], data={CONF_ADDRESS: address}
            )

        configured = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in configured or not _is_cloud_ro(info):
                continue
            self._discovered[info.address] = _title(info)

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered)}
            ),
        )


class CloudROOptionsFlow(OptionsFlow):
    """Let the user change how often the unit is polled."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
