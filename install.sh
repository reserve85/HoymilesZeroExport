#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

PIP3=$(which pip3)

echo 'Installing packages'
if [ -z $PIP3 ]; then
  sudo apt update
  sudo apt -y install python3-pip
fi
sudo pip install requests

cat << EOF | sudo tee /etc/systemd/system/HoymilesZeroExport.service
[Unit]
Description=HoymilesZeroExport Service
After=multi-user.target
[Service]
Type=simple
Restart=always
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/HoymilesZeroExport.py
[Install]
WantedBy=multi-user.target
EOF

sudo chmod 644 /usr/lib/systemd/system/HoymilesZeroExport.service
sudo systemctl daemon-reload
sudo systemctl enable HoymilesZeroExport.service
sudo systemctl stop HoymilesZeroExport.service
sudo systemctl start HoymilesZeroExport.service
sudo systemctl status HoymilesZeroExport.service

echo "Installation of HoymilesZeroExport completed"