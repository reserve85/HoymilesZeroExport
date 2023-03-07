#!/bin/bash
sudo systemctl stop HoymilesZeroExport.service
sudo systemctl start HoymilesZeroExport.service
echo "restart of HoymilesZeroExport completed"