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

# Read of 5e3c1404. The app showed "232 total gallons" at the time.
LIVE = bytes.fromhex(
    "750104001c00f200fe7300006300e9112c003300fd003000f80000000100cc59006b0000791c"
    "03000e001000120011000000140016001500000018001a00190000001c001e001d0000002000"
    "220021000000240026002500000028002a00290000002c00"
)
# Read of 5e3c1401: version string, then unrelated firmware memory.
FIRMWARE = bytes.fromhex("56312e3035000000001402000000000054686973206973")


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


def test_parse_live_minimum_length():
    assert parser.parse_live(LIVE[:16]).tds_inlet == 373
    with pytest.raises(ValueError):
        parser.parse_live(LIVE[:15])


def test_rejection_with_zero_inlet():
    assert parser.parse_live(bytes(16)).rejection is None


def test_parse_firmware():
    assert parser.parse_firmware(FIRMWARE) == "V1.05"
    assert parser.parse_firmware(bytes(8)) is None
