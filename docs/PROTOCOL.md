# Cloud RO Bluetooth protocol notes

Worked out from one unit (firmware `V1.05`) by reading its GATT table. Nothing
here comes from the vendor. Confidence is marked per field; corrections welcome.

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

## Service `5e3c1400-0929-41b6-89ea-502be1edf8b0`

Characteristic UUIDs share the same base; only the fourth byte pair changes.

| Char | Properties | Contents |
|---|---|---|
| `1401` | read, notify | Firmware version string, e.g. `V1.05` |
| `1402` | read, notify, write | Device clock. Notifies once a minute. See below. |
| `1403` | read, notify | An ASCII Unix timestamp (16 bytes). Purpose unconfirmed, probably last filter change or reset. |
| `1404` | read, notify | **Live readings**, notifies once a second. See below. |
| `1405` | read, notify, write | Settings-like block. Observed `u32 = 32`, then bytes `37, 100`. Meaning unknown. |
| `1406` | read, notify | Usage and TDS history. See below. |
| `1407` | read, notify | One timestamped TDS record followed by calibration-looking doubles. |
| `1410` | read, notify, write | Command string. Observed value `TDSHISTORY`. Not needed for normal reads. |
| `1411` | read, notify | Command response text, e.g. `TDS History Sent`. |

Reads return 100 bytes regardless of the real structure size. The bytes past
the end of each structure are neighbouring firmware memory (you will see the
next characteristic's data, or the GATT handle table), so only trust the
offsets listed here.

### `1404` live readings

| Offset | Type | Meaning | Confidence |
|---|---|---|---|
| 0 | u16 | TDS at inlet, ppm | High |
| 2 | u16 | TDS after RO membrane, ppm | High |
| 4 | u16 | TDS after remineralization, ppm | High |
| 6 | u16 | Tank pressure, unit unknown. About 244 when full; fell to 131 after 98 oz was drawn | High (that it is pressure) |
| 8 | u32 | Total water dispensed, US fluid ounces. Updates each time the flow stops | Confirmed against the app (29,694 oz = 232 gal) |
| 12 | u16 | Battery percent (reads 99) | Unconfirmed |
| 14 | u16 | Battery millivolts (reads about 4580, dips briefly when the unit saves to flash) | Medium |
| 16 | u16 | Tank reading, unit unknown. 45 to 46 when full; fell to 18 after 98 oz was drawn. Tracks the pressure, but not linearly | High (that it is tank fill) |
| 18–25 | 4 × u16 | Unknown, constant (51, 253, 48, 248) | |
| 26 | u8 | 0 | |
| 27 | u8 | 1 while water is being dispensed | High |
| 28 | u16 | Status bits. Bit 1 (`0x02`) is set while the tank is refilling. Bit 0 has always been 1 | High (bit 1) |
| 30 | u16 | Uptime counter, +1 per second | High |

The three TDS values are only re-measured when water flows, so they hold
steady between uses.

The app also derives "water bottles saved" as total ounces ÷ 16.

**Tank scale.** One step of the tank reading is roughly 3.6 oz (27 steps for
98 oz), which would fit tenths of a litre or quarter-pints; one observation is
not enough to tell. The integration reports tank level as a percentage of 45.

### `1402` clock

| Offset | Type | Meaning |
|---|---|---|
| 0 | char[16] | Current time, ASCII Unix timestamp, NUL padded |
| 16 | char[16] | The same timestamp that `1403` returns |
| 32 | 9 × u32 | C `struct tm` in UTC: sec, min, hour, mday, mon (0-based), year − 1900, wday, yday, isdst |

### `1406` usage and history

| Offset | Type | Meaning | Confidence |
|---|---|---|---|
| 0 | 12 × u16 | Ounces dispensed per calendar month, January first | High (drawing 98 oz in November raised the eleventh value by 98) |
| 24 | u32 | Ounces in another bucket. The twelve values plus this one sum exactly to the total in `1404` | High (the sum), low (what the bucket is) |
| 28 | u16 | Number of history records | Medium |
| 30 | records | 10 bytes each: `u32` Unix time, then `u16` TDS inlet / RO / remineralized | High |

## Not found yet

- **Filter life.** No per-filter percentage has been seen. The app probably
  computes it from the timestamp in `1403` and the usage counters.
- **Units** of the tank pressure and tank reading.

## Reproducing

```sh
uv run tools/gatt.py <serial> -t 120 -o captures/gatt.jsonl
uv run tools/decode.py captures/gatt.jsonl
```

`gatt.py` only reads and subscribes; it never writes to the unit. Close the
phone app first, since the unit will not advertise while the app is connected.
