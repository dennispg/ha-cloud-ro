"""Summarize a scan.py capture: one row per device, with how many distinct payloads it sent.

Usage: uv run tools/summarize.py captures/survey.jsonl
"""

import json
import sys
from collections import defaultdict

devs: dict[str, dict] = defaultdict(
    lambda: {"names": set(), "payloads": set(), "uuids": set(), "rssi": [], "n": 0}
)
for line in open(sys.argv[1]):
    r = json.loads(line)
    d = devs[r["addr"]]
    d["n"] += 1
    d["rssi"].append(r["rssi"])
    if r["name"]:
        d["names"].add(r["name"])
    d["uuids"].update(u[4:8] if u.endswith("-0000-1000-8000-00805f9b34fb") else u for u in r["svc_uuids"])
    for k, v in r["mfr"].items():
        d["payloads"].add(f"mfr {k}: {v}")
    for k, v in r["svc_data"].items():
        d["payloads"].add(f"svc {k[4:8]}: {v}")

for addr, d in sorted(devs.items(), key=lambda kv: -max(kv[1]["rssi"])):
    print(f"{addr[:8]}  rssi {max(d['rssi']):4d}  lines {d['n']:3d}  "
          f"name={sorted(d['names']) or '-'}  uuids={sorted(d['uuids']) or '-'}")
    for p in sorted(d["payloads"])[:8]:
        print(f"      {p}")
    if len(d["payloads"]) > 8:
        print(f"      ... {len(d['payloads']) - 8} more distinct payloads")
