#! /bin/sh

# Script to read powermeter values from a DDSU666 Monophase
# Needs "mbpoll" (command line utility to communicate with ModBus slave) to be installed, e.g. "apt install mbpoll"
# Usage: GetPowerFromDDSU666 <Device_Number>

# read registers 8196 via ModbusTCP

VE_SYSTEM=$(mbpoll -a "$1" -b 9600 -P none -B -t 4:float -0 -r 8196 -c 1 -1 /dev/ttyUSB0 | grep "\[.*\]:")
if [ $? -ne 0 ]; then
        # failed, one more try
        sleep 1
        VE_SYSTEM=$(mbpoll -a "$1" -b 9600 -P none -B -t 4:float -0 -r 8196 -c 1 -1 /dev/ttyUSB0 | grep "\[.*\]:")
        if [ $? -ne 0 ]; then
                type mbpoll > /dev/null 2>&1
                if [ $? -ne 0 ]; then
                        echo "$0: mbpoll must be installed!"
                else
                        echo 0
                fi
                exit 1
        fi
fi

# Get AC_GRID Value in KW
AC_GRID=$(echo "$VE_SYSTEM" | sed -n -e "s/.*\[8196\]:[[:space:]]*\(-*[0-9]*\.[0-9]*\).*/\1/p")

# Check that AC_GRID is not empty meaning that the GRID return 0
if [ -z "$AC_GRID" ]; then
   AC_GRID=$(echo "$VE_SYSTEM" | sed 's/.*: *\(.*\)$/\1/')
else
# Convert KW in W
   AC_GRID=$(echo "$AC_GRID * 1000" | bc)
fi

#  Keep the integer part only
AC_GRID=$(echo "$AC_GRID" | cut -d'.' -f1)

# Check if AC_GRID is a number
if echo "$AC_GRID" | grep -qE '^-*[0-9]+(\.[0-9]+)?$'; then
    # DSSU666 Hoymiles specific if AC_GRID is positive set it as a Negative value because solar inverter are OverProduction
    if [ "$(echo "$AC_GRID >= 0" | bc -l)" -eq 1 ]; then
        AC_GRID=$(echo "$AC_GRID" | awk '{print ($1 < 0) ? -$1 : -$1}')
    else
    # DSSU666 Hoymiles specific AC_GRID is negative set it as a Positive value solar inverter are notProducing enough
        AC_GRID=$(echo "$AC_GRID" | awk '{print ($1 < 0) ? -$1 : $1}')
    fi
else
    echo "AC_GRID is not a valid number."
fi

echo "$AC_GRID"

