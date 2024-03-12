#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo "start update of HoymilesZeroExport"

wget https://github.com/reserve85/HoymilesZeroExport/archive/refs/heads/main.zip
unzip main.zip
rm main.zip

if [ $(dpkg-query -W -f='${Status}' rsync 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  apt-get install rsync;
fi

rsync -a HoymilesZeroExport-main/ ./
rm -r HoymilesZeroExport-main/

chmod +x $SCRIPT_DIR/install.sh
chmod +x $SCRIPT_DIR/HoymilesZeroExport.py
chmod +x $SCRIPT_DIR/restart.sh
chmod +x $SCRIPT_DIR/uninstall_service.sh
chmod +x $SCRIPT_DIR/update.sh

bash install.sh
bash restart.sh

echo "update of HoymilesZeroExport completed"