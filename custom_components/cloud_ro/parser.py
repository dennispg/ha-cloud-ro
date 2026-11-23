"""Decode Cloud RO characteristic payloads.

Pure Python with no Home Assistant imports, so it can be tested and reused on
its own. Field layout is documented in docs/PROTOCOL.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import struct

OUNCES_PER_GALLON = 128

# The Cloud app judges the battery by voltage: below 4000 mV is low, and below
# 3900 mV it is time to replace it. The percent field is not sent by every
# board, so it is not used for this.
BATTERY_LOW_MILLIVOLTS = 4000
BATTERY_REPLACE_MILLIVOLTS = 3900

# u16 TDS inlet, u16 TDS after RO, u16 TDS after remineralization,
# u16 stored water (oz), u32 total ounces, u16 battery percent,
# u16 battery millivolts, u16 tank pressure (psi),
# u16 lifetime max tank pressure, u16 lifetime max stored water,
# u16 this month's max tank pressure, u16 this month's max stored water
_LIVE = struct.Struct("<HHHHIHHHHHHH")
_FLOW_OFFSET = 27  # u8: 1 while water is being dispensed
_STATUS_OFFSET = 28  # u16 bit field
_STATUS_OUTLET_OPEN = 0x01  # outlet valve open, its normal state
_STATUS_FILLING = 0x02  # inlet valve open: the tank is refilling
_LIVE_MIN_LENGTH = _STATUS_OFFSET + 2

# Clock characteristic: the current time as an ASCII Unix timestamp, NUL
# padded. Whatever follows it in a read is not part of the characteristic.
_CLOCK_LENGTH = 16

# Usage characteristic: twelve u16 ounce counters, one per calendar month.
_MONTHS = struct.Struct("<12H")


@dataclass(frozen=True, slots=True)
class CloudROData:
    """One reading from the unit."""

    tds_inlet: int
    tds_filtered: int
    tds_remineralized: int
    total_ounces: int
    battery_percent: int
    battery_millivolts: int
    tank_ounces: int
    tank_pressure: int
    tank_max_ounces: int
    tank_max_pressure: int
    tank_month_max_ounces: int
    tank_month_max_pressure: int
    dispensing: bool
    filling: bool
    outlet_open: bool
    month_ounces: int | None = None
    firmware: str | None = None

    @property
    def total_gallons(self) -> float:
        """Lifetime water dispensed, in US gallons."""
        return self.total_ounces / OUNCES_PER_GALLON

    @property
    def month_gallons(self) -> float | None:
        """Water dispensed this calendar month, in US gallons."""
        if self.month_ounces is None:
            return None
        return self.month_ounces / OUNCES_PER_GALLON

    @property
    def tank_gallons(self) -> float:
        """Water stored in the tank, in US gallons."""
        return self.tank_ounces / OUNCES_PER_GALLON

    @property
    def battery_voltage(self) -> float:
        """Battery voltage in volts."""
        return self.battery_millivolts / 1000

    @property
    def battery_low(self) -> bool:
        """Whether the battery voltage is below the app's "low" threshold."""
        return self.battery_millivolts < BATTERY_LOW_MILLIVOLTS

    @property
    def rejection(self) -> float | None:
        """Percent of inlet TDS removed by the RO membrane."""
        if self.tds_inlet == 0:
            return None
        return 100 * (1 - self.tds_filtered / self.tds_inlet)

    @property
    def tank_level(self) -> int | None:
        """Stored water as a percentage of the most this unit has ever held.

        "Full" differs between units and with the home's water pressure, so
        the unit's own lifetime maximum is the reference. That maximum is a
        peak, so a normally full tank reads a little under 100.
        """
        if self.tank_max_ounces == 0:
            return None
        return min(100, round(100 * self.tank_ounces / self.tank_max_ounces))


def parse_live(
    data: bytes, firmware: str | None = None, month_ounces: int | None = None
) -> CloudROData:
    """Decode the live-readings characteristic (5e3c1404)."""
    if len(data) < _LIVE_MIN_LENGTH:
        raise ValueError(f"live payload too short: {len(data)} bytes")
    (
        inlet,
        filtered,
        remineralized,
        tank_ounces,
        ounces,
        percent,
        millivolts,
        tank_pressure,
        max_pressure,
        max_ounces,
        month_max_pressure,
        month_max_ounces,
    ) = _LIVE.unpack_from(data)
    (status,) = struct.unpack_from("<H", data, _STATUS_OFFSET)
    return CloudROData(
        tds_inlet=inlet,
        tds_filtered=filtered,
        tds_remineralized=remineralized,
        total_ounces=ounces,
        battery_percent=percent,
        battery_millivolts=millivolts,
        tank_ounces=tank_ounces,
        tank_pressure=tank_pressure,
        tank_max_ounces=max_ounces,
        tank_max_pressure=max_pressure,
        tank_month_max_ounces=month_max_ounces,
        tank_month_max_pressure=month_max_pressure,
        dispensing=bool(data[_FLOW_OFFSET]),
        filling=bool(status & _STATUS_FILLING),
        outlet_open=bool(status & _STATUS_OUTLET_OPEN),
        month_ounces=month_ounces,
        firmware=firmware,
    )


def parse_firmware(data: bytes) -> str | None:
    """Decode the firmware-version characteristic (5e3c1401), e.g. "V1.05"."""
    text = bytes(data).split(b"\0", 1)[0].decode("ascii", "ignore").strip()
    return text or None


def parse_month_ounces(clock: bytes, usage: bytes) -> int | None:
    """Ounces dispensed in the unit's current calendar month.

    `clock` is characteristic 5e3c1402 and `usage` is 5e3c1406. The month comes
    from the unit's own clock (UTC) so the right counter is picked at month
    rollover.
    """
    if len(usage) < _MONTHS.size:
        return None
    text = bytes(clock[:_CLOCK_LENGTH]).split(b"\0", 1)[0]
    if not text.isdigit():
        return None
    try:
        month = datetime.fromtimestamp(int(text), UTC).month
    except (OverflowError, OSError, ValueError):
        return None
    return _MONTHS.unpack_from(usage)[month - 1]
