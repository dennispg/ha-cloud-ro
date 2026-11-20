"""Decode Cloud RO characteristic payloads.

Pure Python with no Home Assistant imports, so it can be tested and reused on
its own. Field layout is documented in docs/PROTOCOL.md.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

OUNCES_PER_GALLON = 128

# The tank reading settles at 45-46 when the tank is full. Its unit is not
# known, so the level is reported relative to this. Measured on one unit.
TANK_FULL_READING = 45

# u16 TDS inlet, u16 TDS after RO, u16 TDS after remineralization,
# u16 tank pressure (raw), u32 total ounces, u16 battery percent,
# u16 battery millivolts, u16 tank reading
_LIVE = struct.Struct("<HHHHIHHH")
_FLOW_OFFSET = 27  # u8: 1 while water is being dispensed
_STATUS_OFFSET = 28  # u16 bit field
_STATUS_FILLING = 0x02
_LIVE_MIN_LENGTH = _STATUS_OFFSET + 2

# Clock characteristic: two 16-byte ASCII timestamps, then a C `struct tm` of
# u32s (sec, min, hour, mday, mon, ...). tm_mon is 0-based.
_CLOCK_MONTH_OFFSET = 32 + 4 * 4

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
    tank_pressure_raw: int
    tank_reading: int
    dispensing: bool
    filling: bool
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
    def battery_voltage(self) -> float:
        """Battery voltage in volts."""
        return self.battery_millivolts / 1000

    @property
    def rejection(self) -> float | None:
        """Percent of inlet TDS removed by the RO membrane."""
        if self.tds_inlet == 0:
            return None
        return 100 * (1 - self.tds_filtered / self.tds_inlet)

    @property
    def tank_level(self) -> int:
        """Tank fill as a percentage of the full reading, capped at 100."""
        return min(100, round(100 * self.tank_reading / TANK_FULL_READING))


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
        pressure,
        ounces,
        percent,
        millivolts,
        tank,
    ) = _LIVE.unpack_from(data)
    (status,) = struct.unpack_from("<H", data, _STATUS_OFFSET)
    return CloudROData(
        tds_inlet=inlet,
        tds_filtered=filtered,
        tds_remineralized=remineralized,
        total_ounces=ounces,
        battery_percent=percent,
        battery_millivolts=millivolts,
        tank_pressure_raw=pressure,
        tank_reading=tank,
        dispensing=bool(data[_FLOW_OFFSET]),
        filling=bool(status & _STATUS_FILLING),
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
    from the unit's own clock so the right counter is picked at month rollover.
    """
    if len(clock) < _CLOCK_MONTH_OFFSET + 4 or len(usage) < _MONTHS.size:
        return None
    (month,) = struct.unpack_from("<I", clock, _CLOCK_MONTH_OFFSET)
    if month > 11:
        return None
    return _MONTHS.unpack_from(usage)[month]
