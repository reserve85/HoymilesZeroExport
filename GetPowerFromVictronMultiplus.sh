#! /bin/sh

# Script to read powermeter values from a Victron Multiplus II 
# Needs "mbpoll" (command line utility to communicate with ModBus slave) to be installed, e.g. "apt install mbpoll"
# Usage: GetPowerFromVictronMultiplus <ip-address> [<username>] [<password>]


# read registers 820-822 via ModbusTCP
VE_SYSTEM=`mbpoll "$1" -a 100 -r 820 -c 3 -t 3 -0 -1 | grep "\[.*\]:"`
if [ $? -ne 0 ]; then
	# failed, one more try
	sleep 1
	VE_SYSTEM=`mbpoll "$1" -a 100 -r 820 -c 3 -t 3 -0 -1 | grep "\[.*\]:"`
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

# /Ac/Grid/L1/Power
AC_GRID_L1=`echo "$VE_SYSTEM" | sed -n -e "s/\[820\]:.*(\(.*\)).*/\1/p" -e "s/\[820\]:[^0-9][^0-9]*\(.*\)/\1/p"`

# /Ac/Grid/L2/Power
AC_GRID_L2=`echo "$VE_SYSTEM" | sed -n -e "s/\[821\]:.*(\(.*\)).*/\1/p" -e "s/\[821\]:[^0-9][^0-9]*\(.*\)/\1/p"`

# /Ac/Grid/L3/Power
AC_GRID_L3=`echo "$VE_SYSTEM" | sed -n -e "s/\[822\]:.*(\(.*\)).*/\1/p" -e "s/\[822\]:[^0-9][^0-9]*\(.*\)/\1/p"`

expr "$AC_GRID_L1" + "$AC_GRID_L2" + "$AC_GRID_L3"
