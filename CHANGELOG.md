# Changelog

## V1.90
### script
* fix HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V, see https://github.com/reserve85/HoymilesZeroExport/issues/174

## V1.89
### script
* Auto-retry failed requests
### config
* add `COMMON`: `MAX_RETRIES`
* add `COMMON`: `RETRY_STATUS_CODES`
* add `COMMON`: `RETRY_BACKOFF_FACTOR`

## V1.88
### script
* Refactoring: Reset all inverter data when inverter becomes unavailable

## V1.87
### script
* Add support for dynamic reconfiguration of config parameters via MQTT
### config
* Add optional section '[MQTT_CONFIG]' to config file. If present, the script will listen for MQTT messages to reconfigure various parameters at runtime.

## V1.86
### script
* Prepare config to support dynamic reconfiguration of various parameters

## V1.85
### script
* Added shell script based powermeter interface (USE_SCRIPT)
### config
* Added parameters for shell script based powermeter interface (SCRIPT_)
### bash script
* Added example shell script for usage with Victron Multiplus II (GetPowerFromVictronMultiplus.sh)
### 
* Updated supported interface list in README.md with new shell script based powermeter

## V1.84
### script
* Add support for priority mixed-mode (combination of battery powered and non-battery powered inverters).

## V1.83
### script
* Bugfix fallback value
### config
* added comment

## V1.82
### script
* read the power rating of each inverter from config file.
* calculate HOY_MIN_POWER based on the inverter power rating.
### config
* add HOY_INVERTER_WATT to INVERTER_x section

## V1.81
### script
* add option to enable/disable to set the inverter to min watts when the powermeter can´t be read out. https://github.com/reserve85/HoymilesZeroExport/issues/28#issuecomment-1967306742 + https://github.com/reserve85/HoymilesZeroExport/issues/74
### config
* add `COMMON`: `SET_INVERTER_TO_MIN_ON_POWERMETER_ERROR`

## V1.80
### script
* add ESPHome for intermediate power meter
* use absolute value for intermediate power value
### config
* add ESPHome fields

## V1.79
### script
* fix intermediate meter (HA, IOBroker): define a fallback value for POWER_CALCULATION (https://github.com/reserve85/HoymilesZeroExport/issues/144)

## V1.78
### script
* openDTU: don´t override serialnumber every time a inverter gets available
### config
* optional field in : `INVERTER_x`: `SERIAL_NUMBER`: If you use more than one inverter you should define the serialnumber(s) in the config. Else a mix-up of the inverters possible (only openDTU)

## V1.77
### script
* fixed wrong calculation "RemainingDelay"

## V1.76
### script
* removed SetLimitDelay + SetLimitDelayMultipleInverter
* improved loop-code
### Config
* removed `SET_LIMIT_DELAY_IN_SECONDS` + `SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER`

## V1.75
### script
* refactoring, all DTU commands moved into DTU class
* support newest version of openDTU (API changed, see https://github.com/tbnobody/OpenDTU/releases/tag/v24.2.12)
* set min Version of openDTU to v24.2.12
* support newest version of AhoyDTU (Authentication, removed Factor, see https://github.com/lumapu/ahoy/issues/1415)
* set min Version of AhoyDTU to 0.8.80
### Config
* renamed `AHOY_PASSWORD =` to `AHOY_PASS` (like openDTU)

## V1.74
### script
* reverted script to support AHOY >= '0.7.29'

## V1.73
### script
* Support of AHOY-DTU Authentication, https://github.com/reserve85/HoymilesZeroExport/issues/132 and https://github.com/lumapu/ahoy/issues/1415
### Config
* added `AHOY_PASSWORD =` to `AHOY_DTU`

## V1.72
### script
* Emlog fix https://github.com/reserve85/HoymilesZeroExport/issues/134 -> calculate power
### Config
* added `EMLOG_JSON_POWER_CALCULATE` to `EMLOG`

## V1.71
### script
* When intermediate meter is not available then try to get "ActualPower" from DTU
* on battery mode: set Inverter to min power on meter-error

## V1.70
### script
* refactoring, big big "thank you" to https://github.com/tomquist - i know it was overdue...

## V1.69
### script
* try to fix: Only repeat limit for the specific inverter (where limit was not acknowledged)

## V1.68
### script
* Only repeat limit for the specific inverter (where limit was not acknowledged)
### Config
* renamed `SET_LIMIT_RETRY` to `SET_POWERSTATUS_CNT`

## V1.67
### script
* Limit-Handling improved (if not acknowledged -> retransmit)

## V1.66
### script
* calculates an average of the "MinPanelVoltage", rel https://github.com/reserve85/HoymilesZeroExport/issues/120
### Config
* add: `INVERTER_x`: `HOY_BATTERY_AVERAGE_CNT`

## V1.65
### script
* bugfix set limit retry

## V1.64
### Config
* added up to 16 inverters in default config. This is needed for the override config.

## V1.63
### script
* support Ahoy Versions >= V 0.8.39 ( https://github.com/reserve85/HoymilesZeroExport/issues/116 )

## V1.62
### script
* added package argparse, install it with "pip3 install argparse" or "pip3 install -r requirements.txt"
* add support of docker (thnx to @tomquist)
* add support of a user specific ini (HoymilesZeroExport_Config_Override.ini) where you can define your specific default values. it will not be overritten when you install an update.
* modified install.sh script

## V1.61
### script
* Bugfix HOY_MIN_WATT_IN_PERCENT: set minWatt for each inverter

## V1.60
### script
* optimized init procedure
* improved some code snippets
### Config
* modified some comments

## V1.59
### script
* force setlimit after BATTERY_THRESHOLD was changed

## V1.58
### script
* bugfix: added index to HOY_BATTERY_PRIORITY

## V1.57
### script
* supports custom inverter priorities, for battery powered inverters only! UNTESTED!
* related: https://github.com/reserve85/HoymilesZeroExport/issues/95
### Config
* add: `INVERTER_x`: `HOY_BATTERY_PRIORITY`

## V1.56
### script
* Bugfix Get lowest panel voltage: return correct value, rel https://github.com/reserve85/HoymilesZeroExport/issues/99
* On Inverter-Power-On: set inverter to HOY_MIN_WATT, rel https://github.com/reserve85/HoymilesZeroExport/issues/100

## V1.55
### script
* Bugfix Get Lowest panel voltage with more than one inverter.

## V1.54
### script
* Bugfix at GetNumberArray https://github.com/reserve85/HoymilesZeroExport/issues/96
* add feature to ignore specific panel voltages in battery mode with opendtu

## V1.53
### script
* Check if AHOY Version is at least V0.7.29. 
* ATTENTION: You need to install the Package "Packaging" -> to do so type "sudo pip3 install packaging" in your terminal (Linux) or "pip3 install packaging" in your cmd (Windows)
* Update install.sh script to install additional package "packaging"
* Update Readme.md to install additional package "packaging"

## V1.52
### script
* OpenDTU: Wait for Acknowledge after SetLimit
* OpenDTU: Removed limit-retries when SetLimit was acknowledged

## V1.51
### script
* Ahoy: removed limit-retries when SetLimit was acknowledged

## V1.50
### script
* use SET_LIMIT_TIMEOUT_SECONDS to wait for acknowledge
### Config
* add: `COMMON`: `SET_LIMIT_TIMEOUT_SECONDS`

## V1.49
### script
* AHOY: Wait for Acknowledge after SetLimit, see https://github.com/lumapu/ahoy/issues/1072
* Warning: if you use AHOY-DTU then you must update your DTU to Version >= 0.7.29 -> https://github.com/lumapu/ahoy/actions

## V1.48
### script
* add a feature to ignore specific panel voltages in battery mode
### Config
* add: `INVERTER_x`: `HOY_BATTERY_IGNORE_PANELS`

## V1.47
### script
* Add VZLogger local http api support (https://wiki.volkszaehler.org/software/controller/vzlogger/vzlogger_conf_parameter#local)
### Config
* add: `[SELECT_POWERMETER]`: `USE_VZLOGGER`
* add: `[SELECT_INTERMEDIATE_METER]`: `USE_VZLOGGER_INTERMEDIATE`
* add: `[VZLOGGER]`: `VZL_IP`
* add: `[VZLOGGER]`: `VZL_PORT`
* add: `[VZLOGGER]`: `VZL_UUID`
* add: `[INTERMEDIATE_VZLOGGER]`: `VZL_IP_INTERMEDIATE`
* add: `[INTERMEDIATE_VZLOGGER]`: `VZL_PORT_INTERMEDIATE`
* add: `[INTERMEDIATE_VZLOGGER]`: `VZL_UUID_INTERMEDIATE`

## V1.46
### script
* Bugfix: jump to defined limit never increased if < 100%
### Config
* just added some comments, nothing productive ( thnx @Ollipop030 )

## V1.45
### script
* BatteryMode: save latest five PanelMinVoltages and return the highest value of them. This ignores temporarly DTU-Errors (e.g. reset values at midnight) for maximum of five iterations.

## V1.44
### script
* replaced the feature "jump to max limit" to "jump to defined limit"
### Config
* changed `[COMMON]/JUMP_TO_MAX_LIMIT_ON_GRID_USAGE` to `[COMMON]/ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT`

## V1.43
### script
* Bugfix: timeout OpenDTU

## V1.42
### script
* AHOY API Update: changed to new functions, see https://github.com/lumapu/ahoy/issues/993

## V1.41
### script
* add timeout = 10 seconds for HTTP Requests

## V1.40
### script
* bugfix: lowest panel voltage "inf" (battery mode)
* chanegd some error messages
### Config
* changed comment of JUMP_TO_MAX_LIMIT_ON_GRID_USAGE to make this point clearer

## V1.39
### script
* add check if POWERMETER_MAX_POINT > (POWERMETER_TOLERANCE + POWERMETER_TARGET_POINT)
### Config
* changed comment of POWERMETER_MAX_POINT to make this point clearer

## V1.38
### script
* Log Python Version on startup and check if it is >= V3.6

## V1.37
### script
* Add ShellyEM support
### Config
* rename section `[SHELLY_3EM]` to `[SHELLY]`
* add: `[SELECT_POWERMETER]`: `USE_SHELLY_EM`
* add: `[SELECT_INTERMEDIATE_METER]`: `USE_SHELLY_EM_INTERMEDIATE`

## V1.36
### script
* Authentication fix for Shelly 2nd Gen. Thanks to user delacor

## V1.35
### script
* another try for authentication of Shelly 2. generation
### Config
* changed some comments

## V1.34
### script
* support user & password for Shelly meters
### Config
* add: `[INTERMEDIATE_SHELLY]`: `SHELLY_USER_INTERMEDIATE` + `SHELLY_PASS_INTERMEDIATE`
* add: `[SHELLY_3EM]`: `SHELLY_USER` + `SHELLY_PASS`

## V1.33
### Script
* new function: CastToInt
### Config
* added some more comments

## V1.32
### Script
* bugfix: cast to int

## V1.31
### Script
* support of power-output-factor to compensate some Inverters (e.g. 700W Limit = 800W Output)
### Config
* add: `[INVERTER_x]`: `HOY_COMPENSATE_WATT_FACTOR` - enter your Factor here. Eg: if you set a limit of 750W = 850W Output -> enter Factor 0.88

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
