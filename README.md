# Hoymiles Zero Export Control / Hoymiles Nulleinspeisung
## Supported Smart-Meter:
- [Tasmota Smart Meter Interface](https://tasmota.github.io/docs/Smart-Meter-Interface/) (e.g. "[Hichi IR Lesekopf](https://www.ebay.de/sch/i.html?_ssn=hicbelm-8)" or equal)
- [Shelly 3EM](https://www.shelly.cloud/de/products/product-overview/shelly-3em-1)
## Supported DTU
- [Ahoy](https://github.com/lumapu/ahoy)
- [OpenDTU](https://github.com/tbnobody/OpenDTU)

## Zero Export Script for Hoymiles Inverters.

This script needs a powermeter which can output a negative power value over the interface when returning some power to the grid.
For example: the Holley DTZ541 shows -150W if the solar inverter is overproducing.

This script does not use MQTT, its based on simple webapi.

Examples in Home-Assistant:

![qkeo2J4U](https://user-images.githubusercontent.com/111107925/222456008-947bfbf1-09b3-4639-97d0-cc88c5af2a72.png)
![IMG_E0136](https://user-images.githubusercontent.com/111107925/217559535-1b530738-67bc-4c29-a6f2-9aa4addce41d.JPG)


## Installation
you´ll only need to install Python (version 3 in my case, download is available at https://www.python.org/) and then install the module "requests"
```sh
sudo apt-get install python3-requests
```
or windows (cmd):
```sh
pip3 install requests
```

### install this script as a service:
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

### start the service:
```sh
sudo systemctl daemon-reload
sudo systemctl enable HoymilesZeroExport.service 
sudo systemctl start HoymilesZeroExport.service
```

### check if the service is running correctly:
```sh
sudo systemctl status HoymilesZeroExport.service
```
## Special thanks to:
- https://github.com/lumapu/ahoy
- https://github.com/tbnobody/OpenDTU
- https://tasmota.github.io/docs/Smart-Meter-Interface/
- https://ottelo.jimdofree.com/stromz%C3%A4hler-auslesen-tasmota/
- https://hessburg.de/tasmota-wifi-smartmeter-konfigurieren/
