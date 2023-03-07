__author__ = "reserve85"
__version__ = "1.4"

import requests, time
from requests.auth import HTTPBasicAuth
import os
import logging
from configparser import ConfigParser
from pathlib import Path

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def SetLimitOpenDTU(pLimit):
    url=f"http://{OPENDTU_IP}/api/limit/config"
    data = f'''data={{"serial":"{OPENDTU_HOY_SERIAL_NR}", "limit_type":1, "limit_value":{pLimit}}}'''
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    logging.info("setting new limit to %s %s",int(pLimit)," Watt")
    requests.post(url, data=data, auth=HTTPBasicAuth(OPENDTU_USER, OPENDTU_PASS), headers=headers)
    time.sleep(SET_LIMIT_DELAY_IN_SECONDS)

def SetLimitAhoy(pLimit):
    url = f"http://{AHOY_IP}/api/ctrl"
    data = f'''{{"id": {AHOY_HOY_INVERTER_ID}, "cmd": "limit_nonpersistent_absolute", "val": {pLimit}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    logging.info("setting new limit to %s %s",int(pLimit)," Watt")
    requests.post(url, data=data, headers=headers)
    time.sleep(SET_LIMIT_DELAY_IN_SECONDS)

def SetLimit(pLimit):
    if USE_AHOY:
        SetLimitAhoy(pLimit)
    elif USE_OPENDTU:
        SetLimitOpenDTU(pLimit)
    else:
        raise Exception("Error: DTU Type not defined")

def GetHoymilesAvailableOpenDTU():
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url).json()
    Reachable = bool(ParsedData["inverters"][0]["reachable"])
    logging.info("HM reachable: %s",Reachable)
    return Reachable

def GetHoymilesAvailableAhoy():
    url = f'http://{AHOY_IP}/api/index'
    ParsedData = requests.get(url).json()
    Reachable = bool(ParsedData["inverter"][0]["is_avail"])
    logging.info("HM reachable: %s",Reachable)
    return Reachable

def GetHoymilesAvailable():
    if USE_AHOY:
        return GetHoymilesAvailableAhoy()
    elif USE_OPENDTU:
        return GetHoymilesAvailableOpenDTU()
    else:
        raise Exception("Error: DTU Type not defined")

def GetHoymilesActualPowerOpenDTU():
    url = f'http://{OPENDTU_IP}/api/livedata/status/inverters'
    ParsedData = requests.get(url).json()
    ActualPower = int(ParsedData['inverters'][0]['0']['Power']['v'])
    logging.info("HM power: %s %s",ActualPower, " Watt")
    return int(ActualPower)

def GetHoymilesActualPowerAhoy():
    url = f'http://{AHOY_IP}/api/record/live'
    ParsedData = requests.get(url).json()
    ActualPower = int(float(next(item for item in ParsedData['inverter'][0] if item['fld'] == 'P_AC')['val']))
    logging.info("HM power: %s %s",ActualPower, " Watt")
    return int(ActualPower)

def GetHoymilesActualPower():
    if USE_AHOY:
        return GetHoymilesActualPowerAhoy()
    elif USE_OPENDTU:
        return GetHoymilesActualPowerOpenDTU()
    else:
        raise Exception("Error: DTU Type not defined")

def GetPowermeterWattsTasmota():
    url = f'http://{TASMOTA_IP}/cm?cmnd=status%2010'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData[TASMOTA_JSON_STATUS][TASMOTA_JSON_PAYLOAD_MQTT_PREFIX][TASMOTA_JSON_POWER_MQTT_LABEL])
    logging.info("powermeter: %s %s",Watts, " Watt")
    return int(Watts)

def GetPowermeterWattsShelly3EM():
    url = f'http://{SHELLY_IP}/status'
    ParsedData = requests.get(url).json()
    Watts = int(ParsedData['total_power'])
    logging.info("powermeter: %s %s",Watts, " Watt")
    return int(Watts)

def GetPowermeterWatts():
    if USE_SHELLY_3EM:
        return GetPowermeterWattsShelly3EM()
    elif USE_TASMOTA:
        return GetPowermeterWattsTasmota()
    else:
        raise Exception("Error: no powermeter defined!")

def ApplyLimitsToSetpoint(pSetpoint):
    if pSetpoint > HOY_MAX_WATT:
        pSetpoint = HOY_MAX_WATT
    if pSetpoint < HOY_MIN_WATT:
        pSetpoint = HOY_MIN_WATT
    return pSetpoint

# read config:
config = ConfigParser()
logging.info("read config file: " + str(Path.joinpath(Path(__file__).parent.resolve(), "HoymilesZeroExport_Config.ini")))
config.read(str(Path.joinpath(Path(__file__).parent.resolve(), "HoymilesZeroExport_Config.ini")))
USE_AHOY = config.getboolean('SELECT_DTU', 'USE_AHOY')
USE_OPENDTU = config.getboolean('SELECT_DTU', 'USE_OPENDTU')
USE_TASMOTA = config.getboolean('SELECT_POWERMETER', 'USE_TASMOTA')
USE_SHELLY_3EM = config.getboolean('SELECT_POWERMETER', 'USE_SHELLY_3EM')
AHOY_IP = config.get('AHOY_DTU', 'AHOY_IP')
AHOY_HOY_INVERTER_ID = config.getint('AHOY_DTU', 'AHOY_HOY_INVERTER_ID')
OPENDTU_IP = config.get('OPEN_DTU', 'OPENDTU_IP')
OPENDTU_USER = config.get('OPEN_DTU', 'OPENDTU_USER')
OPENDTU_PASS = config.get('OPEN_DTU', 'OPENDTU_PASS')
OPENDTU_HOY_SERIAL_NR = config.get('OPEN_DTU', 'OPENDTU_HOY_SERIAL_NR')
TASMOTA_IP = config.get('TASMOTA', 'TASMOTA_IP')
TASMOTA_JSON_STATUS = config.get('TASMOTA', 'TASMOTA_JSON_STATUS')
TASMOTA_JSON_PAYLOAD_MQTT_PREFIX = config.get('TASMOTA', 'TASMOTA_JSON_PAYLOAD_MQTT_PREFIX')
TASMOTA_JSON_POWER_MQTT_LABEL = config.get('TASMOTA', 'TASMOTA_JSON_POWER_MQTT_LABEL')
SHELLY_IP = config.get('SHELLY_3EM', 'SHELLY_IP')
HOY_MAX_WATT = config.getint('COMMON', 'HOY_MAX_WATT')
HOY_MIN_WATT = int(HOY_MAX_WATT * config.getint('COMMON', 'HOY_MIN_WATT_IN_PERCENT') / 100)
SLOW_APPROX_LIMIT = int(HOY_MAX_WATT * config.getint('COMMON', 'SLOW_APPROX_LIMIT_IN_PERCENT') / 100)
LOOP_INTERVAL_IN_SECONDS = config.getint('COMMON', 'LOOP_INTERVAL_IN_SECONDS')
SET_LIMIT_DELAY_IN_SECONDS = config.getint('COMMON', 'SET_LIMIT_DELAY_IN_SECONDS')
POLL_INTERVAL_IN_SECONDS = config.getint('COMMON', 'POLL_INTERVAL_IN_SECONDS')
JUMP_TO_MAX_LIMIT_ON_GRID_USAGE = config.getboolean('COMMON', 'JUMP_TO_MAX_LIMIT_ON_GRID_USAGE')
POWERMETER_TARGET_POINT = config.getint('CONTROL', 'POWERMETER_TARGET_POINT')
POWERMETER_TOLERANCE = config.getint('CONTROL', 'POWERMETER_TOLERANCE')
POWERMETER_MAX_POINT = config.getint('CONTROL', 'POWERMETER_MAX_POINT')

newLimitSetpoint = HOY_MAX_WATT
SetLimit(newLimitSetpoint)
time.sleep(SET_LIMIT_DELAY_IN_SECONDS)

while True:
    try:
        PreviousLimitSetpoint = newLimitSetpoint
        if GetHoymilesAvailable():
            for x in range(int(LOOP_INTERVAL_IN_SECONDS / POLL_INTERVAL_IN_SECONDS)):
                powermeterWatts = GetPowermeterWatts()
                if powermeterWatts > POWERMETER_MAX_POINT:
                    if JUMP_TO_MAX_LIMIT_ON_GRID_USAGE:
                        newLimitSetpoint = HOY_MAX_WATT
                    else:
                        newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts -POWERMETER_TARGET_POINT
                    newLimitSetpoint = ApplyLimitsToSetpoint(newLimitSetpoint)
                    SetLimit(newLimitSetpoint)
                    if int(LOOP_INTERVAL_IN_SECONDS) - SET_LIMIT_DELAY_IN_SECONDS - x * POLL_INTERVAL_IN_SECONDS <= 0:
                        break
                    else:
                        time.sleep(int(LOOP_INTERVAL_IN_SECONDS) - SET_LIMIT_DELAY_IN_SECONDS - x * POLL_INTERVAL_IN_SECONDS)
                    break
                else:
                    time.sleep(POLL_INTERVAL_IN_SECONDS)
            if powermeterWatts > POWERMETER_MAX_POINT:
                continue

            # producing too much power: reduce limit
            if powermeterWatts < (POWERMETER_TARGET_POINT - POWERMETER_TOLERANCE):
                if PreviousLimitSetpoint >= HOY_MAX_WATT:
                    hoymilesActualPower = GetHoymilesActualPower()
                    newLimitSetpoint = hoymilesActualPower + powermeterWatts - POWERMETER_TARGET_POINT
                    LimitDifference = abs(PreviousLimitSetpoint - newLimitSetpoint)
                    newLimitSetpoint = newLimitSetpoint + (LimitDifference / 4)
                    if newLimitSetpoint > hoymilesActualPower:
                        newLimitSetpoint = hoymilesActualPower
                    logging.info("overproducing: reduce limit based on actual power")
                else:
                    newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts - POWERMETER_TARGET_POINT
                    # check if it is necessary to approximate to the setpoint with some more passes. this reduce overshoot
                    LimitDifference = abs(PreviousLimitSetpoint - newLimitSetpoint)
                    if LimitDifference > SLOW_APPROX_LIMIT:
                        logging.info("overproducing: reduce limit based on previous limit setpoint by approximation")
                        newLimitSetpoint = newLimitSetpoint + (LimitDifference / 4)
                    else:
                        logging.info("overproducing: reduce limit based on previous limit setpoint")

            # producing too little power: increase limit
            elif powermeterWatts > (POWERMETER_TARGET_POINT + POWERMETER_TOLERANCE):
                if PreviousLimitSetpoint < HOY_MAX_WATT:
                    newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts - POWERMETER_TARGET_POINT
                    logging.info("Not enough energy producing: increasing limit")
                else:
                    logging.info("Not enough energy producing: limit already at maximum")

            # check for upper and lower limits
            newLimitSetpoint = ApplyLimitsToSetpoint(newLimitSetpoint)
            # set new limit to inverter
            if newLimitSetpoint != PreviousLimitSetpoint:
                SetLimit(newLimitSetpoint)
        else:
            time.sleep(LOOP_INTERVAL_IN_SECONDS)

    except Exception as e:
        if hasattr(e, 'message'):
            print(e.message)
        else:
            print(e)
        time.sleep(LOOP_INTERVAL_IN_SECONDS)
