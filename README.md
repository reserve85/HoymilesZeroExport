# HoymilesZeroExport
Zero Export Script for Hoymiles Inverters by using AhoyDTU and Tasmota Smart Meter inferface

## Thanks to:
- https://github.com/lumapu/ahoy
- https://tasmota.github.io/docs/Smart-Meter-Interface/
- https://ottelo.jimdofree.com/stromz%C3%A4hler-auslesen/

You need to modify the following variables with your own values:
- ahoyIP = '192.168.10.57'
- tasmotaIP = '192.168.10.90'
- hoymilesInverterID = 0
- hoymilesMaxWatt = 1500 # maximum limit in watts (100%)
- hoymilesMinWatt = int(hoymilesMaxWatt / 10) # minimum limit in watts (should be around 10% of maximum inverter power)
- hoymilesPosOffsetInWatt = 50 # positive poweroffset in Watt, used to allow some watts more to produce. It's like a reserve

This script does not use MQTT, its based on webapi.

### install as service:
```sh
sudo nano /etc/systemd/system/HoymilesZeroExport.service
```

### insert the following text:
```sh
[Unit]
Description=HoymilesZeroExport Service
After=multi-user.target
[Service]
Type=simple
Restart=always
ExecStart=/usr/bin/python3 /path/to/your/HoymilesZeroExport.py
[Install]
WantedBy=multi-user.target
```

### to start service:
```sh
sudo systemctl daemon-reload
sudo systemctl enable HoymilesZeroExport.service 
sudo systemctl start HoymilesZeroExport.service
```

### check the service if it is running correctly:
```sh
sudo systemctl status HoymilesZeroExport.service
```
