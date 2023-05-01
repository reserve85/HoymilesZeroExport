# Changelog

## V1.30
### Script
* use different wait time for turning inverter off or on
* add HOME ASSISTANT support
### Config
* add: `[COMMON]`: `SET_POWER_STATUS_DELAY_IN_SECONDS` - delay time after turning the inverter off or on
* add: `[SELECT_POWERMETER]`: `USE_HOMEASSISTANT`
* add: section `[HOMEASSISTANT]` + section `[INTERMEDIATE_HOMEASSISTANT]`
* add: `[SELECT_INTERMEDIATE_METER]`: `USE_HOMEASSISTANT_INTERMEDIATE`

## V1.29
### Script
* on Startup: initialize inverter with lowest limit.
* allow to send same Limits to inverter, use SET_LIMIT_RETRY to limit the repeats

## V1.28
### Script
* add HOY_BATTERY_NORMAL_WATT: you can further limit the inverter in battery mode. E.g. if you have a 1500W Inverter you can limit the max. output power in battery mode to 750 Watts.
### Config
* add: `[INVERTER_x]`: `HOY_BATTERY_NORMAL_WATT`

## V1.27
### Script
* bugfix: Assign problem when reading INI if more than two inverters
* bugfix: changed a += operator because "unsupported operand type s for +:" occur

## V1.26
### Script
* bugfix: SetLimitOpenDTU: there was a calculation error if battery powered and reduced limit was active.
* add ´HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V´: if min_voltage of a panel is higher than this threshold voltage, then max_limit is reset to "max_Watt"
### Config
* add: `[INVERTER_x]`: `HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V`

## V1.25
### Script
* add: support of battery powered hoymiles inverters. activate it by setting `[INVERTER_x]/HOY_BATTERY_MODE` to `true`. 
There is an "off" Limit (`HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V`) where the inverter stops working, if panel voltage is lower
a "reduce" limit (`HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V`) where the inverter reduces it´s max. power, if panel voltage is lower
a "turn on" limit (`HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V`) where the inverter starts working again, if panel voltage is higher
### Config
* add: `[INVERTER_x]`: `HOY_BATTERY_MODE` + `HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V` + `HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V` + `HOY_BATTERY_REDUCE_WATT` + `HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V`

## V1.24
### Script
* add: support of IOBROKER. Needs installed https://github.com/ioBroker/ioBroker.simple-api
* change: more detailed exception logs
### Config
* add: `[SELECT_POWERMETER]`: `USE_IOBROKER`
* add: section `[IOBROKER]` + section `[INTERMEDIATE_IOBROKER]`
* add: `[SELECT_INTERMEDIATE_METER]`: `USE_IOBROKER_INTERMEDIATE`

## V1.23
### Script
* bugfix: ignore LastLimit Counter if inverter was not available

## V1.22
### Script
* bugfix: switch °C to degC, due to compatibility

## V1.21
### Script
* bugfix: openDTU, GetHoymilesAvailable was faulty
* change: use default Log-Names to ensure deletion of old files
* add: optional: read out temperature
* add: read out serial number of inverter
### Config
* add: `LOG_TEMPERATURE = false`
* removed: `SERIAL_NUMBER`, read it from API

## V1.20
### Script
* bugfix: intervall was too fast only in case of setLimit > SET_LIMIT_RETRY
* change: small code optimization for setting limit to multiple inverters

## V1.19
### Script
* script keeps running as long as minimum one inverter is available

## V1.18
### Script
* bugfix: intermediate meter Shelly 1PM did not work
* add: support Shelly 3EM Pro for powermeter and intermediate powermeter
* add: support of Shelly 1PM & Shelly Plus 1PM
### Config
* add: `[SELECT_POWERMETER]`: `USE_SHELLY_3EM_PRO`
* add: `[SELECT_INTERMEDIATE_METER]`: `USE_SHELLY_3EM_PRO_INTERMEDIATE`
* add: `[SELECT_INTERMEDIATE_METER]`: `USE_SHELLY_PLUS_1PM_INTERMEDIATE`

## V1.17
### Script
* add: support EMLOG System for powermeter and intermediate powermeter
* change: added powermeter-type and DTU-type to logs
### Config
* add: In Section `[SELECT_POWERMETER]`: `USE_EMLOG`
* add: Section `[EMLOG]`: `EMLOG_IP` + `EMLOG_METERINDEX`
* add: Section `[INTERMEDIATE_EMLOG]`: `EMLOG_IP_INTERMEDIATE` + `EMLOG_METERINDEX_INTERMEDIATE`

## V1.16
### Script
* add: support Shelly 1PM as intermediate meter
* bugfix: selection of intermediate meter was incorrect.
### Config
* add: In Section `[SELECT_INTERMEDIATE_METER]`: `USE_SHELLY_1PM_INTERMEDIATE`

## V1.15
### Script
* change: replace fixed factor for slow approximation with configurable one (SLOW_APPROX_FACTOR_IN_PERCENT)
* change: check if slow approx is really needed when old limit was 100% (jump down)
* change: calculate "LimitDifference" based on ActualPower and not on MaxWatt in case of old limit was at 100% (jump down)
### Config
* add: In Section `[COMMON]`: `SLOW_APPROX_FACTOR_IN_PERCENT = 20`
### Bash script
* change: update install.sh script for reinstall
* add: uninstall_service.sh script to uninstall the service

## V1.14
### Script
* add: limit the retry of function `SetLimit` if it is the same limit in watt
### Config
* add: In Section `[COMMON]`: `SET_LIMIT_RETRY = 10`

## V1.13
### Script
* Removed: Intermediate meter calculation option
### Config
* Removed: defines for Intermediate meter calculation option: `TASMOTA_JSON_POWER_CALCULATE = FALSE`, `TASMOTA_JSON_POWER_INPUT_MQTT_LABEL`, `TASMOTA_JSON_POWER_OUTPUT_MQTT_LABEL`

## V1.12
### Script
* Add: Intermediate meter support. If you have an intermediate meter behind your solar inverters to measure the exact outputpower, you can set it here. It's faster than the Ahoy/OpenDTU current_power value.
* Changed: some logger.info type to logger.error (if it is in try...except)
* Changed: only load the HoymilesZeroExport_Config.ini once
### Config
* Add: Section `[SELECT_INTERMEDIATE_METER]`, `[INTERMEDIATE_TASMOTA]`, `[INTERMEDIATE_SHELLY_3EM]`, `[INTERMEDIATE_SHRDZM]` in Config

## V1.11
### Script
* Bugfix: filename of midnight rolling backup-logfiles was "today" but should be "yesterday".

## V1.10
### Script
* Bugfix for openDTU set limit, missing array index

## V1.9
### Script
* Add: SHRDZM Powermeter Interface 
* Add: an optional function CutLimitToProduction: prevents the setpoint from running away... 
* Changed: logging to ./log/daily.log, creates a new logfile on midnight
### Config
* Add: Section `[SHRDZM]` + `USE_SHRDZM` in Config (default disabled)
* Add: `MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER` (default disabled)
* Add: `ENABLE_LOG_TO_FILE` and `LOG_BACKUP_COUNT` (default disabled)
* Add: VERSION information
