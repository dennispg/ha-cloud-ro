"""Log BLE advertisements as JSON lines for reverse engineering.

Usage:
  uv run tools/scan.py                      # survey: every device, 20 s
  uv run tools/scan.py -t 60 -f "-CL"       # only devices whose name/address/UUIDs match
  uv run tools/scan.py -o captures/x.jsonl  # also append to a file

Each line is one advertisement. Only payload *changes* per device are printed
unless --all is given, so a long capture stays readable.
"""

import argparse
import asyncio
import json
import time

from bleak import BleakScanner


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-t", "--time", type=float, default=20, help="seconds to scan")
    ap.add_argument("-f", "--filter", default="", help="case-insensitive substring match")
    ap.add_argument("-o", "--out", help="append JSON lines to this file")
    ap.add_argument("--all", action="store_true", help="log repeats, not just changes")
    args = ap.parse_args()

    needle = args.filter.lower()
    last: dict[str, str] = {}
    out = open(args.out, "a") if args.out else None

    def on_adv(device, adv) -> None:
        rec = {
            "addr": device.address,
            "name": adv.local_name or device.name,
            "rssi": adv.rssi,
            "mfr": {f"0x{k:04x}": v.hex() for k, v in adv.manufacturer_data.items()},
            "svc_data": {k: v.hex() for k, v in adv.service_data.items()},
            "svc_uuids": adv.service_uuids,
        }
        if needle and needle not in json.dumps(rec).lower():
            return
        payload = json.dumps([rec["name"], rec["mfr"], rec["svc_data"], rec["svc_uuids"]])
        if not args.all and last.get(device.address) == payload:
            return
        last[device.address] = payload
        line = json.dumps({"t": round(time.time(), 3), **rec})
        print(line, flush=True)
        if out:
            out.write(line + "\n")
            out.flush()

    async def run() -> None:
        async with BleakScanner(on_adv):
            await asyncio.sleep(args.time)

    asyncio.run(run())


if __name__ == "__main__":
    main()
