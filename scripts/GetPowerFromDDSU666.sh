#!/bin/sh

# GetPowerFromDDSU666.sh
#
# Read grid power from a DDSU666 single-phase energy meter
# using Modbus RTU over a serial USB connection.
#
# Requirements:
#   - mbpoll (e.g. "apt install mbpoll")
#
# Usage (SCRIPT_IP in the [SCRIPT] section is passed as <Device_Number>):
#   GetPowerFromDDSU666.sh <Device_Number>
#
# Modbus configuration:
#   Baud rate : 9600
#   Parity    : None
#   Register  : 8196 (Float, 32-bit, kW)
#
# Hoymiles specific:
#   The DDSU666 reports feed-in as positive and grid usage as negative.
#   The sign is inverted, so the script prints grid usage as positive watts.
#
# Output:
#   One integer value in watts, exit code 0.
#   On a read error "0" is printed and the exit code is 1, so HoymilesZeroExport
#   treats it as a powermeter error (see SET_INVERTER_TO_MIN_ON_POWERMETER_ERROR).
#
# Optional filter (disabled by default):
#   With FILTER_THRESHOLD > 0, a drop of more than FILTER_THRESHOLD watts compared
#   to the previous reading is smoothed: only a quarter of the drop is reported per
#   reading. This reduces sudden limit cuts on noisy readings (e.g. at low production),
#   but feed-in after a load switches off lasts longer and ON_GRID_FEED_FAST_LIMIT_DECREASE
#   triggers later.

# --------------------------------------------------
# Configuration
# --------------------------------------------------

DEVICE="/dev/ttyUSB0"
ADDRESS="$1"

# 0 = filter disabled. Example: FILTER_THRESHOLD=300
FILTER_THRESHOLD=0

# the previous reading is only used for filtering if it is not older than this
MAX_AGE=30

# decimal point in mbpoll output and awk, independent of the system language
LC_ALL=C
export LC_ALL

# --------------------------------------------------
# Check required parameters and dependencies
# --------------------------------------------------

if [ -z "$ADDRESS" ]; then
    echo "Usage: $0 <Device_Number>" >&2
    echo 0
    exit 1
fi

if ! command -v mbpoll >/dev/null 2>&1; then
    echo "$0: mbpoll must be installed!" >&2
    echo 0
    exit 1
fi

# one state file per device address, so several meters do not mix their values
STATE_FILE="${TMPDIR:-/tmp}/GetPowerFromDDSU666_${ADDRESS}.last"

# --------------------------------------------------
# Read power from DDSU666 (kW), three attempts
# --------------------------------------------------

get_power() {
    for i in 1 2 3; do
        RAW_VALUE=$(
            mbpoll -a "$ADDRESS" -b 9600 -P none -B \
                -t 4:float -0 -r 8196 -c 1 -1 "$DEVICE" 2>/dev/null |
            sed -n -e 's/.*\[8196\]:[[:space:]]*\([^[:space:]]*\).*/\1/p' |
            head -n 1
        )

        # accept plain and exponent notation, e.g. 0.123, -1, 1.5e-03
        if echo "$RAW_VALUE" | grep -qE '^-?[0-9]+([.][0-9]+)?([eE][-+]?[0-9]+)?$'; then
            echo "$RAW_VALUE"
            return 0
        fi

        [ "$i" -lt 3 ] && sleep 1
    done
    return 1
}

if ! RAW=$(get_power); then
    echo "$0: no valid reading from DDSU666 at address $ADDRESS on $DEVICE" >&2
    echo 0
    exit 1
fi

# kW -> W, rounded, sign inverted for Hoymiles
AC_GRID=$(awk -v kw="$RAW" 'BEGIN { w = -kw * 1000; printf "%d\n", (w < 0) ? w - 0.5 : w + 0.5 }')

# --------------------------------------------------
# Optional filter for sudden drops
# --------------------------------------------------

NOW=$(date +%s)

if [ "$FILTER_THRESHOLD" -gt 0 ] && [ -f "$STATE_FILE" ]; then
    read -r LAST LAST_TIME < "$STATE_FILE"
    if echo "$LAST" | grep -qE '^-?[0-9]+$' &&
       echo "$LAST_TIME" | grep -qE '^[0-9]+$'; then
        AGE=$(( NOW - LAST_TIME ))
        DIFF=$(( AC_GRID - LAST ))
        if [ "$AGE" -ge 0 ] && [ "$AGE" -le "$MAX_AGE" ] &&
           [ "$DIFF" -lt "-$FILTER_THRESHOLD" ]; then
            AC_GRID=$(( (AC_GRID + LAST * 3) / 4 ))
        fi
    fi
fi

if [ "$FILTER_THRESHOLD" -gt 0 ]; then
    echo "$AC_GRID $NOW" > "$STATE_FILE"
fi

echo "$AC_GRID"
exit 0
