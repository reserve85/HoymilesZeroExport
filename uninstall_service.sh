#!/bin/bash
if systemctl --type=service --state=running | grep -Fq 'HoymilesZeroExport.service'; then
  echo 'Uninstall HoymilesZeroExport.service'
  systemctl stop HoymilesZeroExport.service
  systemctl disable HoymilesZeroExport.service
  rm /etc/systemd/system/HoymilesZeroExport.service
  systemctl daemon-reload
  systemctl reset-failed
  echo 'Uninstallation of HoymilesZeroExport.service completed'
fi