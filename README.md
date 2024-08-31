# Hoymiles Zero Export Control / Hoymiles Nulleinspeisung

## Introduction
Hoymiles Zero Export is a Python script for managing the power of the Hoymiles inverters to reduce the amount of the generated power to the grid. Based on the current power output, the script can automatically adjust the export limit of the inverter, allowing for optimal energy management.

## Prerequisites
Before running this script make sure you have a powermeter which outputs a negative power value in case of returning to the grid.
For example: the Holley DTZ541 shows -150W if the solar inverter is overproducing.
This script does not use MQTT, it's based on webapi communication.

### Supported Smart-Meter Modules:
- [Tasmota Smart Meter Interface](https://tasmota.github.io/docs/Smart-Meter-Interface/) (e.g. "[Hichi IR Lesekopf](https://www.ebay.de/sch/i.html?_ssn=hicbelm-8)" or equal)
- [Shelly EM, Shelly 3EM, Shelly 3EM Pro, Shelly 1PM, Shelly Plus 1PM](https://www.shelly.cloud/de/products/product-overview/shelly-3em-1)
- [SHRDZM Smartmeter Modul](https://cms.shrdzm.com/produkt/smartmeter-modul/)
- [Emlog ("electronic meter log")](https://weidmann-elektronik.de/Emlog_Projekt.html)
- [ioBroker](https://www.iobroker.net/) with [simpleAPI](https://github.com/ioBroker/ioBroker.simple-api)
- [HomeAssistant](https://www.home-assistant.io/)
- [Volkszaehler (VZLogger)](https://volkszaehler.org/)
- [ESPHome](https://esphome.io/)
- [Mitterbaur Amis IR Reader](https://www.mitterbaur.at/amis-leser.html)
- shell script based interface with examples for:
  - Victron Multiplus-II (via modbus TCP)
  - DDSU666 powermeter (via modbus TCP)
  - MSunPV powermeter (http API)
- easy to implement new smart meter modules supporting WebAPI / JSON

### Supported DTU and Inverters
- [Ahoy](https://github.com/lumapu/ahoy) - this script is developed with AHOY and therefore i recommend it
- [OpenDTU](https://github.com/tbnobody/OpenDTU)
- Hoymiles MI, HM, HMS and HMT-Series Inverter (--> all inverters that are supported by AHOY / OpenDTU)
-   **Note:** The Hoymiles inverters with a build-in DTU, like the HMS-xxxxW Series, **are not supported!**

### Support of battery powered Hoymiles Inverters
You can set various limits to support battery powered Hoymiles Inverters
- power-off limit
- limit reduction if battery voltage drops
- auto-power-on if battery voltage rises 

## Examples in Home-Assistant:
![qkeo2J4U](https://user-images.githubusercontent.com/111107925/222456008-947bfbf1-09b3-4639-97d0-cc88c5af2a72.png)
![IMG_E0136](https://user-images.githubusercontent.com/111107925/217559535-1b530738-67bc-4c29-a6f2-9aa4addce41d.JPG)

## Linux installation

Make sure you have Python 3.8 or greater installed:
```sh
python3 --version
```
if you don´t have python installed or an older version is on your machine, then [install or upgrade](https://docs.python.org/3.11/using/unix.html#on-linux) it

Get the code and unpack the archive:
```sh
wget https://github.com/reserve85/HoymilesZeroExport/archive/refs/heads/main.zip
unzip main.zip
rm main.zip
mv HoymilesZeroExport-main/ HoymilesZeroExport/
cd HoymilesZeroExport/
```

Launch installscript to create zero export service
```sh
sudo chmod +x install.sh
sudo ./install.sh
```
if you get an error like "error: externally-managed-environment" you´ll need to install the requirements manually with the following command:
```sh
pip install -r requirements.txt --break-system-packages
```

#### Configuration Variant A: 
Define your configuration:
edit `HoymilesZeroExport_Config_Override.ini`. 
You need to provide a configuration where you override individual values. 
To do that edit `HoymilesZeroExport_Config_Override.ini` and set the configuration values from `HoymilesZeroExport_Config.ini` you'd like to override. 
```sh
sudo nano HoymilesZeroExport_Config_Override.ini
```
The minimum content for using AhoyDTU with a Tasmota powermeter looks like this:
```
[SELECT_DTU]
USE_AHOY = true

[SELECT_POWERMETER]
USE_TASMOTA = true

[AHOY_DTU]
AHOY_IP = 192.168.10.57

[TASMOTA]
TASMOTA_IP = 192.168.10.90
...
```
Save with ctrl + s, exit with ctrl + x

#### Configuration Variant B: 

You can also edit the default configuration, but i recommend the procedure described above (Configuration Variant A:)

```sh
sudo nano HoymilesZeroExport_Config.ini
```
save with ctrl + s, exit with ctrl + x

Restart the service after modified configuration or script
```sh
sudo ./restart.sh
```

View the output log
```sh
sudo journalctl -u HoymilesZeroExport.service -n 20000 -e -f
```

If you really don´t want the service anymore, just uninstall it
```sh
sudo ./uninstall_service.sh
```

If you want to update the script to the latest version on Github:
```sh
sudo chmod +x update.sh
sudo ./update.sh
```

## Windows installation
Get Python 3 (download is available at https://www.python.org/) and then install the module "requests" and "packaging":
```sh
pip3 install -r requirements.txt
```
Now you can execute the script with python.

## Docker
By default the Docker image uses a base configuration in `HoymilesZeroExport_Config.ini`. You need to provide a configuration where you override individual values. To do that, create a new `HoymilesZeroExport_Config_Override.ini` and set the configuration values from `HoymilesZeroExport_Config.ini` you'd like to override. The minimum config file for using AhoyDTU with a Tasmota powermeter looks like this:
```
[SELECT_DTU]
USE_AHOY = true

[SELECT_POWERMETER]
USE_TASMOTA = true

[AHOY_DTU]
AHOY_IP = 192.168.10.57

[TASMOTA]
TASMOTA_IP = 192.168.10.90
```

Then run the Docker image:
```sh
docker run -d --name hoymileszeroexport \
    -v ${PWD}/HoymilesZeroExport_Config_Override.ini:/app/HoymilesZeroExport_Config_Override.ini \
    ghcr.io/reserve85/hoymileszeroexport:main -c ./HoymilesZeroExport_Config_Override.ini
```

Using docker-compose:
```yaml
version: '3.3'
services:
  hoymileszeroexport:
    image: ghcr.io/reserve85/hoymileszeroexport:main
    volumes:
      - ./HoymilesZeroExport_Config_Override.ini:/app/config.ini
    command: -c /app/config.ini
```

## MQTT
The script can optionally be controlled via MQTT. To enable this feature, you need to configure the `[MQTT_CONFIG]` section in the configuration file.
Once configured, the script will listen for incoming MQTT messages on the specified topic and act accordingly.
- `zeropower/set/powermeter_target_point`: To change the target point of the powermeter
- `zeropower/set/powermeter_max_point`: To change the max point of the powermeter
- `zeropower/set/powermeter_min_point`: To change the min point of the powermeter
- `zeropower/set/powermeter_tolerance`: To change the tolerance of the powermeter
- `zeropower/set/on_grid_usage_jump_to_limit_percent`: To change the on grid usage jump to limit percent
- `zeropower/set/on_grid_feed_fast_limit_decrease`: To enable or disable the on grid feed fast limit decrease
- `zeropower/set/inverter/0/min_watt_in_percent`: To change the min watt in percent of the first inverter
- `zeropower/set/inverter/0/normal_watt`: To change the battery normal watt of the first inverter
- `zeropower/set/inverter/0/reduce_watt`: To change the battery reduce watt of the first inverter
- `zeropower/set/inverter/0/battery_priority`: To change the battery priority of the first inverter
- `zeropower/set/inverter/<n>/*`: To change the settings of the (n+1)th inverter

To reset a setting to its original value, you can send an empty message to the corresponding topic replacing `set` with `reset`, e.g. `zeropower/reset/powermeter_target_point`.

Additionally, the script will publish the following MQTT messages:
- `zeropower/status`: The current status of the script. Possible values are `online` and `offline`
- `zeropower/state/powermeter_target_point`: The current target point of the powermeter
- `zeropower/state/powermeter_max_point`: The current max point of the powermeter
- `zeropower/state/powermeter_min_point`: The current min point of the powermeter
- `zeropower/state/powermeter_tolerance`: The current tolerance of the powermeter
- `zeropower/state/on_grid_usage_jump_to_limit_percent`: The current on grid usage jump to limit percent
- `zeropower/state/on_grid_feed_fast_limit_decrease`: The current on grid feed fast limit decrease
- `zeropower/state/inverter/0/min_watt_in_percent`: The current min watt in percent of the first inverter
- `zeropower/state/inverter/0/normal_watt`: The current battery normal watt of the first inverter
- `zeropower/state/inverter/0/reduce_watt`: The current battery reduce watt of the first inverter
- `zeropower/state/inverter/0/battery_priority`: The current battery priority of the first inverter
- `zeropower/state/inverter/<n>/*`: The current settings of the (n+1)th inverter

The script can also be configured to publish log messages to MQTT. To enable this feature, you need to set `MQTT_LOG_LEVEL` to `INFO`, which will publish all log messages to the topic `zeropower/log`.

## Special thanks to:
- https://github.com/lumapu/ahoy
- https://github.com/tbnobody/OpenDTU
- https://tasmota.github.io/docs/Smart-Meter-Interface/
- https://ottelo.jimdofree.com/stromz%C3%A4hler-auslesen-tasmota/
- https://hessburg.de/tasmota-wifi-smartmeter-konfigurieren/

## Donate and become a Sponsor
[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif)](https://paypal.me/TobiasWKraft/5)

Please support me if you like this project by spending me a coffee instead of giving away your electricity.
