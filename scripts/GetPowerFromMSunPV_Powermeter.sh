#! /bin/sh

# Script to read powermeter values from a MSunPV (ard-tek.com)
IFS=";"
#Grid power
AC_GRID=$(curl -s http://MSunPV_IP/status.xml | tail -n 3 | (read var1 var2 var3; echo ${var1:7:20}))
echo ${AC_GRID%%,*}