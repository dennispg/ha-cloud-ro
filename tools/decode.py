"""Decode a gatt.py capture of a Cloud RO into raw fields.

Usage: uv run tools/decode.py captures/gatt.jsonl

This prints raw structure so values can be matched against what the phone app
shows. Field meanings are in docs/PROTOCOL.md.
"""

import json
import struct
import sys
from datetime import datetime

SHORT = lambda uuid: uuid[4:8]  # 5e3c14XX-... -> 14XX

# Factory/service command characteristics: deliberately left undecoded.
SKIP = {"1410", "1411"}


def ts(n: int) -> str:
    return datetime.fromtimestamp(n).strftime("%Y-%m-%d %H:%M:%S")


def cstr(b: bytes) -> str:
    return b.split(b"\0")[0].decode("ascii", "replace")


def decode(char: str, b: bytes) -> str:
    if char == "1401":
        return f"firmware={cstr(b[:8])!r} u16@9={struct.unpack_from('<H', b, 9)[0]}"
    if char == "1402":
        # Only the first 16 bytes belong to 1402; the rest is whatever follows.
        return f"clock={ts(int(cstr(b[:16])))}"
    if char == "1403":
        return f"power_on={ts(int(cstr(b[:16])))}"
    if char == "1404":
        return f"u16={struct.unpack_from('<19H', b, 0)}"
    if char == "1405":
        return f"u32={struct.unpack_from('<I', b, 0)[0]} bytes={list(b[4:20])}"
    if char == "1406":
        months = struct.unpack_from("<12H", b, 0)
        total, count = struct.unpack_from("<IH", b, 24)
        recs = []
        for off in range(30, len(b) - 9, 10):
            t, a, c, d = struct.unpack_from("<IHHH", b, off)
            recs.append(f"{ts(t)} {a}/{c}/{d}")
        return f"u16x12={months} total={total} count={count}\n        " + "\n        ".join(recs)
    if char == "1407":
        t, a, c, d = struct.unpack_from("<IHHH", b, 0)
        return f"{ts(t)} {a}/{c}/{d} rest={b[10:].hex()}"
    return b.hex()


last: dict[str, str] = {}
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r["ev"] not in ("char", "notify") or not r.get("value") or r["value"].startswith("ERR"):
        continue
    char = SHORT(r["char"])
    if char in SKIP:
        continue
    text = decode(char, bytes.fromhex(r["value"]))
    if char == "1404":  # drop the 1 Hz uptime counter so only real changes print
        u = list(struct.unpack_from("<19H", bytes.fromhex(r["value"]), 0))
        u[15] = 0
        key = str(u)
    else:
        key = text
    if last.get(char) == key:
        continue
    last[char] = key
    print(f"{ts(r['t'])} {r['ev']:6} {char} {text}")
