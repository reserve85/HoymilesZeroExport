#!/bin/bash
# Check if an argument is provided
if [ $# -gt 1 ]; then
  echo "Error: Too many arguments"
elif [ $# -eq 1 ]; then
  # Use custom URL if provided
  BRANCH="$1"
else
  # Default URL if no argument provided
  BRANCH="main"
fi
BASE_URL="https://github.com/reserve85/HoymilesZeroExport/archive/refs/heads/"
DOWNLOAD_URL="$BASE_URL$BRANCH.zip"

# Change directory to the script's directory
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

echo "Start update of HoymilesZeroExport"

# Download and unzip the file
wget "$DOWNLOAD_URL" -O $BRANCH.zip
unzip $BRANCH.zip
rm $BRANCH.zip

if [ $(dpkg-query -W -f='${Status}' rsync 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  apt-get install rsync;
fi

rsync -a HoymilesZeroExport-$BRANCH/ ./
rm -r HoymilesZeroExport-$BRANCH/

chmod +x $SCRIPT_DIR/install.sh
chmod +x $SCRIPT_DIR/HoymilesZeroExport.py
chmod +x $SCRIPT_DIR/restart.sh
chmod +x $SCRIPT_DIR/uninstall_service.sh
chmod +x $SCRIPT_DIR/update.sh

bash install.sh
bash restart.sh

echo "update of HoymilesZeroExport completed"