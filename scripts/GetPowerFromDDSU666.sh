
#!/bin/sh

# GetPowerFromDDSU666.sh
#
# Read grid power from a DDSU666 single-phase energy meter
# using Modbus RTU over a serial USB connection.
#
# Requirements:
#   - mbpoll
#   - bc
#
# Usage:
#   GetPowerFromDDSU666.sh <Device_Number>
#
# Modbus configuration:
#   Baud rate : 9600
#   Parity    : None
#   Register  : 8196 (Float, 32-bit)
#
# Hoymiles specific:
#   Positive meter values are converted to negative values.
#   Negative meter values are converted to positive values.
#
# Additional protections:
#   - Three Modbus read attempts
#   - Numeric validation
#   - Last valid measurement backup
#   - Maximum backup age of 30 seconds
#   - Asymmetric filtering of sudden power variations


# --------------------------------------------------
# Configuration
# --------------------------------------------------

DEVICE="/dev/ttyUSB0"
ADDRESS="$1"

LAST_FILE="/tmp/last_grid.txt"
TIME_FILE="/tmp/last_grid.timestamp"

MAX_AGE=30
FILTER_THRESHOLD=300

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

if ! command -v bc >/dev/null 2>&1; then
    echo "$0: bc must be installed!" >&2
    echo 0
    exit 1
fi

# --------------------------------------------------
# Function: Read power from DDSU666
# --------------------------------------------------

get_power() {

    for i in 1 2 3; do

        # Read Modbus register 8196
        VE_SYSTEM=$(
            mbpoll -a "$ADDRESS" -b 9600 -P none -B \
                -t 4:float -0 -r 8196 -c 1 -1 "$DEVICE" 2>&1 |
            grep -E '\[8196\]:'
        )

        if [ $? -eq 0 ]; then

            # Extract register value
            RAW_VALUE=$(
                echo "$VE_SYSTEM" |
                awk -F':' '{
                    gsub(/^[ \t]+|[ \t]+$/, "", $2)
                    print $2
                    exit
                }'
            )

            # Validate numeric value
            if echo "$RAW_VALUE" |
                grep -qE '^-?[0-9]+([.][0-9]+)?$'; then

                echo "$RAW_VALUE"
                return 0
            fi
        fi

        # Short delay before retry
        sleep 0.4

    done

    # All Modbus attempts failed
    return 1
}

# --------------------------------------------------
# Read current power
# --------------------------------------------------

RAW=$(get_power)
READ_STATUS=$?

if [ "$READ_STATUS" -eq 0 ]; then

    # Convert kW into W
    AC_GRID=$(echo "$RAW * 1000" | bc)

    # Keep integer power value
    AC_GRID=$(printf "%.0f" "$AC_GRID")

    # Hoymiles specific sign conversion
    AC_GRID=$(( -1 * AC_GRID ))

    FRESH_DATA=1

else

    # Modbus communication failed
    FRESH_DATA=0

    # Check whether a previous measurement exists
    if [ -f "$LAST_FILE" ] && [ -f "$TIME_FILE" ]; then

        LAST=$(cat "$LAST_FILE")
        LAST_TIME=$(cat "$TIME_FILE")
        NOW=$(date +%s)

        # Validate previous measurement and timestamp
        if echo "$LAST" | grep -qE '^-?[0-9]+$' &&
           echo "$LAST_TIME" | grep -qE '^[0-9]+$'; then

            AGE=$(( NOW - LAST_TIME ))

            # Reuse previous value only if still recent
            if [ "$AGE" -ge 0 ] && [ "$AGE" -le "$MAX_AGE" ]; then
                AC_GRID="$LAST"
            else
                AC_GRID=0
            fi
        else
            AC_GRID=0
        fi

    else
        AC_GRID=0
    fi

fi

# --------------------------------------------------
# Filter sudden power variations
# --------------------------------------------------

# Apply filtering only to fresh measurements
if [ "$FRESH_DATA" -eq 1 ] && [ -f "$LAST_FILE" ]; then

    LAST=$(cat "$LAST_FILE")

    # Validate previous value before arithmetic
    if echo "$LAST" | grep -qE '^-?[0-9]+$'; then

        DIFF=$(( AC_GRID - LAST ))

        # Asymmetric filtering:
        # Large negative variations are smoothed.
        # Positive variations are kept immediately.
        if [ "$DIFF" -lt "-$FILTER_THRESHOLD" ]; then

            AC_GRID=$(( (AC_GRID + LAST * 3) / 4 ))

        fi
    fi
fi

# --------------------------------------------------
# Save fresh valid measurement
# --------------------------------------------------

if [ "$FRESH_DATA" -eq 1 ]; then

    echo "$AC_GRID" > "$LAST_FILE"

    # Store timestamp of last successful Modbus reading
    date +%s > "$TIME_FILE"

fi

# --------------------------------------------------
# Return power value and communication status
# --------------------------------------------------

echo "$AC_GRID"

# Return 0 if Modbus reading was successful
# Return 1 if previous value was reused or zero was returned
if [ "$FRESH_DATA" -eq 1 ]; then
    exit 0
else
    exit 1
fi
