# Hoymiles Zero Export Control with Tasmota Smart Meter Interface / Hoymiles Nulleinspeisung mit Tasmota Smart Meter Interface
Zero Export Script for Hoymiles Inverters by using AhoyDTU and Tasmota Smart Meter inferface.
It is tested with a Holley DTZ541 powermeter and a Hoymiles HM-1500 solar inverter.
This script needs a powermeter which outputs negative power values via the interfaces when returning to the grid.
For example: the Holley DTZ541 shows -150W (But it does not count the consumption counter backwards).


### You need to modify the following variables with your own values:
```sh
- ahoyIP = '192.168.10.57'
- tasmotaIP = '192.168.10.90'
- hoymilesInverterID = 0
- hoymilesMaxWatt = 1500 // maximum inverter limit in watts (100%)
- hoymilesMinWatt = int(hoymilesMaxWatt / 10) // minimum limit in watts (should be around 10% of maximum inverter power)
- hoymilesPosOffsetInWatt = 50 // positive poweroffset in Watt, used to allow some watts more to produce. It's like a reserve
```

This script does not use MQTT, its based on simple webapi.

you´ll only need to install Python (version 3 in my case, download is available at https://www.python.org/) and then install the module "requests"
```sh
sudo apt-get install python3-requests
```
or windows:
```sh
pip3 install requests
```

### To install this script as a service:
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

### to start the service:
```sh
sudo systemctl daemon-reload
sudo systemctl enable HoymilesZeroExport.service 
sudo systemctl start HoymilesZeroExport.service
```

### check the service if it is running correctly:
```sh
sudo systemctl status HoymilesZeroExport.service
```
## Thanks to:
- https://github.com/lumapu/ahoy
- https://tasmota.github.io/docs/Smart-Meter-Interface/
- https://ottelo.jimdofree.com/stromz%C3%A4hler-auslesen/
