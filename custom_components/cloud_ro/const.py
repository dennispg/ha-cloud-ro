"""Constants for the Cloud RO integration."""

from datetime import timedelta

DOMAIN = "cloud_ro"

SERVICE_UUID = "5e3c1400-0929-41b6-89ea-502be1edf8b0"
CHAR_FIRMWARE = "5e3c1401-0929-41b6-89ea-502be1edf8b0"
CHAR_LIVE = "5e3c1404-0929-41b6-89ea-502be1edf8b0"

# The unit advertises as "<serial>-CL".
NAME_SUFFIX = "-CL"

# Minutes between polls (an option). The unit is battery powered and accepts
# one connection at a time, so each poll connects briefly and disconnects.
CONF_POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = 5
MIN_POLL_INTERVAL = 1
MAX_POLL_INTERVAL = 1440

# A poll fails whenever the phone app holds the connection. Keep showing the
# last reading for at least this long (or three poll intervals, if longer)
# before the sensors go unavailable.
MIN_STALE_TIME = timedelta(hours=1)
