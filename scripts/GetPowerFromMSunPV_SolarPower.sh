#! /bin/sh

# Script to read PV Solar power values from a MSunPV (ard-tek.com)
IFS=";"
#PV Solar power
AC_PV=$(curl -s http://MSunPV_IP/status.xml | tail -n 3 | (read var1 var2 var3; echo ${var2}))
echo ${AC_PV%%,*}