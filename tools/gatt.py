"""Connect to a BLE device, dump its GATT table, read everything readable,
and log notifications. Read-only: never writes to a characteristic.

Usage:
  uv run tools/gatt.py AB123                 # match on advertised name substring
  uv run tools/gatt.py AB123 -t 120 -o captures/gatt.jsonl

The phone app must be closed (or phone Bluetooth off) first: the unit stops
advertising while something is connected to it.
"""

import argparse
import asyncio
import json
import time

from bleak import BleakClient, BleakScanner


def emit(out, **rec) -> None:
    line = json.dumps({"t": round(time.time(), 3), **rec})
    print(line, flush=True)
    if out:
        out.write(line + "\n")
        out.flush()


async def run(args) -> None:
    out = open(args.out, "a") if args.out else None
    needle = args.name.lower()

    print(f"scanning up to {args.find}s for name containing {args.name!r} ...", flush=True)
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: needle in (adv.local_name or d.name or "").lower(), timeout=args.find
    )
    if device is None:
        print("not found - is the phone app still connected to it?")
        return
    print(f"found {device.name} {device.address}, connecting ...", flush=True)

    async with BleakClient(device, timeout=30) as client:
        emit(out, ev="connected", addr=device.address, name=device.name, mtu=client.mtu_size)
        notify_chars = []
        for svc in client.services:
            for ch in svc.characteristics:
                value = None
                if "read" in ch.properties:
                    try:
                        value = (await client.read_gatt_char(ch)).hex()
                    except Exception as e:  # keep going: some chars need pairing
                        value = f"ERR {e}"
                emit(out, ev="char", svc=svc.uuid, char=ch.uuid, handle=ch.handle,
                     props=ch.properties, value=value,
                     desc=[d.uuid for d in ch.descriptors])
                if "notify" in ch.properties or "indicate" in ch.properties:
                    notify_chars.append(ch)

        for ch in notify_chars:
            def cb(_, data, uuid=ch.uuid):
                emit(out, ev="notify", char=uuid, value=bytes(data).hex())
            try:
                await client.start_notify(ch, cb)
            except Exception as e:
                emit(out, ev="notify_failed", char=ch.uuid, err=str(e))

        print(f"listening for notifications for {args.time}s ...", flush=True)
        await asyncio.sleep(args.time)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="substring of the advertised device name")
    ap.add_argument("-t", "--time", type=float, default=30, help="seconds to listen for notifications")
    ap.add_argument("--find", type=float, default=30, help="seconds to wait for the device to advertise")
    ap.add_argument("-o", "--out", help="append JSON lines to this file")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
