"""Decode a gatt.py capture of a Cloud RO into candidate fields.

Usage: uv run tools/decode.py captures/gatt.jsonl

Field meanings are still being worked out; this prints raw structure so values
can be matched against what the phone app shows.
"""

import json
import struct
import sys
from datetime import datetime

SHORT = lambda uuid: uuid[4:8]  # 5e3c14XX-... -> 14XX


def ts(n: int) -> str:
    return datetime.fromtimestamp(n).strftime("%Y-%m-%d %H:%M:%S")


def cstr(b: bytes) -> str:
    return b.split(b"\0")[0].decode("ascii", "replace")


def decode(char: str, b: bytes) -> str:
    if char == "1401":
        return f"firmware={cstr(b[:8])!r} u16@9={struct.unpack_from('<H', b, 9)[0]}"
    if char == "1402":
        now, since = cstr(b[:16]), cstr(b[16:32])
        u32 = struct.unpack_from("<10I", b, 32)
        return f"clock={ts(int(now))} since={ts(int(since))} u32={u32}"
    if char == "1403":
        since = cstr(b[:16])
        u32 = struct.unpack_from("<10I", b, 16)
        dbl = struct.unpack_from("<5d", b, 56)
        return f"since={ts(int(since))} u32={u32} doubles={[round(x, 3) for x in dbl]}"
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
    if char in ("1410", "1411"):
        return repr(cstr(b))
    return b.hex()


last: dict[str, str] = {}
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r["ev"] not in ("char", "notify") or not r.get("value") or r["value"].startswith("ERR"):
        continue
    char = SHORT(r["char"])
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
