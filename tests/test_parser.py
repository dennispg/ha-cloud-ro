"""Parser tests against bytes captured from a real unit (firmware V1.05).

The parser is loaded by path so the tests don't need Home Assistant installed.
Run with: uv run pytest
"""

import importlib.util
from pathlib import Path
import sys

import pytest

_PATH = Path(__file__).parent.parent / "custom_components" / "cloud_ro" / "parser.py"
_spec = importlib.util.spec_from_file_location("cloud_ro_parser", _PATH)
parser = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = parser
_spec.loader.exec_module(parser)

# Read of 5e3c1404 with the tank full. The app showed "232 total gallons".
LIVE = bytes.fromhex(
    "750104001c00f200fe7300006300e9112c003300fd003000f80000000100cc59006b0000791c"
    "03000e001000120011000000140016001500000018001a00190000001c001e001d0000002000"
    "220021000000240026002500000028002a00290000002c00"
)
# Same characteristic part-way through a refill, after 98 oz had been drawn.
LIVE_FILLING = bytes.fromhex(
    "720104001800db00607400006300e01123003300fd003000f80000000300fc74006b0000791c"
)
# ...and while water was being dispensed.
LIVE_DISPENSING = bytes.fromhex(
    "750104001c00cf00fe7300006300e2111f003300fd003000f80000010100af72006b0000791c"
)
# Read of 5e3c1401: version string, then unrelated firmware memory.
FIRMWARE = bytes.fromhex("56312e3035000000001402000000000054686973206973")
# Read of 5e3c1402 in November: two ASCII timestamps, then a struct tm.
CLOCK = bytes.fromhex(
    "3137393531393234393700000000000031373930353338363836000000000000"
    "180000002300000010000000140000000a0000007e0000000500000043010000"
)
# Read of 5e3c1406: twelve monthly ounce counters, then history.
USAGE = bytes.fromhex(
    "e5059f0374074f091f09fb084c09dd09870ca0073a079102e41600000e00"
)


def test_parse_live():
    data = parser.parse_live(LIVE, "V1.05")
    assert data.tds_inlet == 373
    assert data.tds_filtered == 4
    assert data.tds_remineralized == 28
    assert data.total_ounces == 29694
    assert round(data.total_gallons) == 232
    assert data.battery_percent == 99
    assert data.battery_voltage == 4.585
    assert data.rejection == pytest.approx(98.93, abs=0.01)
    assert data.firmware == "V1.05"
    assert data.tank_ounces == 242
    assert data.tank_gallons == pytest.approx(1.89, abs=0.01)
    assert data.tank_pressure == 44
    assert data.tank_max_pressure == 51
    assert data.tank_max_ounces == 253
    assert data.tank_month_max_pressure == 48
    assert data.tank_month_max_ounces == 248
    assert data.tank_level == 96
    assert data.filling is False
    assert data.outlet_open is True
    assert data.dispensing is False
    assert data.battery_low is False
    assert data.month_ounces is None
    assert data.month_gallons is None


def test_parse_live_while_filling():
    data = parser.parse_live(LIVE_FILLING)
    assert data.total_ounces == 29792
    assert data.tank_ounces == 219
    assert data.tank_pressure == 35
    assert data.tank_level == 87
    assert data.filling is True
    assert data.outlet_open is True
    assert data.dispensing is False


def test_parse_live_while_dispensing():
    data = parser.parse_live(LIVE_DISPENSING)
    assert data.dispensing is True
    assert data.filling is False
    assert data.tank_level == 82


def test_tank_level_is_capped():
    full = bytearray(LIVE)
    full[6] = 255  # more stored water than the recorded lifetime maximum
    assert parser.parse_live(bytes(full)).tank_level == 100


def test_tank_level_without_a_recorded_maximum():
    assert parser.parse_live(bytes(30)).tank_level is None


def test_battery_low_goes_by_voltage():
    low = bytearray(LIVE)
    low[14:16] = (3999).to_bytes(2, "little")
    assert parser.parse_live(bytes(low)).battery_low is True
    low[14:16] = (4000).to_bytes(2, "little")
    assert parser.parse_live(bytes(low)).battery_low is False


def test_parse_live_minimum_length():
    assert parser.parse_live(LIVE[:30]).tds_inlet == 373
    with pytest.raises(ValueError):
        parser.parse_live(LIVE[:29])


def test_rejection_with_zero_inlet():
    assert parser.parse_live(bytes(30)).rejection is None


def test_parse_firmware():
    assert parser.parse_firmware(FIRMWARE) == "V1.05"
    assert parser.parse_firmware(bytes(8)) is None


def test_parse_month_ounces():
    # The clock reads 2026-11-20 UTC; the November counter read 1850 oz.
    assert parser.parse_month_ounces(CLOCK, USAGE) == 1850
    assert parser.parse_live(LIVE, month_ounces=1850).month_gallons == pytest.approx(14.45, abs=0.01)


def test_parse_month_ounces_uses_only_the_timestamp():
    # Bytes after the 16-byte timestamp are not part of the characteristic.
    assert parser.parse_month_ounces(CLOCK[:16], USAGE) == 1850
    assert parser.parse_month_ounces(CLOCK[:16] + bytes(84), USAGE) == 1850
    # 2026-12-01 00:00:00 UTC picks the December counter.
    december = b"1796083200".ljust(16, b"\0")
    assert parser.parse_month_ounces(december, USAGE) == 657


def test_parse_month_ounces_rejects_bad_input():
    assert parser.parse_month_ounces(CLOCK, USAGE[:10]) is None
    assert parser.parse_month_ounces(b"", USAGE) is None
    assert parser.parse_month_ounces(bytes(16), USAGE) is None
    assert parser.parse_month_ounces(b"not a time".ljust(16, b"\0"), USAGE) is None
    assert parser.parse_month_ounces(b"9" * 16, USAGE) is None
