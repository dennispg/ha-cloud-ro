# Cloud RO for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/github/license/dennispg/ha-cloud-ro.svg)](LICENSE)

[![Open Cloud RO inside your Home Assistant Community Store (HACS).](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dennispg&repository=ha-cloud-ro&category=integration)

A Home Assistant custom integration for the
[Cloud RO](https://www.cloudwaterfilters.com/) under-sink reverse osmosis
filter.

The Cloud RO only talks Bluetooth to its phone app. This integration reads the
filter directly over Bluetooth Low Energy, through any Bluetooth adapter or
Bluetooth proxy Home Assistant already uses. No cloud account, no app, and no
changes to the filter.

> **Status: early.** The protocol was worked out from a single unit on firmware
> `V1.05`. The integration passes its tests inside a Home Assistant test
> harness with Bluetooth mocked, but has had little time against real hardware.
> Some values are still unidentified (see [What's missing](#whats-missing)).
> This project is not affiliated with or endorsed by Cloud Water Filters.

## What you get

| Entity | Unit | Notes |
|---|---|---|
| TDS inlet | ppm | Tap water going in |
| TDS filtered | ppm | After the RO membrane |
| TDS remineralized | ppm | What comes out of the faucet |
| Membrane rejection | % | Calculated: how much of the inlet TDS the membrane removes |
| Total water | gal | Lifetime total; matches "total gallons consumed" in the app. Home Assistant shows litres on metric systems. |
| Battery | % | Unconfirmed, treat as approximate |
| Battery voltage | V | Unconfirmed, treat as approximate |

Readings refresh every 5 minutes by default; see [Options](#options).

## What you need

- A Cloud RO with its Bluetooth monitor working (it shows up in the Cloud app).
- Home Assistant with the Bluetooth integration set up, and **a connectable
  Bluetooth adapter or proxy within range of the filter**, a few metres at
  most. Either of these works:
  - a Bluetooth adapter on the Home Assistant machine, or
  - an [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy/)
    with `active: true`. A passive proxy is not enough, because the integration
    has to connect to the filter.

## Install

### HACS

The quick way: click the button below, confirm adding the repository, download
**Cloud RO**, and restart Home Assistant.

[![Open Cloud RO inside your Home Assistant Community Store (HACS).](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dennispg&repository=ha-cloud-ro&category=integration)

Or add it by hand:

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/dennispg/ha-cloud-ro` with type **Integration**.
3. Find **Cloud RO** in HACS, download it, and restart Home Assistant.

### Manual

Copy the `custom_components/cloud_ro` folder from this repo into the
`custom_components` folder of your Home Assistant config directory, then
restart Home Assistant.

## Set up

1. **Close the Cloud phone app**, or turn off Bluetooth on your phone. The
   filter accepts one connection at a time and is invisible to everything else
   while the app is connected.
2. Go to **Settings → Devices & services**. The filter should appear under
   *Discovered* within a minute or so; choose **Add**.
3. If it isn't discovered, choose **Add integration**, search for **Cloud RO**,
   and pick your filter from the list. This button does the same thing:

   [![Add Cloud RO to your Home Assistant.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=cloud_ro)

There is nothing to configure: no MAC address or serial number to type in. If
you have more than one filter, each is listed by its serial number, which you
can check in the Cloud app under **Account → Cloud Devices**. (The filter's
Bluetooth name is the serial followed by `-CL`, for example `AB123-CL`.) If
Home Assistant hasn't seen the filter's name yet, it is listed by its Bluetooth
address instead.

## Options

On the integration's page (**Settings → Devices & services → Cloud RO**),
choose **Configure** to change the one setting:

| Option | Default | Range | Meaning |
|---|---|---|---|
| Poll interval | 5 minutes | 1 to 1440 minutes | How often Home Assistant connects to the filter and reads it |

## Things to know

- **The phone app and Home Assistant take turns.** Home Assistant connects for
  a few seconds per poll and then lets go, so the app works normally the rest
  of the time. If the app is open and connected when a poll is due, that poll
  is skipped and the sensors keep their last values. If no poll succeeds for an
  hour (or three poll intervals, if that is longer), the sensors become
  unavailable.
- **Polling costs battery.** The filter's monitor runs on batteries, and each
  connection uses some. The effect on battery life has not been measured; if
  your batteries drain faster than before, raise the poll interval. The
  readings change slowly, so little is lost by polling less often.
- **Read-only.** The integration never writes to the filter.

## Troubleshooting

- **"No Cloud RO found".** The phone app is probably still connected; close it
  fully. Otherwise check that your adapter or proxy is connectable and close
  enough. The filter usually sits inside a cabinet, which blocks a lot of
  signal.
- **Setup keeps retrying.** Home Assistant can see the filter but can't connect
  to it. This is nearly always range, or a proxy without `active: true`.
- **Values look wrong.** Your firmware may lay its data out differently. Please
  open an issue with your firmware version (shown on the device page), and see
  below for how to capture what your unit sends.

## What's missing

- **Tank level.** The app shows it, but the field hasn't been identified yet.
- **Filter life.** The unit doesn't appear to send a per-filter percentage; the
  app likely calculates it from a stored date and water usage.
- **Usage history and TDS history.** The unit stores both and the format is
  mostly understood, but the integration doesn't expose them.

Details of every characteristic, including the unidentified fields, are in
[docs/PROTOCOL.md](docs/PROTOCOL.md).

## Helping decode the rest

The [tools/](tools/) folder has the scripts used to work out the protocol. They
need [uv](https://docs.astral.sh/uv/) and a computer with Bluetooth near the
filter. Close the Cloud app before running them, and note that Home Assistant
may hold the connection for a few seconds if a refresh happens to be running.

```sh
# Is the unit advertising? Look for <serial>-CL
uv run tools/scan.py -t 30 -f "-CL"

# Connect, dump every characteristic, and log notifications for two minutes
uv run tools/gatt.py AB123 -t 120 -o captures/gatt.jsonl

# Print the capture as decoded fields, showing only changes
uv run tools/decode.py captures/gatt.jsonl
```

`gatt.py` only reads; it never writes to the unit. Captures go in `captures/`,
which is git-ignored because a raw scan records every nearby Bluetooth device.

The most useful contribution is a capture taken while something known is
happening, with a note of what the app showed: draw a few litres so the tank
drains and refills, or capture just before and after a filter change.

## Development

```sh
# Parser tests only (fast, no Home Assistant needed)
uv run pytest

# Everything, inside a Home Assistant test harness with Bluetooth mocked
uv run --no-project --with-requirements requirements-test.txt pytest
```

## License

[MIT](LICENSE)
