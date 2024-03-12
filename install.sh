#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

chmod +x $SCRIPT_DIR/HoymilesZeroExport.py
chmod +x $SCRIPT_DIR/restart.sh
chmod +x $SCRIPT_DIR/uninstall_service.sh
chmod +x $SCRIPT_DIR/update.sh

PIP3=$(which pip3)

echo 'Installing packages'
if [ -z $PIP3 ]; then
  apt update
  apt -y install python3-pip
fi
pip3 install -r requirements.txt
echo 'Packages install completed'

if systemctl --type=service --state=running | grep -Fq 'HoymilesZeroExport.service'; then
  echo 'Uninstall HoymilesZeroExport.service'
  systemctl stop HoymilesZeroExport.service
  systemctl disable HoymilesZeroExport.service
  rm /etc/systemd/system/HoymilesZeroExport.service
  systemctl daemon-reload
  systemctl reset-failed
  echo 'Uninstallation of HoymilesZeroExport.service completed'
fi

if [ ! -f "${SCRIPT_DIR}/HoymilesZeroExport_Config_Override.ini" ]; then
    touch "${SCRIPT_DIR}/HoymilesZeroExport_Config_Override.ini"
	chmod u=rw,g=rw,o=rw "$SCRIPT_DIR/HoymilesZeroExport_Config_Override.ini"
fi

cat << EOF | tee /etc/systemd/system/HoymilesZeroExport.service
[Unit]
Description=HoymilesZeroExport Service
After=multi-user.target
[Service]
Type=simple
Restart=always
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/HoymilesZeroExport.py -c ${SCRIPT_DIR}/HoymilesZeroExport_Config_Override.ini
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable HoymilesZeroExport.service
systemctl start HoymilesZeroExport.service
systemctl status HoymilesZeroExport.service

echo 'Installation of HoymilesZeroExport completed'
