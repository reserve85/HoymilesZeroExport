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
__version__ = "1.63"

import requests
import time
from requests.auth import HTTPBasicAuth
from requests.auth import HTTPDigestAuth
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from configparser import ConfigParser
from pathlib import Path
from datetime import timedelta
import datetime
import sys
from packaging import version
import argparse 

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', help='Override configuration file path')
args = parser.parse_args()

try:
    config = ConfigParser()
    
    baseconfig = str(Path.joinpath(Path(__file__).parent.resolve(), "HoymilesZeroExport_Config.ini"))
    if args.config:
        config.read([baseconfig, args.config])
    else:
        config.read(baseconfig)

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
logger.info('Python Version: ' + sys.version)
try:
    assert sys.version_info >= (3,6)
except:
    logger.info('Error: your Python version is too old, this script requires version 3.6 or newer. Please update your Python.')
    sys.exit()

def CastToInt(pValueToCast):
    try:
        result = int(pValueToCast)
        return result
    except:
        result = 0
    try:
        result = int(float(pValueToCast))
        return result
    except:
        logger.error("Exception at CastToInt")
        raise

def SetLimitOpenDTU(pInverterId, pLimit):
    relLimit = CastToInt(pLimit / HOY_INVERTER_WATT[pInverterId] * 100)
    url=f"http://{OPENDTU_IP}/api/limit/config"
    data = f'''data={{"serial":"{SERIAL_NUMBER[pInverterId]}", "limit_type":1, "limit_value":{relLimit}}}'''
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    logger.info('OpenDTU: Inverter "%s": setting new limit from %s Watt to %s Watt',NAME[pInverterId],CastToInt(CURRENT_LIMIT[pInverterId]),CastToInt(pLimit))
    requests.post(url, data=data, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), headers=headers)
    CURRENT_LIMIT[pInverterId] = pLimit

def SetLimitAhoy(pInverterId, pLimit):
    url = f"http://{AHOY_IP}/api/ctrl"
    data = f'''{{"id": {pInverterId}, "cmd": "limit_nonpersistent_absolute", "val": {pLimit*AHOY_FACTOR}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    logger.info('Ahoy: Inverter "%s": setting new limit from %s Watt to %s Watt',NAME[pInverterId],CastToInt(CURRENT_LIMIT[pInverterId]),CastToInt(pLimit))
    requests.post(url, data=data, headers=headers)
    CURRENT_LIMIT[pInverterId] = pLimit

def WaitForAckAhoy(pInverterId, pTimeoutInS):
    url = f'http://{AHOY_IP}/api/inverter/id/{pInverterId}'
    timeout = pTimeoutInS
    timeout_start = time.time()
    while time.time() < timeout_start + timeout:
        time.sleep(0.5)
        ParsedData = requests.get(url, timeout=pTimeoutInS).json()
        ack = bool(ParsedData['power_limit_ack'])
        if ack:
            break
    if ack:
        logger.info('Ahoy: Inverter "%s": Limit acknowledged', NAME[pInverterId])
    else:
        logger.info('Ahoy: Inverter "%s": Limit timeout!', NAME[pInverterId])
    return ack

def WaitForAckOpenDTU(pInverterId, pTimeoutInS):
    url = f'http://{OPENDTU_IP}/api/limit/status'
    timeout = pTimeoutInS
    timeout_start = time.time()
    while time.time() < timeout_start + timeout:
        time.sleep(0.5)
        ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), timeout=10).json()
        ack = (ParsedData[SERIAL_NUMBER[pInverterId]]['limit_set_status'] == 'Ok')
        if ack:
            break
    if ack:
        logger.info('OpenDTU: Inverter "%s": Limit acknowledged', NAME[pInverterId])
    else:
        logger.info('OpenDTU: Inverter "%s": Limit timeout!', NAME[pInverterId])
    return ack

def SetLimitWithPriority(pLimit):
    try:
        if SET_LIMIT_RETRY != -1:
            if not hasattr(SetLimitWithPriority, "LastLimit"):
                SetLimitWithPriority.LastLimit = CastToInt(0)
            if not hasattr(SetLimitWithPriority, "SameLimitCnt"):
                SetLimitWithPriority.SameLimitCnt = CastToInt(0)
            if not hasattr(SetLimitWithPriority, "LastLimitAck"):
                SetLimitWithPriority.LastLimitAck = bool(False)
            if (SetLimitWithPriority.LastLimit == pLimit) and SetLimitWithPriority.LastLimitAck:
                logger.info("Inverterlimit already at %s Watt",CastToInt(pLimit))
                return
            if (SetLimitWithPriority.LastLimit == pLimit):
                SetLimitWithPriority.SameLimitCnt = SetLimitWithPriority.SameLimitCnt + 1
            else:
                SetLimitWithPriority.LastLimit = pLimit
                SetLimitWithPriority.SameLimitCnt = 0
            if SetLimitWithPriority.SameLimitCnt >= SET_LIMIT_RETRY:
                logger.info("Retry Counter exceeded: Inverterlimit already at %s Watt",CastToInt(pLimit))
                time.sleep(SET_LIMIT_DELAY_IN_SECONDS)
                return
        logger.info("setting new limit to %s Watt",CastToInt(pLimit))
        SetLimitWithPriority.LastLimitAck = True
        if (pLimit <= GetMinWattFromAllInverters()):
            pLimit = 0 # set only minWatt for every inv.
        RemainingLimit = pLimit
        for j in range (1,6):
            if GetMaxWattFromAllInvertersSamePrio(j) <= 0:
                continue
            if RemainingLimit >= GetMaxWattFromAllInvertersSamePrio(j):
                LimitPrio = GetMaxWattFromAllInvertersSamePrio(j)
            else:
                LimitPrio = RemainingLimit    
            RemainingLimit = RemainingLimit - LimitPrio            
                       
            for i in range(INVERTER_COUNT):
                if (not AVAILABLE[i]) or (not HOY_BATTERY_GOOD_VOLTAGE[i]):
                    continue
                if HOY_BATTERY_PRIORITY[i] != j:
                    continue
                Factor = HOY_MAX_WATT[i] / GetMaxWattFromAllInvertersSamePrio(j)
                
                NewLimit = CastToInt(LimitPrio*Factor)
                NewLimit = ApplyLimitsToSetpointInverter(i, NewLimit)
                if HOY_COMPENSATE_WATT_FACTOR[i] != 1:
                    logger.info('Ahoy: Inverter "%s": compensate Limit from %s Watt to %s Watt', NAME[i], CastToInt(NewLimit), CastToInt(NewLimit*HOY_COMPENSATE_WATT_FACTOR[i]))
                    NewLimit = CastToInt(NewLimit * HOY_COMPENSATE_WATT_FACTOR[i])
                    NewLimit = ApplyLimitsToMaxInverterLimits(i, NewLimit)
                if USE_AHOY:
                    SetLimitAhoy(i, NewLimit)
                    if not WaitForAckAhoy(i, SET_LIMIT_TIMEOUT_SECONDS):
                        SetLimitWithPriority.LastLimitAck = False
                elif USE_OPENDTU:
                    SetLimitOpenDTU(i, NewLimit)
                    if not WaitForAckOpenDTU(i, SET_LIMIT_TIMEOUT_SECONDS):
                        SetLimitWithPriority.LastLimitAck = False
                else:
                    raise Exception("Error: DTU Type not defined")
    except:
        logger.error("Exception at SetLimitWithPriority")
        SetLimitWithPriority.LastLimitAck = False
        raise

def SetLimit(pLimit):
    try:
        if not GetMixedMode() and GetBatteryMode() and GetPriorityMode():
            SetLimitWithPriority(pLimit)
            return

        if SET_LIMIT_RETRY != -1:
            if not hasattr(SetLimit, "LastLimit"):
                SetLimit.LastLimit = CastToInt(0)
            if not hasattr(SetLimit, "SameLimitCnt"):
                SetLimit.SameLimitCnt = CastToInt(0)
            if not hasattr(SetLimit, "LastLimitAck"):
                SetLimit.LastLimitAck = bool(False)
            if (SetLimit.LastLimit == pLimit) and SetLimit.LastLimitAck:
                logger.info("Inverterlimit already at %s Watt",CastToInt(pLimit))
                return
            if (SetLimit.LastLimit == pLimit):
                SetLimit.SameLimitCnt = SetLimit.SameLimitCnt + 1
            else:
                SetLimit.LastLimit = pLimit
                SetLimit.SameLimitCnt = 0
            if SetLimit.SameLimitCnt >= SET_LIMIT_RETRY:
                logger.info("Retry Counter exceeded: Inverterlimit already at %s Watt",CastToInt(pLimit))
                time.sleep(SET_LIMIT_DELAY_IN_SECONDS)
                return
        logger.info("setting new limit to %s Watt",CastToInt(pLimit))
        SetLimit.LastLimitAck = True
        if (pLimit <= GetMinWattFromAllInverters()):
            pLimit = 0 # set only minWatt for every inv.
        for i in range(INVERTER_COUNT):
            if (not AVAILABLE[i]) or (not HOY_BATTERY_GOOD_VOLTAGE[i]):
                continue
            Factor = HOY_MAX_WATT[i] / GetMaxWattFromAllInverters()
            NewLimit = CastToInt(pLimit*Factor)
            NewLimit = ApplyLimitsToSetpointInverter(i, NewLimit)
            if HOY_COMPENSATE_WATT_FACTOR[i] != 1:
                logger.info('Ahoy: Inverter "%s": compensate Limit from %s Watt to %s Watt', NAME[i], CastToInt(NewLimit), CastToInt(NewLimit*HOY_COMPENSATE_WATT_FACTOR[i]))
                NewLimit = CastToInt(NewLimit * HOY_COMPENSATE_WATT_FACTOR[i])
                NewLimit = ApplyLimitsToMaxInverterLimits(i, NewLimit)
            if USE_AHOY:
                SetLimitAhoy(i, NewLimit)
                if not WaitForAckAhoy(i, SET_LIMIT_TIMEOUT_SECONDS):
                    SetLimit.LastLimitAck = False
            elif USE_OPENDTU:
                SetLimitOpenDTU(i, NewLimit)
                if not WaitForAckOpenDTU(i, SET_LIMIT_TIMEOUT_SECONDS):
                    SetLimit.LastLimitAck = False
            else:
                raise Exception("Error: DTU Type not defined")
    except:
        logger.error("Exception at SetLimit")
        SetLimit.LastLimitAck = False
        raise

def GetHoymilesAvailableOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), timeout=10).json()
    Reachable = bool(ParsedData["inverters"][pInverterId]["reachable"])
    logger.info('OpenDTU: Inverter "%s" reachable: %s',NAME[pInverterId],Reachable)
    return Reachable

def GetHoymilesAvailableAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/index'
    ParsedData = requests.get(url, timeout=10).json()
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
            except Exception as e:
                AVAILABLE[i] = False
                logger.error("Exception at GetHoymilesAvailable, Inverter %s (%s) not reachable", i, NAME[i])
                if hasattr(e, 'message'):
                    logger.error(e.message)
                else:
                    logger.error(e)
        return GetHoymilesAvailable
    except:
        logger.error('Exception at GetHoymilesAvailable')
        raise
    
def CheckAhoyVersion():
    MinVersion = '0.7.29'
    url = f'http://{AHOY_IP}/api/system'
    ParsedData = requests.get(url, timeout=10).json()
    AhoyVersion = str((ParsedData["version"]))
    logger.info('Ahoy: Current Version: %s',AhoyVersion)
    if version.parse(AhoyVersion) < version.parse(MinVersion):
        logger.error('Error: Your AHOY Version is too old! Please update at least to Version %s - you can find the newest dev-releases here: https://github.com/lumapu/ahoy/actions',MinVersion)
        quit()

def GetAhoyLimitFactor():
    Version = '0.8.39'
    url = f'http://{AHOY_IP}/api/system'
    ParsedData = requests.get(url, timeout=10).json()
    AhoyVersion = str((ParsedData["version"]))
    if version.parse(AhoyVersion) < version.parse(Version):
        return 1
    else:
        return 10

def GetHoymilesInfoOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), timeout=10).json()
    SERIAL_NUMBER[pInverterId] = str(ParsedData['inverters'][pInverterId]['serial'])
    TEMPERATURE[pInverterId] = str(round(float((ParsedData['inverters'][pInverterId]['INV']['0']['Temperature']['v'])),1)) + ' degC'
    NAME[pInverterId] = str(ParsedData['inverters'][pInverterId]['name'])
    logger.info('OpenDTU: Inverter "%s" / serial number "%s" / temperature %s',NAME[pInverterId],SERIAL_NUMBER[pInverterId],TEMPERATURE[pInverterId])

def GetHoymilesInfoAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/live'
    ParsedData = requests.get(url, timeout=10).json()
    temp_index = ParsedData["ch0_fld_names"].index("Temp")
    
    url = f'http://{AHOY_IP}/api/inverter/id/{pInverterId}'
    ParsedData = requests.get(url, timeout=10).json()
    SERIAL_NUMBER[pInverterId] = str(ParsedData['serial'])
    NAME[pInverterId] = str(ParsedData['name'])
    TEMPERATURE[pInverterId] = str(ParsedData["ch"][0][temp_index]) + ' degC'
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
            except Exception as e:
                logger.error('Exception at GetHoymilesInfo, Inverter "%s" not reachable', NAME[i])
                if hasattr(e, 'message'):
                    logger.error(e.message)
                else:
                    logger.error(e)
    except:
        logger.error("Exception at GetHoymilesInfo")
        raise

def GetHoymilesPanelMinVoltageAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/live'
    ParsedData = requests.get(url, timeout=10).json()
    PanelVDC_index = ParsedData["fld_names"].index("U_DC")
    url = f'http://{AHOY_IP}/api/inverter/id/{pInverterId}'
    ParsedData = requests.get(url, timeout=10).json()
    PanelVDC = []
    ExcludedPanels = GetNumberArray(HOY_BATTERY_IGNORE_PANELS[pInverterId])
    for i in range(1, len(ParsedData['ch']), 1):
        if i not in ExcludedPanels:
            PanelVDC.append(float(ParsedData['ch'][i][PanelVDC_index]))
    minVdc = float('inf')
    for i in range(len(PanelVDC)):
        if (minVdc > PanelVDC[i]) and (PanelVDC[i] > 5):
            minVdc = PanelVDC[i]
    if minVdc == float('inf'):
        minVdc = 0

    # save last 5 min-values in list and return the "highest" value.
    HOY_PANEL_VOLTAGE_LIST[pInverterId].append(minVdc)
    if len(HOY_PANEL_VOLTAGE_LIST[pInverterId]) > 5:
        HOY_PANEL_VOLTAGE_LIST[pInverterId].pop(0)
    max_value = None
    for num in HOY_PANEL_VOLTAGE_LIST[pInverterId]:
        if (max_value is None or num > max_value):
            max_value = num

    logger.info('Lowest panel voltage inverter "%s": %s Volt',NAME[pInverterId],max_value)
    return max_value

def GetHoymilesPanelMinVoltageOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), timeout=10).json()
    PanelVDC = []
    ExcludedPanels = GetNumberArray(HOY_BATTERY_IGNORE_PANELS[pInverterId])
    for i in range(len(ParsedData['inverters'][pInverterId]['DC'])):
        if i not in ExcludedPanels:
            PanelVDC.append(float(ParsedData['inverters'][pInverterId]['DC'][str(i)]['Voltage']['v']))
    minVdc = float('inf')
    for i in range(len(PanelVDC)):
        if (minVdc > PanelVDC[i]) and (PanelVDC[i] > 5):
            minVdc = PanelVDC[i]
    if minVdc == float('inf'):
        minVdc = 0

    # save last 5 min-values in list and return the "highest" value.
    HOY_PANEL_VOLTAGE_LIST[pInverterId].append(minVdc)
    if len(HOY_PANEL_VOLTAGE_LIST[pInverterId]) > 5:
        HOY_PANEL_VOLTAGE_LIST[pInverterId].pop(0)
    max_value = None
    for num in HOY_PANEL_VOLTAGE_LIST[pInverterId]:
        if (max_value is None or num > max_value):
            max_value = num

    logger.info('Lowest panel voltage inverter "%s": %s Volt',NAME[pInverterId],max_value)
    return max_value

def GetHoymilesPanelMinVoltage(pInverterId):
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
        raise

def SetHoymilesPowerStatusAhoy(pInverterId, pActive):
    url = f"http://{AHOY_IP}/api/ctrl"
    data = f'''{{"id": {pInverterId}, "cmd": "power", "val": {CastToInt(pActive == True)}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    if pActive:
        logger.info('Ahoy: Inverter "%s": Turn on',NAME[pInverterId])
    else:
        logger.info('Ahoy: Inverter "%s": Turn off',NAME[pInverterId])
    requests.post(url, data=data, headers=headers)

def SetHoymilesPowerStatusOpenDTU(pInverterId, pActive):
    url=f"http://{OPENDTU_IP}/api/power/config"
    data = f'''data={{"serial":"{SERIAL_NUMBER[pInverterId]}", "power":{CastToInt(pActive == True)}}}'''
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    if pActive:
        logger.info('OpenDTU: Inverter "%s": Turn on',NAME[pInverterId])
    else:
        logger.info('OpenDTU: Inverter "%s": Turn off',NAME[pInverterId])
    a = requests.post(url, data=data, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), headers=headers)

def SetHoymilesPowerStatus(pInverterId, pActive):
    try:
        if not AVAILABLE[pInverterId]:
            return
        if SET_LIMIT_RETRY != -1:
            if not hasattr(SetHoymilesPowerStatus, "LastPowerStatus"):
                SetHoymilesPowerStatus.LastPowerStatus = []
                SetHoymilesPowerStatus.LastPowerStatus = [False for i in range(INVERTER_COUNT)]
            if not hasattr(SetHoymilesPowerStatus, "SamePowerStatusCnt"):
                SetHoymilesPowerStatus.SamePowerStatusCnt = []
                SetHoymilesPowerStatus.SamePowerStatusCnt = [0 for i in range(INVERTER_COUNT)]
            if SetHoymilesPowerStatus.LastPowerStatus[pInverterId] == pActive:
                SetHoymilesPowerStatus.SamePowerStatusCnt[pInverterId] = SetHoymilesPowerStatus.SamePowerStatusCnt[pInverterId] + 1
            else:
                SetHoymilesPowerStatus.LastPowerStatus[pInverterId] = pActive
                SetHoymilesPowerStatus.SamePowerStatusCnt[pInverterId] = 0
            if SetHoymilesPowerStatus.SamePowerStatusCnt[pInverterId] >= SET_LIMIT_RETRY:
                if pActive:
                    logger.info("Retry Counter exceeded: Inverter PowerStatus already ON")
                else:
                    logger.info("Retry Counter exceeded: Inverter PowerStatus already OFF")
                return
        if USE_AHOY:
            SetHoymilesPowerStatusAhoy(pInverterId, pActive)
        elif USE_OPENDTU:
            SetHoymilesPowerStatusOpenDTU(pInverterId, pActive)
        else:
            raise Exception("Error: DTU Type not defined")
        time.sleep(SET_POWER_STATUS_DELAY_IN_SECONDS)
    except:
        logger.error("Exception at SetHoymilesPowerStatus")
        raise
    
def GetNumberArray(pExcludedPanels):
    lclExcludedPanelsList = pExcludedPanels.split(',')
    result = []
    for number_str in lclExcludedPanelsList:
        if number_str == '':
            continue
        number = int(number_str.strip())
        result.append(number)
    return result

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
                    HOY_BATTERY_GOOD_VOLTAGE[i] = False
                    HOY_MAX_WATT[i] = HOY_BATTERY_REDUCE_WATT[i]

                elif minVoltage <= HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V[i]:
                    if HOY_MAX_WATT[i] != HOY_BATTERY_REDUCE_WATT[i]:
                        HOY_MAX_WATT[i] = HOY_BATTERY_REDUCE_WATT[i]
                        SetLimit.LastLimit = -1

                elif minVoltage >= HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V[i]:
                    SetHoymilesPowerStatus(i, True)
                    if not HOY_BATTERY_GOOD_VOLTAGE[i]:
                        if USE_AHOY:
                            SetLimitAhoy(i, HOY_MIN_WATT[i])
                            WaitForAckAhoy(i, SET_LIMIT_TIMEOUT_SECONDS)
                        else:
                            SetLimitOpenDTU(i, HOY_MIN_WATT[i])
                            WaitForAckOpenDTU(i, SET_LIMIT_TIMEOUT_SECONDS)
                        SetLimit.LastLimit = -1
                    HOY_BATTERY_GOOD_VOLTAGE[i] = True
                    HOY_MAX_WATT[i] = HOY_BATTERY_NORMAL_WATT[i]

                elif minVoltage >= HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V[i]:
                    if HOY_MAX_WATT[i] != HOY_BATTERY_NORMAL_WATT[i]:
                        HOY_MAX_WATT[i] = HOY_BATTERY_NORMAL_WATT[i]
                        SetLimit.LastLimit = -1

                if HOY_BATTERY_GOOD_VOLTAGE[i]:
                    result = True
            except:
                logger.error("Exception at CheckBattery, Inverter %s not reachable", i)
        return result
    except:
        logger.error("Exception at CheckBattery")
        raise

def GetHoymilesTemperatureOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), timeout=10).json()
    TEMPERATURE[pInverterId] = str(round(float((ParsedData['inverters'][pInverterId]['INV']['0']['Temperature']['v'])),1)) + ' degC'
    logger.info('OpenDTU: Inverter "%s" temperature: %s',NAME[pInverterId],TEMPERATURE[pInverterId])

def GetHoymilesTemperatureAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/live'
    ParsedData = requests.get(url, timeout=10).json()
    temp_index = ParsedData["ch0_fld_names"].index("Temp")
    url = f'http://{AHOY_IP}/api/inverter/id/{pInverterId}'
    ParsedData = requests.get(url, timeout=10).json()
    TEMPERATURE[pInverterId] = str(ParsedData["ch"][0][temp_index]) + ' degC'
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
    except:
        logger.error("Exception at GetHoymilesTemperature")
        raise

def GetHoymilesActualPowerOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), timeout=10).json()
    ActualPower = CastToInt(ParsedData['inverters'][pInverterId]['AC']['0']['Power']['v'])
    logger.info('OpenDTU: Inverter "%s" power producing: %s %s',NAME[pInverterId],ActualPower," Watt")
    return CastToInt(ActualPower)

def GetHoymilesActualPowerAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/live'
    ParsedData = requests.get(url, timeout=10).json()
    ActualPower_index = ParsedData["ch0_fld_names"].index("P_AC")
    url = f'http://{AHOY_IP}/api/inverter/id/{pInverterId}'
    ParsedData = requests.get(url, timeout=10).json()
    ActualPower = CastToInt(ParsedData["ch"][0][ActualPower_index])
    logger.info('Ahoy: Inverter "%s" power producing: %s %s',NAME[pInverterId],ActualPower," Watt")
    return CastToInt(ActualPower)

def GetHoymilesActualPower():
    try:
        ActualPower = 0
        if USE_SHELLY_EM_INTERMEDIATE:
            return GetPowermeterWattsShellyEM_Intermediate()        
        elif USE_SHELLY_3EM_INTERMEDIATE:
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
        elif USE_HOMEASSISTANT_INTERMEDIATE:
            return GetPowermeterWattsHomeAssistant_Intermediate()
        elif USE_VZLOGGER_INTERMEDIATE:
            return GetPowermeterWattsVZLogger_Intermediate()
        elif USE_AHOY:
            for i in range(INVERTER_COUNT):
                if (not AVAILABLE[i]) or (not HOY_BATTERY_GOOD_VOLTAGE[i]):
                    continue
                ActualPower = ActualPower + GetHoymilesActualPowerAhoy(i)
            return ActualPower
        elif USE_OPENDTU:
            for i in range(INVERTER_COUNT):
                if (not AVAILABLE[i]) or (not HOY_BATTERY_GOOD_VOLTAGE[i]):
                    continue
                ActualPower = ActualPower + GetHoymilesActualPowerOpenDTU(i)
            return ActualPower
        else:
            raise Exception("Error: DTU Type not defined")
    except:
        logger.error("Exception at GetHoymilesActualPower")
        raise

def GetPowermeterWattsTasmota_Intermediate():
    url = f'http://{TASMOTA_IP_INTERMEDIATE}/cm?cmnd=status%2010'
    ParsedData = requests.get(url, timeout=10).json()
    Watts = CastToInt(ParsedData[TASMOTA_JSON_STATUS_INTERMEDIATE][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX_INTERMEDIATE][TASMOTA_JSON_POWER_MQTT_LABEL_INTERMEDIATE])
    logger.info("intermediate meter Tasmota: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShelly1PM_Intermediate():
    url = f'http://{SHELLY_IP_INTERMEDIATE}/status'
    headers = {"content-type": "application/json"}
    ParsedData = requests.get(url, headers=headers, auth=(SHELLY_USER_INTERMEDIATE,SHELLY_PASS_INTERMEDIATE), timeout=10).json()
    Watts = CastToInt(ParsedData['meters'][0]['power'])
    logger.info("intermediate meter Shelly 1PM: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShellyPlus1PM_Intermediate():
    url = f'http://{SHELLY_IP_INTERMEDIATE}/rpc/Switch.GetStatus?id=0'
    headers = {"content-type": "application/json"}
    ParsedData = requests.get(url, headers=headers, auth=HTTPDigestAuth(SHELLY_USER_INTERMEDIATE,SHELLY_PASS_INTERMEDIATE), timeout=10).json()
    Watts = CastToInt(ParsedData['apower'])
    logger.info("intermediate meter Shelly Plus 1PM: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShellyEM_Intermediate():
    url = f'http://{SHELLY_IP_INTERMEDIATE}/status'
    headers = {"content-type": "application/json"}
    ParsedData = requests.get(url, headers=headers, auth=(SHELLY_USER_INTERMEDIATE,SHELLY_PASS_INTERMEDIATE), timeout=10).json()
    Watts = sum(CastToInt(emeter['power']) for emeter in ParsedData['emeters'])
    logger.info("intermediate meter Shelly EM: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShelly3EM_Intermediate():
    url = f'http://{SHELLY_IP_INTERMEDIATE}/status'
    headers = {"content-type": "application/json"}
    ParsedData = requests.get(url, headers=headers, auth=(SHELLY_USER_INTERMEDIATE,SHELLY_PASS_INTERMEDIATE), timeout=10).json()
    Watts = CastToInt(ParsedData['total_power'])
    logger.info("intermediate meter Shelly 3EM: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShelly3EMPro_Intermediate():
    url = f'http://{SHELLY_IP_INTERMEDIATE}/rpc/EM.GetStatus?id=0'
    headers = {"content-type": "application/json"}
    ParsedData = requests.get(url, headers=headers, auth=HTTPDigestAuth(SHELLY_USER_INTERMEDIATE,SHELLY_PASS_INTERMEDIATE), timeout=10).json()
    Watts = CastToInt(ParsedData['total_act_power'])
    logger.info("intermediate meter Shelly 3EM Pro: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShrdzm_Intermediate():
    url = f'http://{SHRDZM_IP_INTERMEDIATE}/getLastData?user={SHRDZM_USER_INTERMEDIATE}&password={SHRDZM_PASS_INTERMEDIATE}'
    ParsedData = requests.get(url, timeout=10).json()
    Watts = CastToInt(CastToInt(ParsedData['1.7.0']) - CastToInt(ParsedData['2.7.0']))
    logger.info("intermediate meter SHRDZM: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsEmlog_Intermediate():
    url = f'http://{EMLOG_IP_INTERMEDIATE}/pages/getinformation.php?heute&meterindex={EMLOG_METERINDEX_INTERMEDIATE}'
    ParsedData = requests.get(url, timeout=10).json()
    Watts = CastToInt(ParsedData['Leistung170'])
    logger.info("intermediate meter EMLOG: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsIobroker_Intermediate():
    url = f'http://{IOBROKER_IP_INTERMEDIATE}:{IOBROKER_PORT_INTERMEDIATE}/getBulk/{IOBROKER_CURRENT_POWER_ALIAS_INTERMEDIATE}'
    ParsedData = requests.get(url, timeout=10).json()
    Watts = CastToInt(ParsedData[0]['val'])
    logger.info("intermediate meter IOBROKER: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsHomeAssistant_Intermediate():
    url = f"http://{HA_IP_INTERMEDIATE}:{HA_PORT_INTERMEDIATE}/api/states/{HA_CURRENT_POWER_ENTITY_INTERMEDIATE}"
    headers = {"Authorization": "Bearer " + HA_ACCESSTOKEN_INTERMEDIATE, "content-type": "application/json"}
    ParsedData = requests.get(url, headers=headers, timeout=10).json()
    Watts = CastToInt(ParsedData['state'])
    logger.info("intermediate meter HomeAssistant: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsVZLogger_Intermediate():
    url = f"http://{VZL_IP_INTERMEDIATE}:{VZL_PORT_INTERMEDIATE}/{VZL_UUID_INTERMEDIATE}"
    ParsedData = requests.get(url, timeout=10).json()
    Watts = CastToInt(ParsedData['data'][0]['tuples'][0][1])
    logger.info("intermediate meter VZLogger: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsTasmota():
    url = f'http://{TASMOTA_IP}/cm?cmnd=status%2010'
    ParsedData = requests.get(url, timeout=10).json()
    if not TASMOTA_JSON_POWER_CALCULATE:
        Watts = CastToInt(ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_MQTT_LABEL])
    else:
        input = ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_INPUT_MQTT_LABEL]
        ouput = ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_OUTPUT_MQTT_LABEL]
        Watts = CastToInt(input - ouput)
    logger.info("powermeter Tasmota: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShellyEM():
    url = f'http://{SHELLY_IP}/status'
    headers = {"content-type": "application/json"}
    ParsedData = requests.get(url, headers=headers, auth=(SHELLY_USER,SHELLY_PASS), timeout=10).json()
    Watts = sum(CastToInt(emeter['power']) for emeter in ParsedData['emeters'])
    logger.info("powermeter Shelly EM: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShelly3EM():
    url = f'http://{SHELLY_IP}/status'
    headers = {"content-type": "application/json"}
    ParsedData = requests.get(url, headers=headers, auth=(SHELLY_USER,SHELLY_PASS), timeout=10).json()
    Watts = CastToInt(ParsedData['total_power'])
    logger.info("powermeter Shelly 3EM: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShelly3EMPro():
    url = f'http://{SHELLY_IP}/rpc/EM.GetStatus?id=0'
    headers = {"content-type": "application/json"}
    ParsedData = requests.get(url, headers=headers, auth=HTTPDigestAuth(SHELLY_USER,SHELLY_PASS), timeout=10).json()
    Watts = CastToInt(ParsedData['total_act_power'])
    logger.info("powermeter Shelly 3EM Pro: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsShrdzm():
    url = f'http://{SHRDZM_IP}/getLastData?user={SHRDZM_USER}&password={SHRDZM_PASS}'
    ParsedData = requests.get(url, timeout=10).json()
    Watts = CastToInt(CastToInt(ParsedData['1.7.0']) - CastToInt(ParsedData['2.7.0']))
    logger.info("powermeter SHRDZM: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsEmlog():
    url = f'http://{EMLOG_IP}/pages/getinformation.php?heute&meterindex={EMLOG_METERINDEX}'
    ParsedData = requests.get(url, timeout=10).json()
    Watts = CastToInt(CastToInt(ParsedData['Leistung170']) - CastToInt(ParsedData['Leistung270']))
    logger.info("powermeter EMLOG: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsIobroker():
    if not IOBROKER_POWER_CALCULATE:
        url = f'http://{IOBROKER_IP}:{IOBROKER_PORT}/getBulk/{IOBROKER_CURRENT_POWER_ALIAS}'
        ParsedData = requests.get(url, timeout=10).json()
        for item in ParsedData:
            if item['id'] == IOBROKER_CURRENT_POWER_ALIAS:
                Watts = CastToInt(item['val'])
                break
    else:
        url = f'http://{IOBROKER_IP}:{IOBROKER_PORT}/getBulk/{IOBROKER_POWER_INPUT_ALIAS},{IOBROKER_POWER_OUTPUT_ALIAS}'
        ParsedData = requests.get(url, timeout=10).json()
        for item in ParsedData:
            if item['id'] == IOBROKER_POWER_INPUT_ALIAS:
                input = CastToInt(item['val'])
            if item['id'] == IOBROKER_POWER_OUTPUT_ALIAS:
                output = CastToInt(item['val'])
        Watts = CastToInt(input - output)
    logger.info("powermeter IOBROKER: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsHomeAssistant():
    if not HA_POWER_CALCULATE:
        url = f"http://{HA_IP}:{HA_PORT}/api/states/{HA_CURRENT_POWER_ENTITY}"
        headers = {"Authorization": "Bearer " + HA_ACCESSTOKEN, "content-type": "application/json"}
        ParsedData = requests.get(url, headers=headers, timeout=10).json()
        Watts = CastToInt(ParsedData['state'])
    else:
        url = f"http://{HA_IP}:{HA_PORT}/api/states/{HA_POWER_INPUT_ALIAS}"
        headers = {"Authorization": "Bearer " + HA_ACCESSTOKEN, "content-type": "application/json"}
        ParsedData = requests.get(url, headers=headers, timeout=10).json()
        input = CastToInt(ParsedData['state'])
        url = f"http://{HA_IP}:{HA_PORT}/api/states/{HA_POWER_OUTPUT_ALIAS}"
        headers = {"Authorization": "Bearer " + HA_ACCESSTOKEN, "content-type": "application/json"}
        ParsedData = requests.get(url, headers=headers, timeout=10).json()
        output = CastToInt(ParsedData['state'])
        Watts = CastToInt(input - output)
    logger.info("powermeter HomeAssistant: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWattsVZLogger():
    url = f"http://{VZL_IP}:{VZL_PORT}/{VZL_UUID}"
    ParsedData = requests.get(url, timeout=10).json()
    Watts = CastToInt(ParsedData['data'][0]['tuples'][0][1])
    logger.info("powermeter VZLogger: %s %s",Watts," Watt")
    return CastToInt(Watts)

def GetPowermeterWatts():
    try:
        if USE_SHELLY_EM:
            return GetPowermeterWattsShellyEM()
        elif USE_SHELLY_3EM:
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
        elif USE_HOMEASSISTANT:
            return GetPowermeterWattsHomeAssistant()
        elif USE_VZLOGGER:
            return GetPowermeterWattsVZLogger()
        else:
            raise Exception("Error: no powermeter defined!")
    except:
        logger.error("Exception at GetPowermeterWatts")
        raise

def CutLimitToProduction(pSetpoint):
    if pSetpoint != GetMaxWattFromAllInverters():
        ActualPower = GetHoymilesActualPower()
        # prevent the setpoint from running away...
        if pSetpoint > ActualPower + (GetMaxWattFromAllInverters() * MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER / 100):
            pSetpoint = CastToInt(ActualPower + (GetMaxWattFromAllInverters() * MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER / 100))
            logger.info('Cut limit to %s Watt, limit was higher than %s percent of live-production', CastToInt(pSetpoint), MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER)
    return CastToInt(pSetpoint)

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

def ApplyLimitsToMaxInverterLimits(pInverter, pSetpoint):
    if pSetpoint > HOY_INVERTER_WATT[pInverter]:
        pSetpoint = HOY_INVERTER_WATT[pInverter]
    if pSetpoint < HOY_MIN_WATT[pInverter]:
        pSetpoint = HOY_MIN_WATT[pInverter]
    return pSetpoint

# Max possible Watts, can be reduced on battery mode
def GetMaxWattFromAllInverters():
    maxWatt = 0
    for i in range(INVERTER_COUNT):
        if (not AVAILABLE[i]) or (not HOY_BATTERY_GOOD_VOLTAGE[i]):
            continue
        maxWatt = maxWatt + HOY_MAX_WATT[i]
    return maxWatt

# Max possible Watts, can be reduced on battery mode
def GetMaxWattFromAllInvertersSamePrio(pPriority):
    maxWatt = 0
    for i in range(INVERTER_COUNT):
        if (not AVAILABLE[i]) or (not HOY_BATTERY_GOOD_VOLTAGE[i]):
            continue
        if HOY_BATTERY_PRIORITY[i] == pPriority:
            maxWatt = maxWatt + HOY_MAX_WATT[i]
    return maxWatt

# Max possible Watts (physically) - Inverter Specification!
def GetMaxInverterWattFromAllInverters():
    maxWatt = 0
    for i in range(INVERTER_COUNT):
        if (not AVAILABLE[i]) or (not HOY_BATTERY_GOOD_VOLTAGE[i]):
            continue
        maxWatt = maxWatt + HOY_INVERTER_WATT[i]
    return maxWatt

def GetMinWattFromAllInverters():
    minWatt = 0
    for i in range(INVERTER_COUNT):
        if (not AVAILABLE[i]) or (not HOY_BATTERY_GOOD_VOLTAGE[i]):
            continue
        minWatt = minWatt + HOY_MIN_WATT[i]
    return minWatt

def GetMixedMode():
    #if battery mode and custom priority use SetLimitWithPriority
    for i in range(INVERTER_COUNT):
        for j in range(INVERTER_COUNT):
            if (HOY_BATTERY_MODE[i] != HOY_BATTERY_MODE[j]):
                return True
    return False

def GetBatteryMode():
    for i in range(INVERTER_COUNT):
        if HOY_BATTERY_MODE[i]:
            return True
    return False

def GetPriorityMode():
    for i in range(INVERTER_COUNT):
        for j in range(INVERTER_COUNT):
            if HOY_BATTERY_PRIORITY[i] != HOY_BATTERY_PRIORITY[j]:
                return True
    return False

# ----- START -----

logger.info("Author: %s / Script Version: %s",__author__, __version__)

# read config:
logger.info("read config file: " + str(Path.joinpath(Path(__file__).parent.resolve(), "HoymilesZeroExport_Config.ini")))
if args.config:
    logger.info("read additional config file: " + args.config)

VERSION = config.get('VERSION', 'VERSION')
logger.info("Config file V %s", VERSION)
USE_AHOY = config.getboolean('SELECT_DTU', 'USE_AHOY')
USE_OPENDTU = config.getboolean('SELECT_DTU', 'USE_OPENDTU')
USE_TASMOTA = config.getboolean('SELECT_POWERMETER', 'USE_TASMOTA')
USE_SHELLY_EM = config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_EM')
USE_SHELLY_3EM = config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_3EM')
USE_SHELLY_3EM_PRO = config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_3EM_PRO')
USE_SHRDZM = config.getboolean('SELECT_POWERMETER', 'USE_SHRDZM')
USE_EMLOG = config.getboolean('SELECT_POWERMETER', 'USE_EMLOG')
USE_IOBROKER = config.getboolean('SELECT_POWERMETER', 'USE_IOBROKER')
USE_HOMEASSISTANT = config.getboolean('SELECT_POWERMETER', 'USE_HOMEASSISTANT')
USE_VZLOGGER = config.getboolean('SELECT_POWERMETER', 'USE_VZLOGGER')
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
SHELLY_IP = config.get('SHELLY', 'SHELLY_IP')
SHELLY_USER = config.get('SHELLY', 'SHELLY_USER')
SHELLY_PASS = config.get('SHELLY', 'SHELLY_PASS')
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
HA_IP = config.get('HOMEASSISTANT', 'HA_IP')
HA_PORT = config.get('HOMEASSISTANT', 'HA_PORT')
HA_ACCESSTOKEN = config.get('HOMEASSISTANT', 'HA_ACCESSTOKEN')
HA_CURRENT_POWER_ENTITY = config.get('HOMEASSISTANT', 'HA_CURRENT_POWER_ENTITY')
HA_POWER_CALCULATE = config.getboolean('HOMEASSISTANT', 'HA_POWER_CALCULATE')
HA_POWER_INPUT_ALIAS = config.get('HOMEASSISTANT', 'HA_POWER_INPUT_ALIAS')
HA_POWER_OUTPUT_ALIAS = config.get('HOMEASSISTANT', 'HA_POWER_OUTPUT_ALIAS')
VZL_IP = config.get('VZLOGGER', 'VZL_IP')
VZL_PORT = config.get('VZLOGGER', 'VZL_PORT')
VZL_UUID = config.get('VZLOGGER', 'VZL_UUID')
USE_TASMOTA_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_TASMOTA_INTERMEDIATE')
USE_SHELLY_EM_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHELLY_EM_INTERMEDIATE')
USE_SHELLY_3EM_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHELLY_3EM_INTERMEDIATE')
USE_SHELLY_3EM_PRO_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHELLY_3EM_PRO_INTERMEDIATE')
USE_SHELLY_1PM_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHELLY_1PM_INTERMEDIATE')
USE_SHELLY_PLUS_1PM_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHELLY_PLUS_1PM_INTERMEDIATE')
USE_SHRDZM_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_SHRDZM_INTERMEDIATE')
USE_EMLOG_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_EMLOG_INTERMEDIATE')
USE_IOBROKER_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_IOBROKER_INTERMEDIATE')
USE_HOMEASSISTANT_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_HOMEASSISTANT_INTERMEDIATE')
USE_VZLOGGER_INTERMEDIATE = config.getboolean('SELECT_INTERMEDIATE_METER', 'USE_VZLOGGER_INTERMEDIATE')
TASMOTA_IP_INTERMEDIATE = config.get('INTERMEDIATE_TASMOTA', 'TASMOTA_IP_INTERMEDIATE')
TASMOTA_JSON_STATUS_INTERMEDIATE = config.get('INTERMEDIATE_TASMOTA', 'TASMOTA_JSON_STATUS_INTERMEDIATE')
TASMOTA_JSON_PAYLOAD_MQTT_PREFIX_INTERMEDIATE = config.get('INTERMEDIATE_TASMOTA', 'TASMOTA_JSON_PAYLOAD_MQTT_PREFIX_INTERMEDIATE')
TASMOTA_JSON_POWER_MQTT_LABEL_INTERMEDIATE = config.get('INTERMEDIATE_TASMOTA', 'TASMOTA_JSON_POWER_MQTT_LABEL_INTERMEDIATE')
SHELLY_IP_INTERMEDIATE = config.get('INTERMEDIATE_SHELLY', 'SHELLY_IP_INTERMEDIATE')
SHELLY_USER_INTERMEDIATE = config.get('INTERMEDIATE_SHELLY', 'SHELLY_USER_INTERMEDIATE')
SHELLY_PASS_INTERMEDIATE = config.get('INTERMEDIATE_SHELLY', 'SHELLY_PASS_INTERMEDIATE')
SHRDZM_IP_INTERMEDIATE = config.get('INTERMEDIATE_SHRDZM', 'SHRDZM_IP_INTERMEDIATE')
SHRDZM_USER_INTERMEDIATE = config.get('INTERMEDIATE_SHRDZM', 'SHRDZM_USER_INTERMEDIATE')
SHRDZM_PASS_INTERMEDIATE = config.get('INTERMEDIATE_SHRDZM', 'SHRDZM_PASS_INTERMEDIATE')
EMLOG_IP_INTERMEDIATE = config.get('INTERMEDIATE_EMLOG', 'EMLOG_IP_INTERMEDIATE')
EMLOG_METERINDEX_INTERMEDIATE = config.get('INTERMEDIATE_EMLOG', 'EMLOG_METERINDEX_INTERMEDIATE')
IOBROKER_IP_INTERMEDIATE = config.get('INTERMEDIATE_IOBROKER', 'IOBROKER_IP_INTERMEDIATE')
IOBROKER_PORT_INTERMEDIATE = config.get('INTERMEDIATE_IOBROKER', 'IOBROKER_PORT_INTERMEDIATE')
IOBROKER_CURRENT_POWER_ALIAS_INTERMEDIATE = config.get('INTERMEDIATE_IOBROKER', 'IOBROKER_CURRENT_POWER_ALIAS_INTERMEDIATE')
HA_IP_INTERMEDIATE = config.get('INTERMEDIATE_HOMEASSISTANT', 'HA_IP_INTERMEDIATE')
HA_PORT_INTERMEDIATE = config.get('INTERMEDIATE_HOMEASSISTANT', 'HA_PORT_INTERMEDIATE')
HA_ACCESSTOKEN_INTERMEDIATE = config.get('INTERMEDIATE_HOMEASSISTANT', 'HA_ACCESSTOKEN_INTERMEDIATE')
HA_CURRENT_POWER_ENTITY_INTERMEDIATE = config.get('INTERMEDIATE_HOMEASSISTANT', 'HA_CURRENT_POWER_ENTITY_INTERMEDIATE')
VZL_IP_INTERMEDIATE = config.get('INTERMEDIATE_VZLOGGER', 'VZL_IP_INTERMEDIATE')
VZL_PORT_INTERMEDIATE = config.get('INTERMEDIATE_VZLOGGER', 'VZL_PORT_INTERMEDIATE')
VZL_UUID_INTERMEDIATE = config.get('INTERMEDIATE_VZLOGGER', 'VZL_UUID_INTERMEDIATE')
INVERTER_COUNT = config.getint('COMMON', 'INVERTER_COUNT')
LOOP_INTERVAL_IN_SECONDS = config.getint('COMMON', 'LOOP_INTERVAL_IN_SECONDS')
SET_LIMIT_DELAY_IN_SECONDS = config.getint('COMMON', 'SET_LIMIT_DELAY_IN_SECONDS')
SET_LIMIT_TIMEOUT_SECONDS = config.getint('COMMON', 'SET_LIMIT_TIMEOUT_SECONDS')
SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER = config.getint('COMMON', 'SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER')
SET_POWER_STATUS_DELAY_IN_SECONDS = config.getint('COMMON', 'SET_POWER_STATUS_DELAY_IN_SECONDS')
POLL_INTERVAL_IN_SECONDS = config.getint('COMMON', 'POLL_INTERVAL_IN_SECONDS')
ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT = config.getint('COMMON', 'ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT')
MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER = config.getint('COMMON', 'MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER')
SET_LIMIT_RETRY = config.getint('COMMON', 'SET_LIMIT_RETRY')
SLOW_APPROX_FACTOR_IN_PERCENT = config.getint('COMMON', 'SLOW_APPROX_FACTOR_IN_PERCENT')
LOG_TEMPERATURE = config.getboolean('COMMON', 'LOG_TEMPERATURE')
POWERMETER_TARGET_POINT = config.getint('CONTROL', 'POWERMETER_TARGET_POINT')
POWERMETER_TOLERANCE = config.getint('CONTROL', 'POWERMETER_TOLERANCE')
POWERMETER_MAX_POINT = config.getint('CONTROL', 'POWERMETER_MAX_POINT')
if POWERMETER_MAX_POINT < (POWERMETER_TARGET_POINT + POWERMETER_TOLERANCE):
    POWERMETER_MAX_POINT = POWERMETER_TARGET_POINT + POWERMETER_TOLERANCE + 50
    logger.info('Warning: POWERMETER_MAX_POINT < POWERMETER_TARGET_POINT + POWERMETER_TOLERANCE. Setting POWERMETER_MAX_POINT to ' + str(POWERMETER_MAX_POINT))
SERIAL_NUMBER = []
NAME = []
TEMPERATURE = []
HOY_MAX_WATT = []
HOY_INVERTER_WATT = []
HOY_MIN_WATT = []
CURRENT_LIMIT = []
AVAILABLE = []
HOY_BATTERY_GOOD_VOLTAGE = []
HOY_COMPENSATE_WATT_FACTOR = []
HOY_BATTERY_MODE = []
HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V = []
HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V = []
HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V = []
HOY_BATTERY_NORMAL_WATT = []
HOY_BATTERY_REDUCE_WATT = []
HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V = []
HOY_BATTERY_IGNORE_PANELS = []
HOY_BATTERY_PRIORITY = []
HOY_PANEL_VOLTAGE_LIST = []
for i in range(INVERTER_COUNT):
    SERIAL_NUMBER.append(str('yet unknown'))
    NAME.append(str('yet unknown'))
    TEMPERATURE.append(str('--- degC'))
    HOY_MAX_WATT.append(config.getint('INVERTER_' + str(i + 1), 'HOY_MAX_WATT'))
    HOY_INVERTER_WATT.append(HOY_MAX_WATT[i])
    HOY_MIN_WATT.append(int(HOY_MAX_WATT[i] * config.getint('INVERTER_' + str(i + 1), 'HOY_MIN_WATT_IN_PERCENT') / 100))
    CURRENT_LIMIT.append(int(0))
    AVAILABLE.append(bool(False))
    HOY_BATTERY_GOOD_VOLTAGE.append(bool(True))
    HOY_BATTERY_MODE.append(config.getboolean('INVERTER_' + str(i + 1), 'HOY_BATTERY_MODE'))
    HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V.append(config.getfloat('INVERTER_' + str(i + 1), 'HOY_BATTERY_THRESHOLD_OFF_LIMIT_IN_V'))
    HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V.append(config.getfloat('INVERTER_' + str(i + 1), 'HOY_BATTERY_THRESHOLD_REDUCE_LIMIT_IN_V'))
    HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V.append(config.getfloat('INVERTER_' + str(i + 1), 'HOY_BATTERY_THRESHOLD_NORMAL_LIMIT_IN_V'))
    HOY_BATTERY_NORMAL_WATT.append(config.getint('INVERTER_' + str(i + 1), 'HOY_BATTERY_NORMAL_WATT'))
    if HOY_BATTERY_NORMAL_WATT[i] > HOY_MAX_WATT[i]:
        HOY_BATTERY_NORMAL_WATT[i] = HOY_MAX_WATT[i]
    HOY_BATTERY_REDUCE_WATT.append(config.getint('INVERTER_' + str(i + 1), 'HOY_BATTERY_REDUCE_WATT'))
    HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V.append(config.getfloat('INVERTER_' + str(i + 1), 'HOY_BATTERY_THRESHOLD_ON_LIMIT_IN_V'))
    HOY_COMPENSATE_WATT_FACTOR.append(config.getfloat('INVERTER_' + str(i + 1), 'HOY_COMPENSATE_WATT_FACTOR'))
    HOY_BATTERY_IGNORE_PANELS.append(config.get('INVERTER_' + str(i + 1), 'HOY_BATTERY_IGNORE_PANELS'))
    HOY_BATTERY_PRIORITY.append(config.getint('INVERTER_' + str(i + 1), 'HOY_BATTERY_PRIORITY'))
    HOY_PANEL_VOLTAGE_LIST.append([])
SLOW_APPROX_LIMIT = CastToInt(GetMaxWattFromAllInverters() * config.getint('COMMON', 'SLOW_APPROX_LIMIT_IN_PERCENT') / 100)

try:
    logger.info("---Init---")
    newLimitSetpoint = 0
    if USE_AHOY:
        CheckAhoyVersion()
        AHOY_FACTOR = GetAhoyLimitFactor()
    if GetHoymilesAvailable():
        for i in range(INVERTER_COUNT):
            SetHoymilesPowerStatus(i, True)
        SetLimit(GetMinWattFromAllInverters())
        GetHoymilesActualPower()
        GetCheckBattery()
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
            for x in range(CastToInt(LOOP_INTERVAL_IN_SECONDS / POLL_INTERVAL_IN_SECONDS)):
                powermeterWatts = GetPowermeterWatts()
                if powermeterWatts > POWERMETER_MAX_POINT:
                    if ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT > 0:
                        newLimitSetpoint = CastToInt(GetMaxInverterWattFromAllInverters() * ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT / 100)
                        if (newLimitSetpoint <= PreviousLimitSetpoint) and (ON_GRID_USAGE_JUMP_TO_LIMIT_PERCENT != 100):
                            newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts - POWERMETER_TARGET_POINT
                    else:
                        newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts - POWERMETER_TARGET_POINT
                    newLimitSetpoint = ApplyLimitsToSetpoint(newLimitSetpoint)
                    SetLimit(newLimitSetpoint)
                    if CastToInt(LOOP_INTERVAL_IN_SECONDS) - SET_LIMIT_DELAY_IN_SECONDS - x * POLL_INTERVAL_IN_SECONDS <= 0:
                        break
                    else:
                        time.sleep(CastToInt(LOOP_INTERVAL_IN_SECONDS) - SET_LIMIT_DELAY_IN_SECONDS - x * POLL_INTERVAL_IN_SECONDS)
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
