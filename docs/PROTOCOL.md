# Cloud RO Bluetooth protocol notes

Worked out from one unit (firmware `V1.05`) by reading its GATT table. Nothing
here comes from the vendor. Confidence is marked per field; corrections welcome.

## Basics

- The unit advertises as `<serial>-CL`, for example `AB123-CL`. The serial is
  shown in the app under Account → Cloud Devices.
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
| `1402` | read, notify, write | Device clock as an ASCII Unix timestamp (16 bytes, NUL padded). Notifies once a minute. |
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
| 6 | u16 | Unknown. ×10 °C water temperature is a guess (242 → 245 over two minutes) | Low |
| 8 | u32 | Total water dispensed, US fluid ounces | Confirmed against the app (29,694 oz = 232 gal) |
| 12 | u16 | Battery percent (read 99) | Unconfirmed |
| 14 | u16 | Battery millivolts (read 4585) | Unconfirmed |
| 16 | u16 | Unknown (44 → 46, rises with offset 6) | |
| 18–25 | 4 × u16 | Unknown (51, 253, 48, 248) | |
| 26 | u16 | 0 | |
| 28 | u16 | 1 | |
| 30 | u16 | Uptime counter, +1 per second | High |

The app also derives "water bottles saved" as total ounces ÷ 16.

### `1406` usage and history

| Offset | Type | Meaning | Confidence |
|---|---|---|---|
| 0 | 12 × u16 | Ounces per period, probably monthly | Medium |
| 24 | u32 | Ounces in another bucket. The twelve values plus this one sum exactly to the total in `1404`. | High (the sum), low (what the bucket is) |
| 28 | u16 | Number of history records | Medium |
| 30 | records | 10 bytes each: `u32` Unix time, then `u16` TDS inlet / RO / remineralized | High |

## Not found yet

- **Tank level.** The app shows it (for example "full"), but the field has not
  been identified. Candidates are the unknowns in `1404` and the `100` in `1405`.
- **Filter life.** No per-filter percentage has been seen. The app probably
  computes it from the timestamp in `1403` and the usage counters.

## Reproducing

```sh
uv run tools/gatt.py <serial> -t 120 -o captures/gatt.jsonl
uv run tools/decode.py captures/gatt.jsonl
```

`gatt.py` only reads and subscribes; it never writes to the unit. Close the
phone app first, since the unit will not advertise while the app is connected.
