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

## Get the code and unpack the archive
```sh
wget https://github.com/reserve85/HoymilesZeroExport/archive/refs/heads/main.zip
unzip main.zip
rm main.zip
mv HoymilesZeroExport-main/ HoymilesZeroExport/
```

## Installation of python and zero export service
in Linux
```sh
sudo chmod +x install.sh
./install.sh
```
or windows (cmd):
```sh
pip3 install requests
```

## Edit your configuration
```sh
sudo nano HoymilesZeroExport_Config.ini
```

## Restart the service after modified configuration or script
```sh
sudo chmod +x restart.sh
./restart.sh
```

## Showing the output-log
```sh
sudo journalctl -u HoymilesZeroExport.service -n 20000 -e -f
```

## Special thanks to:
- https://github.com/lumapu/ahoy
- https://github.com/tbnobody/OpenDTU
- https://tasmota.github.io/docs/Smart-Meter-Interface/
- https://ottelo.jimdofree.com/stromz%C3%A4hler-auslesen-tasmota/
- https://hessburg.de/tasmota-wifi-smartmeter-konfigurieren/
