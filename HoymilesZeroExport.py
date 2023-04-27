# HoymilesZeroExport - https://github.com/reserve85/HoymilesZeroExport
# Copyright (C) 2023, Tobias Kraft

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = "Tobias Kraft"
__version__ = "1.28"

import requests
import time
from requests.auth import HTTPBasicAuth
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from configparser import ConfigParser
from pathlib import Path
from datetime import timedelta
import datetime

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()

try:
    config = ConfigParser()
    config.read(str(Path.joinpath(Path(__file__).parent.resolve(), "HoymilesZeroExport_Config.ini")))
    ENABLE_LOG_TO_FILE = config.getboolean('COMMON', 'ENABLE_LOG_TO_FILE')
    LOG_BACKUP_COUNT = config.getint('COMMON', 'LOG_BACKUP_COUNT')
except Exception as e:
    logger.info('Error on reading ENABLE_LOG_TO_FILE, set it to DISABLED')
    ENABLE_LOG_TO_FILE = False
    if hasattr(e, 'message'):
        logger.error(e.message)
    else:
        logger.error(e)

if ENABLE_LOG_TO_FILE:
    if not os.path.exists(Path.joinpath(Path(__file__).parent.resolve(), 'log')):
        os.makedirs(Path.joinpath(Path(__file__).parent.resolve(), 'log'))

    rotating_file_handler = TimedRotatingFileHandler(
        filename=Path.joinpath(Path.joinpath(Path(__file__).parent.resolve(), 'log'),'log'),
        when='midnight',
        interval=2,
        backupCount=LOG_BACKUP_COUNT)

    formatter = logging.Formatter(
        '%(asctime)s %(levelname)-8s %(message)s')
    rotating_file_handler.setFormatter(formatter)
    logger.addHandler(rotating_file_handler)

logger.info('Log write to file: %s', ENABLE_LOG_TO_FILE)

def SetLimitOpenDTU(pInverterId, pLimit):
    relLimit = int(pLimit / HOY_INVERTER_WATT[pInverterId] * 100)
    url=f"http://{OPENDTU_IP}/api/limit/config"
    data = f'''data={{"serial":"{SERIAL_NUMBER[pInverterId]}", "limit_type":1, "limit_value":{relLimit}}}'''
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    logger.info('OpenDTU: Inverter "%s": setting new limit from %s Watt to %s Watt',NAME[pInverterId],int(CURRENT_LIMIT[pInverterId]),int(pLimit))
    requests.post(url, data=data, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), headers=headers)
    CURRENT_LIMIT[pInverterId] = pLimit

def SetLimitAhoy(pInverterId, pLimit):
    url = f"http://{AHOY_IP}/api/ctrl"
    data = f'''{{"id": {pInverterId}, "cmd": "limit_nonpersistent_absolute", "val": {pLimit}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    logger.info('Ahoy: Inverter "%s": setting new limit from %s Watt to %s Watt',NAME[pInverterId],int(CURRENT_LIMIT[pInverterId]),int(pLimit))
    requests.post(url, data=data, headers=headers)
    CURRENT_LIMIT[pInverterId] = pLimit

def SetLimit(pLimit):
    try:
        if SET_LIMIT_RETRY != -1:
            if not hasattr(SetLimit, "LastLimit"):
                SetLimit.LastLimit = int(0)
            if not hasattr(SetLimit, "SameLimitCnt"):
                SetLimit.SameLimitCnt = int(0)
            if SetLimit.LastLimit == pLimit:
                SetLimit.SameLimitCnt = SetLimit.SameLimitCnt + 1
            else:
                SetLimit.LastLimit = pLimit
                SetLimit.SameLimitCnt = 0
            if SetLimit.SameLimitCnt >= SET_LIMIT_RETRY:
                logger.info("Set Limit Retry Counter exceeded: Inverterlimit already at %s Watt",int(pLimit))
                time.sleep(SET_LIMIT_DELAY_IN_SECONDS)
                return
        logger.info("setting new limit to %s Watt",int(pLimit))
        for i in range(INVERTER_COUNT):
            if (not AVAILABLE[i]) or (not HOY_POWER_STATUS[i]):
                continue
            if i != 0:
                time.sleep(SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER)
            Factor = HOY_MAX_WATT[i] / GetMaxWattFromAllInverters()
            NewLimit = int(pLimit*Factor)
            NewLimit = ApplyLimitsToSetpointInverter(i, NewLimit)
            if USE_AHOY:
                SetLimitAhoy(i, NewLimit)
            elif USE_OPENDTU:
                SetLimitOpenDTU(i, NewLimit)
            else:
                raise Exception("Error: DTU Type not defined")
        time.sleep(SET_LIMIT_DELAY_IN_SECONDS)
    except Exception as e:
        logger.error("Exception at SetLimit")
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        raise

def GetHoymilesAvailableOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS)).json()
    Reachable = bool(ParsedData["inverters"][pInverterId]["reachable"])
    logger.info('OpenDTU: Inverter "%s" reachable: %s',NAME[pInverterId],Reachable)
    return Reachable

def GetHoymilesAvailableAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/index'
    ParsedData = requests.get(url).json()
    Reachable = bool(ParsedData["inverter"][pInverterId]["is_avail"])
    logger.info('Ahoy: Inverter "%s" reachable: %s',NAME[pInverterId],Reachable)
    return Reachable

def GetHoymilesAvailable():
    try:
        GetHoymilesAvailable = False
        for i in range(INVERTER_COUNT):
            try:
                WasAvail = AVAILABLE[i]
                if USE_AHOY:
                    AVAILABLE[i] = GetHoymilesAvailableAhoy(i)
                elif USE_OPENDTU:
                    AVAILABLE[i] = GetHoymilesAvailableOpenDTU(i)
                else:
                    raise Exception("Error: DTU Type not defined")
                if AVAILABLE[i]:
                    GetHoymilesAvailable = True
                    if not WasAvail:
                        GetHoymilesInfo()
            except:
                AVAILABLE[i] = False
                logger.error("Exception at GetHoymilesAvailable, Inverter %s (%s) not reachable", i, NAME[i])
        return GetHoymilesAvailable
    except Exception as e:
        logger.error('Exception at GetHoymilesAvailable')
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        raise

def GetHoymilesInfoOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS)).json()
    SERIAL_NUMBER[pInverterId] = str(ParsedData['inverters'][pInverterId]['serial'])
    TEMPERATURE[pInverterId] = str(round(float((ParsedData['inverters'][pInverterId]['INV']['0']['Temperature']['v'])),1)) + ' degC'
    NAME[pInverterId] = str(ParsedData['inverters'][pInverterId]['name'])
    logger.info('OpenDTU: Inverter "%s" / serial number "%s" / temperature %s',NAME[pInverterId],SERIAL_NUMBER[pInverterId],TEMPERATURE[pInverterId])

def GetHoymilesInfoAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/record/live'
    ParsedData = requests.get(url).json()
    TEMPERATURE[pInverterId] = str(round(float(next(item for item in ParsedData['inverter'][pInverterId] if item['fld'] == 'Temp')['val']),1)) + ' degC'

    url = f'http://{AHOY_IP}/api/inverter/list'
    ParsedData = requests.get(url).json()
    SERIAL_NUMBER[pInverterId] = str(ParsedData['inverter'][pInverterId]['serial'])
    NAME[pInverterId] = str(ParsedData['inverter'][pInverterId]['name'])
    logger.info('Ahoy: Inverter "%s" / serial number "%s" / temperature %s',NAME[pInverterId],SERIAL_NUMBER[pInverterId],TEMPERATURE[pInverterId])

def GetHoymilesInfo():
    try:
        for i in range(INVERTER_COUNT):
            try:
                if not AVAILABLE[i]:
                    continue
                if USE_AHOY:
                    GetHoymilesInfoAhoy(i)
                elif USE_OPENDTU:
                    GetHoymilesInfoOpenDTU(i)
                else:
                    raise Exception("Error: DTU Type not defined")
            except:
                logger.error("Exception at GetHoymilesInfo, Inverter %s not reachable", i)
    except Exception as e:
        logger.error("Exception at GetHoymilesInfo")
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        raise

def GetHoymilesPanelMinVoltageAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/record/live'
    ParsedData = requests.get(url).json()
    PanelVDC = []
    for item in ParsedData['inverter'][pInverterId]:
        if item['fld'] == 'U_DC':
            PanelVDC.append(float(item['val']))
    minVdc = float('inf')
    for i in range(len(PanelVDC)):
        if (minVdc > PanelVDC[i]) and (PanelVDC[i] > 5):
            minVdc = PanelVDC[i]
    logger.info("Lowest panel voltage: %s Volt",minVdc)
    return minVdc

def GetHoymilesPanelMinVoltageOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS)).json()
    PanelVDC = []
    for i in range(len(ParsedData['inverters'][pInverterId]['DC'])):
        PanelVDC.append(float(ParsedData['inverters'][pInverterId]['DC'][str(i)]['Voltage']['v']))
    minVdc = float('inf')
    for i in range(len(PanelVDC)):
        if (minVdc > PanelVDC[i]) and (PanelVDC[i] > 5):
            minVdc = PanelVDC[i]
    logger.info("Lowest panelvoltage: %s Volt",minVdc)
    return minVdc

def GetHoymilesPanelMinVoltage(pInverterId):
    try:
        try:
            if not AVAILABLE[pInverterId]:
                return 0
            if USE_AHOY:
                return GetHoymilesPanelMinVoltageAhoy(pInverterId)
            elif USE_OPENDTU:
                return GetHoymilesPanelMinVoltageOpenDTU(pInverterId)
            else:
                raise Exception("Error: DTU Type not defined")
        except:
            logger.error("Exception at GetHoymilesPanelMinVoltage, Inverter %s not reachable", pInverterId)
    except Exception as e:
        logger.error("Exception at GetHoymilesPanelMinVoltage")
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        raise

def SetHoymilesPowerStatusAhoy(pInverterId, pActive):
    url = f"http://{AHOY_IP}/api/ctrl"
    data = f'''{{"id": {pInverterId}, "cmd": "power", "val": {int(pActive == True)}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    if pActive:
        logger.info('Ahoy: Inverter "%s": Turn on',NAME[pInverterId])
    else:
        logger.info('Ahoy: Inverter "%s": Turn off',NAME[pInverterId])
    requests.post(url, data=data, headers=headers)
    HOY_POWER_STATUS[pInverterId] = pActive

def SetHoymilesPowerStatusOpenDTU(pInverterId, pActive):
    url=f"http://{OPENDTU_IP}/api/power/config"
    data = f'''data={{"serial":"{SERIAL_NUMBER[pInverterId]}", "power":{int(pActive == True)}}}'''
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    if pActive:
        logger.info('OpenDTU: Inverter "%s": Turn on',NAME[pInverterId])
    else:
        logger.info('OpenDTU: Inverter "%s": Turn off',NAME[pInverterId])
    a = requests.post(url, data=data, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), headers=headers)
    HOY_POWER_STATUS[pInverterId] = pActive

def SetHoymilesPowerStatus(pInverterId, pActive):
    try:
        if not AVAILABLE[pInverterId]:
            return
        if SET_LIMIT_RETRY != -1:
            if not hasattr(SetLimit, "LastPowerStatus"):
                SetLimit.LastPowerStatus = []
                SetLimit.LastPowerStatus = [False for i in range(INVERTER_COUNT)]
            if not hasattr(SetLimit, "SamePowerStatusCnt"):
                SetLimit.SamePowerStatusCnt = []
                SetLimit.SamePowerStatusCnt = [0 for i in range(INVERTER_COUNT)]
            if SetLimit.LastPowerStatus[pInverterId] == pActive:
                SetLimit.SamePowerStatusCnt[pInverterId] = SetLimit.SamePowerStatusCnt[pInverterId] + 1
            else:
                SetLimit.LastPowerStatus[pInverterId] = pActive
                SetLimit.SamePowerStatusCnt[pInverterId] = 0
            if SetLimit.SamePowerStatusCnt[pInverterId] >= SET_LIMIT_RETRY:
                logger.info("Set Limit Retry Counter exceeded: Inverter PowerStatus already %s",int(pActive))
                time.sleep(SET_LIMIT_DELAY_IN_SECONDS)
                return
        if USE_AHOY:
            SetHoymilesPowerStatusAhoy(pInverterId, pActive)
        elif USE_OPENDTU:
            SetHoymilesPowerStatusOpenDTU(pInverterId, pActive)
        else:
            raise Exception("Error: DTU Type not defined")
        time.sleep(SET_LIMIT_DELAY_IN_SECONDS)
    except Exception as e:
        logger.error("Exception at SetHoymilesPowerStatus")
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        raise

def GetCheckBattery():
    try:
        result = False
        for i in range(INVERTER_COUNT):
            try:
                if not AVAILABLE[i]:
                    continue
                if not HOY_BATTERY_MODE[i]:
                    result = True
                    continue
                minVoltage = GetHoymilesPanelMinVoltage(i)
                if minVoltage <= HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V[i]:
                    SetHoymilesPowerStatus(i, False)
                    HOY_MAX_WATT[i] = HOY_BATTERY_REDUCE_WATT[i]
                elif minVoltage <= HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V[i]:
                    HOY_MAX_WATT[i] = HOY_BATTERY_REDUCE_WATT[i]
                elif minVoltage >= HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V[i]:
                    SetHoymilesPowerStatus(i, True)
                    HOY_MAX_WATT[i] = HOY_BATTERY_NORMAL_WATT[i]
                elif minVoltage >= HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V[i]:
                    HOY_MAX_WATT[i] = HOY_BATTERY_NORMAL_WATT[i]
                if HOY_POWER_STATUS[i]:
                    result = True
            except:
                logger.error("Exception at CheckBattery, Inverter %s not reachable", i)
        return result
    except Exception as e:
        logger.error("Exception at CheckBattery")
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        raise

def GetHoymilesTemperatureOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS)).json()
    TEMPERATURE[pInverterId] = str(round(float((ParsedData['inverters'][pInverterId]['INV']['0']['Temperature']['v'])),1)) + ' degC'
    logger.info('OpenDTU: Inverter "%s" temperature: %s',NAME[pInverterId],TEMPERATURE[pInverterId])

def GetHoymilesTemperatureAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/record/live'
    ParsedData = requests.get(url).json()
    TEMPERATURE[pInverterId] = str(round(float(next(item for item in ParsedData['inverter'][pInverterId] if item['fld'] == 'Temp')['val']),1)) + ' degC'
    logger.info('Ahoy: Inverter "%s" temperature: %s',NAME[pInverterId],TEMPERATURE[pInverterId])

def GetHoymilesTemperature():
    try:
        for i in range(INVERTER_COUNT):
            try:
                if not AVAILABLE[i]:
                    continue
                if USE_AHOY:
                    GetHoymilesTemperatureAhoy(i)
                elif USE_OPENDTU:
                    GetHoymilesTemperatureOpenDTU(i)
                else:
                    raise Exception("Error: DTU Type not defined")
            except:
                logger.error("Exception at GetHoymilesTemperature, Inverter %s not reachable", i)
    except Exception as e:
        logger.error("Exception at GetHoymilesTemperature")
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        raise

def GetHoymilesActualPowerOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS)).json()
    ActualPower = int(ParsedData['inverters'][pInverterId]['AC']['0']['Power']['v'])
    logger.info('OpenDTU: Inverter "%s" power producing: %s %s',NAME[pInverterId],ActualPower," Watt")
    return int(ActualPower)

def GetHoymilesActualPowerAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/record/live'
    ParsedData = requests.get(url).json()
    ActualPower = int(float(next(item for item in ParsedData['inverter'][pInverterId] if item['fld'] == 'P_AC')['val']))
    logger.info('Ahoy: Inverter "%s" power producing: %s %s',NAME[pInverterId],ActualPower," Watt")
    return int(ActualPower)

def GetHoymilesActualPower():
    try:
        ActualPower = 0
        if USE_SHELLY_3EM_INTERMEDIATE:
            return GetPowermeterWattsShelly3EM_Intermediate()
        elif USE_SHELLY_3EM_PRO_INTERMEDIATE:
            return GetPowermeterWattsShelly3EMPro_Intermediate()
        elif USE_SHELLY_1PM_INTERMEDIATE:
            return GetPowermeterWattsShelly1PM_Intermediate()
        elif USE_SHELLY_PLUS_1PM_INTERMEDIATE:
            return GetPowermeterWattsShellyPlus1PM_Intermediate()
        elif USE_TASMOTA_INTERMEDIATE:
            return GetPowermeterWattsTasmota_Intermediate()
        elif USE_SHRDZM_INTERMEDIATE:
            return GetPowermeterWattsShrdzm_Intermediate()
        elif USE_EMLOG_INTERMEDIATE:
            return GetPowermeterWattsEmlog_Intermediate()
        elif USE_IOBROKER_INTERMEDIATE:
            return GetPowermeterWattsIobroker_Intermediate()
        elif USE_AHOY:
            for i in range(INVERTER_COUNT):
                if (not AVAILABLE[i]) or (not HOY_POWER_STATUS[i]):
                    continue
                ActualPower = ActualPower + GetHoymilesActualPowerAhoy(i)
            return ActualPower
        elif USE_OPENDTU:
            for i in range(INVERTER_COUNT):
                if (not AVAILABLE[i]) or (not HOY_POWER_STATUS[i]):
                    continue
                ActualPower = ActualPower + GetHoymilesActualPowerOpenDTU(i)
            return ActualPower
        else:
            raise Exception("Error: DTU Type not defined")
    except Exception as e:
        logger.error("Exception at GetHoymilesActualPower")
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        raise

def GetPowermeterWattsTasmota_Intermediate():
    url = f'http://{TASMOTA_IP_INTERMEDIATE}/cm?cmnd=status%2010'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData[TASMOTA_JSON_STATUS_INTERMEDIATE][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX_INTERMEDIATE][TASMOTA_JSON_POWER_MQTT_LABEL_INTERMEDIATE])
    logger.info("intermediate meter Tasmota: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShelly1PM_Intermediate():
    url = f'http://{SHELLY_IP_INTERMEDIATE}/status'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData['meters'][0]['power'])
    logger.info("intermediate meter Shelly 1PM: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShellyPlus1PM_Intermediate():
    url = f'http://{SHELLY_IP_INTERMEDIATE}/rpc/Switch.GetStatus?id=0'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData['apower'])
    logger.info("intermediate meter Shelly Plus 1PM: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShelly3EM_Intermediate():
    url = f'http://{SHELLY_IP_INTERMEDIATE}/status'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData['total_power'])
    logger.info("intermediate meter Shelly 3EM: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShelly3EMPro_Intermediate():
    url = f'http://{SHELLY_IP_INTERMEDIATE}/rpc/EM.GetStatus?id=0'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData['total_act_power'])
    logger.info("intermediate meter Shelly 3EM Pro: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShrdzm_Intermediate():
    url = f'http://{SHRDZM_IP_INTERMEDIATE}/getLastData?user={SHRDZM_USER_INTERMEDIATE}&password={SHRDZM_PASS_INTERMEDIATE}'
    ParsedData = requests.get(url).json()
    Watts = int(int(ParsedData['1.7.0']) - int(ParsedData['2.7.0']))
    logger.info("intermediate meter SHRDZM: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsEmlog_Intermediate():
    url = f'http://{EMLOG_IP_INTERMEDIATE}/pages/getinformation.php?heute&meterindex={EMLOG_METERINDEX_INTERMEDIATE}'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData['Leistung170'])
    logger.info("intermediate meter EMLOG: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsIobroker_Intermediate():
    url = f'http://{IOBROKER_IP_INTERMEDIATE}:{IOBROKER_PORT_INTERMEDIATE}/getBulk/{IOBROKER_CURRENT_POWER_ALIAS_INTERMEDIATE}'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData[0]['val'])
    logger.info("intermediate meter IOBROKER: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsTasmota():
    url = f'http://{TASMOTA_IP}/cm?cmnd=status%2010'
    ParsedData = requests.get(url).json()
    if not TASMOTA_JSON_POWER_CALCULATE:
        Watts = int(ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_MQTT_LABEL])
    else:
        input = ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_INPUT_MQTT_LABEL]
        ouput = ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_OUTPUT_MQTT_LABEL]
        Watts = int(input - ouput)
    logger.info("powermeter Tasmota: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShelly3EM():
    url = f'http://{SHELLY_IP}/status'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData['total_power'])
    logger.info("powermeter Shelly 3EM: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShelly3EMPro():
    url = f'http://{SHELLY_IP}/rpc/EM.GetStatus?id=0'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData['total_act_power'])
    logger.info("powermeter Shelly 3EM Pro: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShrdzm():
    url = f'http://{SHRDZM_IP}/getLastData?user={SHRDZM_USER}&password={SHRDZM_PASS}'
    ParsedData = requests.get(url).json()
    Watts = int(int(ParsedData['1.7.0']) - int(ParsedData['2.7.0']))
    logger.info("powermeter SHRDZM: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsEmlog():
    url = f'http://{EMLOG_IP}/pages/getinformation.php?heute&meterindex={EMLOG_METERINDEX}'
    ParsedData = requests.get(url).json()
    Watts = int(int(ParsedData['Leistung170']) - int(ParsedData['Leistung270']))
    logger.info("powermeter EMLOG: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsIobroker():
    if not IOBROKER_POWER_CALCULATE:
        url = f'http://{IOBROKER_IP}:{IOBROKER_PORT}/getBulk/{IOBROKER_CURRENT_POWER_ALIAS}'
        ParsedData = requests.get(url).json()
        for item in ParsedData:
            if item['id'] == IOBROKER_CURRENT_POWER_ALIAS:
                Watts = int(item['val'])
                break
    else:
        url = f'http://{IOBROKER_IP}:{IOBROKER_PORT}/getBulk/{IOBROKER_POWER_INPUT_ALIAS},{IOBROKER_POWER_OUTPUT_ALIAS}'
        ParsedData = requests.get(url).json()
        for item in ParsedData:
            if item['id'] == IOBROKER_POWER_INPUT_ALIAS:
                input = int(item['val'])
            if item['id'] == IOBROKER_POWER_OUTPUT_ALIAS:
                output = int(item['val'])
        Watts = int(input - output)
    logger.info("powermeter IOBROKER: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWatts():
    try:
        if USE_SHELLY_3EM:
            return GetPowermeterWattsShelly3EM()
        elif USE_SHELLY_3EM_PRO:
            return GetPowermeterWattsShelly3EMPro()
        elif USE_TASMOTA:
            return GetPowermeterWattsTasmota()
        elif USE_SHRDZM:
            return GetPowermeterWattsShrdzm()
        elif USE_EMLOG:
            return GetPowermeterWattsEmlog()
        elif USE_IOBROKER:
            return GetPowermeterWattsIobroker()
        else:
            raise Exception("Error: no powermeter defined!")
    except Exception as e:
        logger.error("Exception at GetPowermeterWatts")
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        raise

def CutLimitToProduction(pSetpoint):
    if pSetpoint != GetMaxWattFromAllInverters():
        ActualPower = GetHoymilesActualPower()
        # prevent the setpoint from running away...
        if pSetpoint > ActualPower + (GetMaxWattFromAllInverters() * MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER / 100):
            pSetpoint = int(ActualPower + (GetMaxWattFromAllInverters() * MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER / 100))
            logger.info('Cut limit to %s Watt, limit was higher than %s percent of live-production', int(pSetpoint), MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER)
    return int(pSetpoint)

def ApplyLimitsToSetpoint(pSetpoint):
    if pSetpoint > GetMaxWattFromAllInverters():
        pSetpoint = GetMaxWattFromAllInverters()
    if pSetpoint < GetMinWattFromAllInverters():
        pSetpoint = GetMinWattFromAllInverters()
    return pSetpoint

def ApplyLimitsToSetpointInverter(pInverter, pSetpoint):
    if pSetpoint > HOY_MAX_WATT[pInverter]:
        pSetpoint = HOY_MAX_WATT[pInverter]
    if pSetpoint < HOY_MIN_WATT[pInverter]:
        pSetpoint = HOY_MIN_WATT[pInverter]
    return pSetpoint

def GetMaxWattFromAllInverters():
    maxWatt = 0
    for i in range(INVERTER_COUNT):
        if (not AVAILABLE[i]) or (not HOY_POWER_STATUS[i]):
            continue
        maxWatt = maxWatt + HOY_MAX_WATT[i]
    return maxWatt

def GetMinWattFromAllInverters():
    minWatt = 0
    for i in range(INVERTER_COUNT):
        if (not AVAILABLE[i]) or (not HOY_POWER_STATUS[i]):
            continue
        minWatt = minWatt + HOY_MIN_WATT[i]
    return minWatt

# ----- START -----

logger.info("Author: %s / Script Version: %s",__author__, __version__)

# read config:
logger.info("read config file: " + str(Path.joinpath(Path(__file__).parent.resolve(), "HoymilesZeroExport_Config.ini")))
VERSION = config.get('VERSION', 'VERSION')
logger.info("Config file V %s", VERSION)
USE_AHOY = config.getboolean('SELECT_DTU', 'USE_AHOY')
USE_OPENDTU = config.getboolean('SELECT_DTU', 'USE_OPENDTU')
USE_TASMOTA = config.getboolean('SELECT_POWERMETER', 'USE_TASMOTA')
USE_SHELLY_3EM = config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_3EM')
USE_SHELLY_3EM_PRO = config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_3EM_PRO')
USE_SHRDZM = config.getboolean('SELECT_POWERMETER', 'USE_SHRDZM')
USE_EMLOG = config.getboolean('SELECT_POWERMETER', 'USE_EMLOG')
USE_IOBROKER = config.getboolean('SELECT_POWERMETER', 'USE_IOBROKER')
AHOY_IP = config.get('AHOY_DTU', 'AHOY_IP')
OPENDTU_IP = config.get('OPEN_DTU', 'OPENDTU_IP')
OPENDTU_USER = config.get('OPEN_DTU', 'OPENDTU_USER')
OPENDTU_PASS = config.get('OPEN_DTU', 'OPENDTU_PASS')
TASMOTA_IP = config.get('TASMOTA', 'TASMOTA_IP')
TASMOTA_JSON_STATUS = config.get('TASMOTA', 'TASMOTA_JSON_STATUS')
TASMOTA_JSON_PAYLOAD_MQTT_PREFIX = config.get('TASMOTA', 'TASMOTA_JSON_PAYLOAD_MQTT_PREFIX')
TASMOTA_JSON_POWER_MQTT_LABEL = config.get('TASMOTA', 'TASMOTA_JSON_POWER_MQTT_LABEL')
TASMOTA_JSON_POWER_CALCULATE = config.getboolean('TASMOTA', 'TASMOTA_JSON_POWER_CALCULATE')
TASMOTA_JSON_POWER_INPUT_MQTT_LABEL = config.get('TASMOTA', 'TASMOTA_JSON_POWER_INPUT_MQTT_LABEL')
TASMOTA_JSON_POWER_OUTPUT_MQTT_LABEL = config.get('TASMOTA', 'TASMOTA_JSON_POWER_OUTPUT_MQTT_LABEL')
SHELLY_IP = config.get('SHELLY_3EM', 'SHELLY_IP')
SHRDZM_IP = config.get('SHRDZM', 'SHRDZM_IP')
SHRDZM_USER = config.get('SHRDZM', 'SHRDZM_USER')
SHRDZM_PASS = config.get('SHRDZM', 'SHRDZM_PASS')
EMLOG_IP = config.get('EMLOG', 'EMLOG_IP')
EMLOG_METERINDEX = config.get('EMLOG', 'EMLOG_METERINDEX')
IOBROKER_IP = config.get('IOBROKER', 'IOBROKER_IP')
IOBROKER_PORT = config.get('IOBROKER', 'IOBROKER_PORT')
IOBROKER_CURRENT_POWER_ALIAS = config.get('IOBROKER', 'IOBROKER_CURRENT_POWER_ALIAS')
IOBROKER_POWER_CALCULATE = config.getboolean('IOBROKER', 'IOBROKER_POWER_CALCULATE')
IOBROKER_POWER_INPUT_ALIAS = config.get('IOBROKER', 'IOBROKER_POWER_INPUT_ALIAS')
IOBROKER_POWER_OUTPUT_ALIAS = config.get('IOBROKER', 'IOBROKER_POWER_OUTPUT_ALIAS')
USE_TASMOTA_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_TASMOTA_INTERMEDIATE')
USE_SHELLY_3EM_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHELLY_3EM_INTERMEDIATE')
USE_SHELLY_3EM_PRO_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHELLY_3EM_PRO_INTERMEDIATE')
USE_SHELLY_1PM_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHELLY_1PM_INTERMEDIATE')
USE_SHELLY_PLUS_1PM_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHELLY_PLUS_1PM_INTERMEDIATE')
USE_SHRDZM_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHRDZM_INTERMEDIATE')
USE_EMLOG_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_EMLOG_INTERMEDIATE')
USE_IOBROKER_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_IOBROKER_INTERMEDIATE')
TASMOTA_IP_INTERMEDIATE = config.get('INTERMEDIATE_TASMOTA', 'TASMOTA_IP_INTERMEDIATE')
TASMOTA_JSON_STATUS_INTERMEDIATE = config.get('INTERMEDIATE_TASMOTA', 'TASMOTA_JSON_STATUS_INTERMEDIATE')
TASMOTA_JSON_PAYLOAD_MQTT_PREFIX_INTERMEDIATE = config.get('INTERMEDIATE_TASMOTA', 'TASMOTA_JSON_PAYLOAD_MQTT_PREFIX_INTERMEDIATE')
TASMOTA_JSON_POWER_MQTT_LABEL_INTERMEDIATE = config.get('INTERMEDIATE_TASMOTA', 'TASMOTA_JSON_POWER_MQTT_LABEL_INTERMEDIATE')
SHELLY_IP_INTERMEDIATE = config.get('INTERMEDIATE_SHELLY', 'SHELLY_IP_INTERMEDIATE')
SHRDZM_IP_INTERMEDIATE = config.get('INTERMEDIATE_SHRDZM', 'SHRDZM_IP_INTERMEDIATE')
SHRDZM_USER_INTERMEDIATE = config.get('INTERMEDIATE_SHRDZM', 'SHRDZM_USER_INTERMEDIATE')
SHRDZM_PASS_INTERMEDIATE = config.get('INTERMEDIATE_SHRDZM', 'SHRDZM_PASS_INTERMEDIATE')
EMLOG_IP_INTERMEDIATE = config.get('INTERMEDIATE_EMLOG', 'EMLOG_IP_INTERMEDIATE')
EMLOG_METERINDEX_INTERMEDIATE = config.get('INTERMEDIATE_EMLOG', 'EMLOG_METERINDEX_INTERMEDIATE')
IOBROKER_IP_INTERMEDIATE = config.get('INTERMEDIATE_IOBROKER', 'IOBROKER_IP_INTERMEDIATE')
IOBROKER_PORT_INTERMEDIATE = config.get('INTERMEDIATE_IOBROKER', 'IOBROKER_PORT_INTERMEDIATE')
IOBROKER_CURRENT_POWER_ALIAS_INTERMEDIATE = config.get('INTERMEDIATE_IOBROKER', 'IOBROKER_CURRENT_POWER_ALIAS_INTERMEDIATE')
INVERTER_COUNT = config.getint('COMMON', 'INVERTER_COUNT')
LOOP_INTERVAL_IN_SECONDS = config.getint('COMMON', 'LOOP_INTERVAL_IN_SECONDS')
SET_LIMIT_DELAY_IN_SECONDS = config.getint('COMMON', 'SET_LIMIT_DELAY_IN_SECONDS')
SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER = config.getint('COMMON', 'SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER')
POLL_INTERVAL_IN_SECONDS = config.getint('COMMON', 'POLL_INTERVAL_IN_SECONDS')
JUMP_TO_MAX_LIMIT_ON_GRID_USAGE = config.getboolean('COMMON', 'JUMP_TO_MAX_LIMIT_ON_GRID_USAGE')
MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER = config.getint('COMMON', 'MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER')
SET_LIMIT_RETRY = config.getint('COMMON', 'SET_LIMIT_RETRY')
SLOW_APPROX_FACTOR_IN_PERCENT = config.getint('COMMON', 'SLOW_APPROX_FACTOR_IN_PERCENT')
LOG_TEMPERATURE = config.getboolean('COMMON', 'LOG_TEMPERATURE')
POWERMETER_TARGET_POINT = config.getint('CONTROL', 'POWERMETER_TARGET_POINT')
POWERMETER_TOLERANCE = config.getint('CONTROL', 'POWERMETER_TOLERANCE')
POWERMETER_MAX_POINT = config.getint('CONTROL', 'POWERMETER_MAX_POINT')
SERIAL_NUMBER = []
NAME = []
TEMPERATURE = []
HOY_MAX_WATT = []
HOY_INVERTER_WATT = []
HOY_MIN_WATT = []
CURRENT_LIMIT = []
AVAILABLE = []
HOY_BATTERY_MODE = []
HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V = []
HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V = []
HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V = []
HOY_BATTERY_NORMAL_WATT = []
HOY_BATTERY_REDUCE_WATT = []
HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V = []
HOY_POWER_STATUS = []
for i in range(INVERTER_COUNT):
    SERIAL_NUMBER.append(str('yet unknown'))
    NAME.append(str('yet unknown'))
    TEMPERATURE.append(str('--- degC'))
    HOY_MAX_WATT.append(config.getint('INVERTER_' + str(i + 1), 'HOY_MAX_WATT'))
    HOY_INVERTER_WATT.append(HOY_MAX_WATT[i])
    HOY_MIN_WATT.append(int(HOY_MAX_WATT[i] * config.getint('INVERTER_' + str(i + 1), 'HOY_MIN_WATT_IN_PERCENT') / 100))
    CURRENT_LIMIT.append(int(0))
    AVAILABLE.append(bool(False))
    HOY_BATTERY_MODE.append(config.getboolean('INVERTER_' + str(i + 1), 'HOY_BATTERY_MODE'))
    HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V.append(config.getfloat('INVERTER_' + str(i + 1), 'HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V'))
    HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V.append(config.getfloat('INVERTER_' + str(i + 1), 'HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V'))
    HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V.append(config.getfloat('INVERTER_' + str(i + 1), 'HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V'))
    HOY_BATTERY_NORMAL_WATT.append(config.getint('INVERTER_' + str(i + 1), 'HOY_BATTERY_NORMAL_WATT'))
    if HOY_BATTERY_NORMAL_WATT[i] > HOY_MAX_WATT[i]:
        HOY_BATTERY_NORMAL_WATT[i] = HOY_MAX_WATT[i]
    HOY_BATTERY_REDUCE_WATT.append(config.getint('INVERTER_' + str(i + 1), 'HOY_BATTERY_REDUCE_WATT'))
    HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V.append(config.getfloat('INVERTER_' + str(i + 1), 'HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V'))
    HOY_POWER_STATUS.append(bool(True))
SLOW_APPROX_LIMIT = int(GetMaxWattFromAllInverters() * config.getint('COMMON', 'SLOW_APPROX_LIMIT_IN_PERCENT') / 100)

try:
    logger.info("---Init---")
    newLimitSetpoint = 0
    if GetHoymilesAvailable():
        for i in range(INVERTER_COUNT):
            SetHoymilesPowerStatus(i, True)
        newLimitSetpoint = GetMaxWattFromAllInverters()
        GetHoymilesActualPower()
        SetLimit(newLimitSetpoint)
    GetPowermeterWatts()
    time.sleep(SET_LIMIT_DELAY_IN_SECONDS)
except Exception as e:
    if hasattr(e, 'message'):
        logger.error(e.message)
    else:
        logger.error(e)
    time.sleep(LOOP_INTERVAL_IN_SECONDS)
logger.info("---Start Zero Export---")

while True:
    try:
        PreviousLimitSetpoint = newLimitSetpoint
        if GetHoymilesAvailable() and GetCheckBattery():
            if LOG_TEMPERATURE:
                GetHoymilesTemperature()
            for x in range(int(LOOP_INTERVAL_IN_SECONDS / POLL_INTERVAL_IN_SECONDS)):
                powermeterWatts = GetPowermeterWatts()
                if powermeterWatts > POWERMETER_MAX_POINT:
                    if JUMP_TO_MAX_LIMIT_ON_GRID_USAGE:
                        newLimitSetpoint = GetMaxWattFromAllInverters()
                    else:
                        newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts - POWERMETER_TARGET_POINT
                    newLimitSetpoint = ApplyLimitsToSetpoint(newLimitSetpoint)
                    SetLimit(newLimitSetpoint)
                    if int(LOOP_INTERVAL_IN_SECONDS) - SET_LIMIT_DELAY_IN_SECONDS - x * POLL_INTERVAL_IN_SECONDS <= 0:
                        break
                    else:
                        time.sleep(int(LOOP_INTERVAL_IN_SECONDS) - SET_LIMIT_DELAY_IN_SECONDS - x * POLL_INTERVAL_IN_SECONDS)
                    break
                else:
                    time.sleep(POLL_INTERVAL_IN_SECONDS)

            if MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER != 100:
                CutLimit = CutLimitToProduction(newLimitSetpoint)
                if CutLimit != newLimitSetpoint:
                    newLimitSetpoint = CutLimit
                    PreviousLimitSetpoint = newLimitSetpoint

            if powermeterWatts > POWERMETER_MAX_POINT:
                continue

            # producing too much power: reduce limit
            if powermeterWatts < (POWERMETER_TARGET_POINT - POWERMETER_TOLERANCE):
                if PreviousLimitSetpoint >= GetMaxWattFromAllInverters():
                    hoymilesActualPower = GetHoymilesActualPower()
                    newLimitSetpoint = hoymilesActualPower + powermeterWatts - POWERMETER_TARGET_POINT
                    LimitDifference = abs(hoymilesActualPower - newLimitSetpoint)
                    if LimitDifference > SLOW_APPROX_LIMIT:
                        newLimitSetpoint = newLimitSetpoint + (LimitDifference * SLOW_APPROX_FACTOR_IN_PERCENT / 100)
                    if newLimitSetpoint > hoymilesActualPower:
                        newLimitSetpoint = hoymilesActualPower
                    logger.info("overproducing: reduce limit based on actual power")
                else:
                    newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts - POWERMETER_TARGET_POINT
                    # check if it is necessary to approximate to the setpoint with some more passes. this reduce overshoot
                    LimitDifference = abs(PreviousLimitSetpoint - newLimitSetpoint)
                    if LimitDifference > SLOW_APPROX_LIMIT:
                        logger.info("overproducing: reduce limit based on previous limit setpoint by approximation")
                        newLimitSetpoint = newLimitSetpoint + (LimitDifference * SLOW_APPROX_FACTOR_IN_PERCENT / 100)
                    else:
                        logger.info("overproducing: reduce limit based on previous limit setpoint")

            # producing too little power: increase limit
            elif powermeterWatts > (POWERMETER_TARGET_POINT + POWERMETER_TOLERANCE):
                if PreviousLimitSetpoint < GetMaxWattFromAllInverters():
                    newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts - POWERMETER_TARGET_POINT
                    logger.info("Not enough energy producing: increasing limit")
                else:
                    logger.info("Not enough energy producing: limit already at maximum")

            # check for upper and lower limits
            newLimitSetpoint = ApplyLimitsToSetpoint(newLimitSetpoint)
            # set new limit to inverter
            if newLimitSetpoint != PreviousLimitSetpoint:
                SetLimit(newLimitSetpoint)
        else:
            if hasattr(SetLimit, "LastLimit"):
                SetLimit.LastLimit = -1
            time.sleep(LOOP_INTERVAL_IN_SECONDS)

    except Exception as e:
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        time.sleep(LOOP_INTERVAL_IN_SECONDS)
