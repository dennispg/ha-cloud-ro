"""Decode Cloud RO characteristic payloads.

Pure Python with no Home Assistant imports, so it can be tested and reused on
its own. Field layout is documented in docs/PROTOCOL.md.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

OUNCES_PER_GALLON = 128

# u16 TDS inlet, u16 TDS after RO, u16 TDS after remineralization,
# u16 unknown, u32 total ounces, u16 battery percent, u16 battery millivolts
_LIVE = struct.Struct("<HHHHIHH")


@dataclass(frozen=True, slots=True)
class CloudROData:
    """One reading from the unit."""

    tds_inlet: int
    tds_filtered: int
    tds_remineralized: int
    total_ounces: int
    battery_percent: int
    battery_millivolts: int
    firmware: str | None = None

    @property
    def total_gallons(self) -> float:
        """Lifetime water dispensed, in US gallons."""
        return self.total_ounces / OUNCES_PER_GALLON

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


def parse_live(data: bytes, firmware: str | None = None) -> CloudROData:
    """Decode the live-readings characteristic (5e3c1404)."""
    if len(data) < _LIVE.size:
        raise ValueError(f"live payload too short: {len(data)} bytes")
    inlet, filtered, remineralized, _unknown, ounces, percent, millivolts = (
        _LIVE.unpack_from(data)
    )
    return CloudROData(
        tds_inlet=inlet,
        tds_filtered=filtered,
        tds_remineralized=remineralized,
        total_ounces=ounces,
        battery_percent=percent,
        battery_millivolts=millivolts,
        firmware=firmware,
    )


def parse_firmware(data: bytes) -> str | None:
    """Decode the firmware-version characteristic (5e3c1401), e.g. "V1.05"."""
    text = bytes(data).split(b"\0", 1)[0].decode("ascii", "ignore").strip()
    return text or None
