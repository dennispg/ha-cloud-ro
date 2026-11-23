# Cloud RO Bluetooth protocol notes

Worked out from one unit (firmware `V1.05`) by reading its GATT table. The
layout has since been confirmed, so the meanings below are no longer guesses,
and other firmware versions use the same layout. This project is unofficial
and not affiliated with Cloud.

## Basics

- The unit's name is `<serial>-CLOUDRO`, for example `AB123-CLOUDRO`. Scans
  often see it shortened to `<serial>-CL`. The serial is shown in the app under
  Account → Cloud Devices.
- The advertisement carries only the name and one service UUID. No sensor data
  is in the advertisement; you have to connect.
- It accepts **one connection at a time** and stops advertising while connected.
- No pairing, bonding or unlock command is needed. Every characteristic below
  can be read immediately after connecting.
- The radio is a Nordic chip (the Nordic DFU service `0xFE59` is present).
- All multi-byte integers are little-endian.
- **Only read.** Everything the app displays can be had by reading. Some
  characteristics accept writes; do not write to any of them (see
  [Not documented here](#not-documented-here)).

## Service `5e3c1400-0929-41b6-89ea-502be1edf8b0`

Characteristic UUIDs share the same base; only the fourth byte pair changes.

| Char | Contents |
|---|---|
| `1401` | Firmware version string, e.g. `V1.05` |
| `1402` | Device clock. Notifies once a minute. See below. |
| `1403` | The date the unit was last powered on, as an ASCII Unix timestamp (16 bytes) |
| `1404` | **Live readings**, notifies once a second. See below. |
| `1405` | A settings block that is not currently in use |
| `1406` | Usage and TDS history. See below. |
| `1407` | One timestamped TDS record followed by factory sensor calibration (doubles). Nothing useful to an integration. |

Reads return 100 bytes regardless of the real structure size. The bytes past
the end of each structure are neighbouring firmware memory (you will see the
next characteristic's data, or the GATT handle table). What lands there can
change between firmware versions, so only trust the offsets listed here.

### `1404` live readings

| Offset | Type | Meaning |
|---|---|---|
| 0 | u16 | TDS at inlet, ppm |
| 2 | u16 | TDS after RO membrane, ppm |
| 4 | u16 | TDS after remineralization, ppm |
| 6 | u16 | Water stored in the tank, US fluid ounces. About 244 when full on the development unit; fell to 131 after 98 oz was drawn |
| 8 | u32 | Total water dispensed, US fluid ounces. Updates each time the flow stops (29,694 oz showed as 232 gal in the app) |
| 12 | u16 | Battery percent. Not reported by every board, so do not rely on it |
| 14 | u16 | Battery millivolts (reads about 4580 when fresh, dips briefly when the unit saves to flash) |
| 16 | u16 | Tank pressure, psi. 45 to 46 when full on the development unit; fell to 18 after 98 oz was drawn |
| 18 | u16 | Highest tank pressure the unit has ever seen, psi |
| 20 | u16 | Most stored water the unit has ever seen, oz |
| 22 | u16 | Highest tank pressure this month, psi |
| 24 | u16 | Most stored water this month, oz |
| 26 | u8 | 0 |
| 27 | u8 | 1 while water is being dispensed |
| 28 | u16 | Status bits. Bit 0 (`0x01`): outlet valve open, its normal state. Bit 1 (`0x02`): inlet valve open, which means the tank is refilling |
| 30 | u16 | Uptime counter, +1 per second |

The three TDS values are only re-measured when water flows, so they hold
steady between uses.

The app also derives "water bottles saved" as total ounces ÷ 16.

**How full is full.** It varies a little between units and with the home's
water pressure; roughly 230 to 250 oz. The development unit's maximums read
51 psi / 253 oz lifetime and 48 psi / 248 oz for the month, a little past that
range. The integration reports tank level as stored water divided by the
unit's own lifetime maximum (offset 20), so it needs no per-unit setting. The
monthly maximum is not used for this because it starts over each month.

**Battery.** The app goes by the voltage, not the percent: below 4000 mV is
low, and below 3900 mV it is time to change the battery.

### `1402` clock

| Offset | Type | Meaning |
|---|---|---|
| 0 | char[16] | Current time, ASCII Unix timestamp, NUL padded |

That is the whole characteristic. On `V1.05` a read happens to continue with
the `1403` timestamp and then a C `struct tm` of the current time in UTC, but
those bytes are not part of `1402` and can move between firmware versions.
Work out the date from the timestamp instead.

### `1406` usage and history

| Offset | Type | Meaning |
|---|---|---|
| 0 | 12 × u16 | Ounces dispensed per calendar month, January first (drawing 98 oz in November raised the eleventh value by 98) |
| 24 | u32 | Ounces dispensed in months that have rolled off the twelve-month window. The twelve values plus this one sum exactly to the total in `1404` |
| 28 | u16 | Number of history records |
| 30 | records | 10 bytes each: `u32` Unix time, then `u16` TDS inlet / RO / remineralized |

## Not on the unit

- **Filter life.** There is no per-filter value. The filters and battery are
  replaced together as a set, and the replacement date is not worked out on
  the unit, so the app is the place to see it.
- **Water quality, pH, toxins and minerals** in the app are calculated or
  looked up, not read from the unit.

## Not documented here

The service also has characteristics used for factory and service commands.
They are deliberately left out of these notes: some of those commands can
return the unit to a factory or uncalibrated state. Nothing in this
project writes to the unit, and nothing should.

## Reproducing

```sh
uv run tools/gatt.py <serial> -t 120 -o captures/gatt.jsonl
uv run tools/decode.py captures/gatt.jsonl
```

`gatt.py` only reads and subscribes; it never writes to the unit. Close the
phone app first, since the unit will not advertise while the app is connected.
