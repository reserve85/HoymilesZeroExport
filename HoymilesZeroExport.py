__author__ = "reserve85"
__version__ = "1.9"

import requests, time
from requests.auth import HTTPBasicAuth
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from configparser import ConfigParser
from pathlib import Path
import datetime as dt

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
    def GetNewLogFilename(self):
        now = dt.datetime.now()
        return Path.joinpath(Path.joinpath(Path(__file__).parent.resolve(), 'log'),''+now.strftime("%Y%m%d_%H%M%S")+'.log')
    if not os.path.exists(Path.joinpath(Path(__file__).parent.resolve(), 'log')):
        os.makedirs(Path.joinpath(Path(__file__).parent.resolve(), 'log'))
    rotating_file_handler = TimedRotatingFileHandler(
        filename=Path.joinpath(Path.joinpath(Path(__file__).parent.resolve(), 'log'),'today.log'),
        when='midnight',
        interval=2,
        backupCount=LOG_BACKUP_COUNT)
    rotating_file_handler.rotation_filename = GetNewLogFilename
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)-8s %(message)s')
    rotating_file_handler.setFormatter(formatter)
    logger.addHandler(rotating_file_handler)

logger.info('Log write to file: %s', ENABLE_LOG_TO_FILE)

def SetLimitOpenDTU(pInverterId, pLimit):
    if INVERTER_ID[pInverterId] != 0:
        time.sleep(SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER)
    relLimit = int(pLimit / HOY_MAX_WATT * 100)
    url=f"http://{OPENDTU_IP}/api/limit/config"
    data = f'''data={{"serial":"{SERIAL_NUMBER[pInverterId]}", "limit_type":1, "limit_value":{relLimit}}}'''
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    logger.info("Inverter %s: setting new limit from %s Watt to %s Watt",int(pInverterId),int(CURRENT_LIMIT[pInverterId]),int(pLimit))
    requests.post(url, data=data, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), headers=headers)
    CURRENT_LIMIT[pInverterId] = pLimit

def SetLimitAhoy(pInverterId, pLimit):
    if INVERTER_ID[pInverterId] != 0:
        time.sleep(SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER)
    url = f"http://{AHOY_IP}/api/ctrl"
    data = f'''{{"id": {pInverterId}, "cmd": "limit_nonpersistent_absolute", "val": {pLimit}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    logger.info("Inverter %s: setting new limit from %s Watt to %s Watt",int(pInverterId),int(CURRENT_LIMIT[pInverterId]),int(pLimit))
    requests.post(url, data=data, headers=headers)
    CURRENT_LIMIT[pInverterId] = pLimit

def SetLimit(pLimit):
    try:
        logger.info("setting new limit to %s Watt",int(pLimit))
        for i in range(INVERTER_COUNT):
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
    except:
        logger.info("Exception at SetLimit")
        raise

def GetHoymilesAvailableOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url).json()
    Reachable = bool(ParsedData["inverters"][pInverterId]["reachable"])
    logger.info("Inverter %s reachable: %s",int(pInverterId),Reachable)
    return Reachable

def GetHoymilesAvailableAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/index'
    ParsedData = requests.get(url).json()
    Reachable = bool(ParsedData["inverter"][pInverterId]["is_avail"])
    logger.info("Inverter %s reachable: %s",int(pInverterId),Reachable)
    return Reachable

def GetHoymilesAvailable():
    try:
        GetHoymilesAvailable = True
        if USE_AHOY:
            for i in range(INVERTER_COUNT):
                GetHoymilesAvailable = GetHoymilesAvailable and GetHoymilesAvailableAhoy(i)
            return GetHoymilesAvailable
        elif USE_OPENDTU:
            for i in range(INVERTER_COUNT):
                GetHoymilesAvailable = GetHoymilesAvailable and GetHoymilesAvailableOpenDTU(i)
            return GetHoymilesAvailable
        else:
            raise Exception("Error: DTU Type not defined")
    except:
        logger.info("Exception at GetHoymilesAvailable, Inverter not available")
        raise

def GetHoymilesActualPowerOpenDTU(pInverterId):
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url).json()
    ActualPower = int(ParsedData['inverters'][pInverterId]['AC']['0']['Power']['v'])
    logger.info("Inverter %s power producing: %s %s",int(pInverterId),ActualPower," Watt")
    return int(ActualPower)

def GetHoymilesActualPowerAhoy(pInverterId):
    url = f'http://{AHOY_IP}/api/record/live'
    ParsedData = requests.get(url).json()
    ActualPower = int(float(next(item for item in ParsedData['inverter'][pInverterId] if item['fld'] == 'P_AC')['val']))
    logger.info("Inverter %s power producing: %s %s",int(pInverterId),ActualPower," Watt")
    return int(ActualPower)

def GetHoymilesActualPower():
    try:
        ActualPower = 0
        if USE_AHOY:
            for i in range(INVERTER_COUNT):
                ActualPower = ActualPower + GetHoymilesActualPowerAhoy(i)
            return ActualPower
        elif USE_OPENDTU:
            for i in range(INVERTER_COUNT):
                ActualPower = ActualPower + GetHoymilesActualPowerOpenDTU(i)
            return ActualPower
        else:
            raise Exception("Error: DTU Type not defined")
    except:
        logger.info("Exception at GetHoymilesActualPower")
        raise

def GetPowermeterWattsTasmota():
    url = f'http://{TASMOTA_IP}/cm?cmnd=status%2010'
    ParsedData = requests.get(url).json()
    if not TASMOTA_JSON_POWER_CALCULATE:
        Watts = int(ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_MQTT_LABEL])
    else:
        input = ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_INPUT_MQTT_LABEL]
        ouput = ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_OUTPUT_MQTT_LABEL]
        Watts = int(input - ouput)
    logger.info("powermeter: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShelly3EM():
    url = f'http://{SHELLY_IP}/status'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData['total_power'])
    logger.info("powermeter: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWattsShrdzm():
    url = f'http://{SHRDZM_IP}/getLastData?user={SHRDZM_USER}&password={SHRDZM_PASS}'
    ParsedData = requests.get(url).json()
    Watts = int(int(ParsedData['1.7.0']) - int(ParsedData['2.7.0']))
    logger.info("powermeter: %s %s",Watts," Watt")
    return int(Watts)

def GetPowermeterWatts():
    try:
        if USE_SHELLY_3EM:
            return GetPowermeterWattsShelly3EM()
        elif USE_TASMOTA:
            return GetPowermeterWattsTasmota()
        elif USE_SHRDZM:
            return GetPowermeterWattsShrdzm()
        else:
            raise Exception("Error: no powermeter defined!")
    except:
        logger.info("Exception at GetPowermeterWatts")
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
        maxWatt = maxWatt + HOY_MAX_WATT[i]
    return maxWatt

def GetMinWattFromAllInverters():
    minWatt = 0
    for i in range(INVERTER_COUNT):
        minWatt = minWatt + HOY_MIN_WATT[i]
    return minWatt

# ----- START -----

logger.info("Author: %s / Script Version: %s",__author__, __version__)

# read config:
config = ConfigParser()
logger.info("read config file: " + str(Path.joinpath(Path(__file__).parent.resolve(), "HoymilesZeroExport_Config.ini")))
config.read(str(Path.joinpath(Path(__file__).parent.resolve(), "HoymilesZeroExport_Config.ini")))
VERSION = config.get('VERSION', 'VERSION')
logger.info("Config file V %s", VERSION)
USE_AHOY = config.getboolean('SELECT_DTU', 'USE_AHOY')
USE_OPENDTU = config.getboolean('SELECT_DTU', 'USE_OPENDTU')
USE_TASMOTA = config.getboolean('SELECT_POWERMETER', 'USE_TASMOTA')
USE_SHELLY_3EM = config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_3EM')
USE_SHRDZM = config.getboolean('SELECT_POWERMETER', 'USE_SHRDZM')
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
INVERTER_COUNT = config.getint('COMMON', 'INVERTER_COUNT')
LOOP_INTERVAL_IN_SECONDS = config.getint('COMMON', 'LOOP_INTERVAL_IN_SECONDS')
SET_LIMIT_DELAY_IN_SECONDS = config.getint('COMMON', 'SET_LIMIT_DELAY_IN_SECONDS')
SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER = config.getint('COMMON', 'SET_LIMIT_DELAY_IN_SECONDS_MULTIPLE_INVERTER')
POLL_INTERVAL_IN_SECONDS = config.getint('COMMON', 'POLL_INTERVAL_IN_SECONDS')
JUMP_TO_MAX_LIMIT_ON_GRID_USAGE = config.getboolean('COMMON', 'JUMP_TO_MAX_LIMIT_ON_GRID_USAGE')
MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER = config.getint('COMMON', 'MAX_DIFFERENCE_BETWEEN_LIMIT_AND_OUTPUTPOWER')
POWERMETER_TARGET_POINT = config.getint('CONTROL', 'POWERMETER_TARGET_POINT')
POWERMETER_TOLERANCE = config.getint('CONTROL', 'POWERMETER_TOLERANCE')
POWERMETER_MAX_POINT = config.getint('CONTROL', 'POWERMETER_MAX_POINT')
INVERTER_ID = []
SERIAL_NUMBER = []
HOY_MAX_WATT = []
HOY_MIN_WATT = []
CURRENT_LIMIT = []
for i in range(INVERTER_COUNT):
    INVERTER_ID.append(i)
    SERIAL_NUMBER.append(config.get('INVERTER_' + str(i + 1), 'SERIAL_NUMBER'))
    HOY_MAX_WATT.append(config.getint('INVERTER_' + str(i + 1), 'HOY_MAX_WATT'))
    HOY_MIN_WATT.append(int(HOY_MAX_WATT[i] * config.getint('INVERTER_' + str(i + 1), 'HOY_MIN_WATT_IN_PERCENT') / 100))
    CURRENT_LIMIT.append(int(0))
SLOW_APPROX_LIMIT = int(GetMaxWattFromAllInverters() * config.getint('COMMON', 'SLOW_APPROX_LIMIT_IN_PERCENT') / 100)

try:
    newLimitSetpoint = GetMaxWattFromAllInverters()
    if GetHoymilesAvailable():
        SetLimit(newLimitSetpoint)
    time.sleep(SET_LIMIT_DELAY_IN_SECONDS)
except Exception as e:
    if hasattr(e, 'message'):
        logger.error(e.message)
    else:
        logger.error(e)
    time.sleep(LOOP_INTERVAL_IN_SECONDS)
    
while True:
    try:
        PreviousLimitSetpoint = newLimitSetpoint
        if GetHoymilesAvailable():
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
                    LimitDifference = abs(PreviousLimitSetpoint - newLimitSetpoint)
                    newLimitSetpoint = newLimitSetpoint + (LimitDifference / 4)
                    if newLimitSetpoint > hoymilesActualPower:
                        newLimitSetpoint = hoymilesActualPower
                    logger.info("overproducing: reduce limit based on actual power")
                else:
                    newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts - POWERMETER_TARGET_POINT
                    # check if it is necessary to approximate to the setpoint with some more passes. this reduce overshoot
                    LimitDifference = abs(PreviousLimitSetpoint - newLimitSetpoint)
                    if LimitDifference > SLOW_APPROX_LIMIT:
                        logger.info("overproducing: reduce limit based on previous limit setpoint by approximation")
                        newLimitSetpoint = newLimitSetpoint + (LimitDifference / 4)
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
            time.sleep(LOOP_INTERVAL_IN_SECONDS)

    except Exception as e:
        if hasattr(e, 'message'):
            logger.error(e.message)
        else:
            logger.error(e)
        time.sleep(LOOP_INTERVAL_IN_SECONDS)
