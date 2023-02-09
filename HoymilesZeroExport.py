import requests, time
from requests.auth import HTTPBasicAuth
import os
import logging

ahoyIP = '192.168.10.57'
tasmotaIP = '192.168.10.90'

powermeterTargetPoint = int(-75) # this is the target power for powermeter in watts
powermeterTolerance = int(30) # this is the tolerance (pos and neg) around the target point. in this range no adjustment will be set
hoymilesInverterID = int(0) # number of inverter in Ahoy-Setup
hoymilesMaxWatt = int(1500) # maximum limit in watts (100%)
hoymilesMinWatt = int(hoymilesMaxWatt * 0.05) # minimum limit in watts, e.g. 5%
hoymilesBigJumpPowerOffset = int(2.5 * powermeterTargetPoint) # Additional offset used for calculation to jump from max Limit to calculated limit
LoopIntervalInSeconds = int(20) # time for loop interval
SetLimitDelay = int(5) # min delay time after sending limit

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def setLimit(hoymilesInverterID, Limit):
    url = f"http://{ahoyIP}/api/ctrl"
    data = f'''{{"id": {hoymilesInverterID}, "cmd": "limit_nonpersistent_absolute", "val": {Limit}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    logging.info("setting new limit to %s %s",Limit," Watt")
    requests.post(url, data=data, headers=headers)
    time.sleep(SetLimitDelay)

# Init
newLimitSetpoint = hoymilesMaxWatt
setLimit(hoymilesInverterID, newLimitSetpoint)
time.sleep(LoopIntervalInSeconds - SetLimitDelay)

while True:
    try:
        oldLimitSetpoint = newLimitSetpoint
        ParsedData = requests.get(url = f'http://{ahoyIP}/api/index').json()
        hoymilesIsReachable = bool(ParsedData["inverter"][0]["is_avail"])
        logging.info("HM reachable: %s",hoymilesIsReachable)

        if hoymilesIsReachable:
            # check all the time if powermeterWatts > 0...
            for x in range(LoopIntervalInSeconds):
                ParsedData = requests.get(url = f'http://{tasmotaIP}/cm?cmnd=status%2010').json()
                powermeterWatts = int(ParsedData["StatusSNS"]["SML"]["curr_w"])
                logging.info("powermeter: %s %s",powermeterWatts, " Watt")
                if powermeterWatts > 0:
                    newLimitSetpoint = hoymilesMaxWatt
                    setLimit(hoymilesInverterID, newLimitSetpoint)
                    lclsleeptime = LoopIntervalInSeconds - SetLimitDelay - x
                    if lclsleeptime <= 0:
                        break
                    else:
                        time.sleep(lclsleeptime)
                    break
                time.sleep(1)
            if powermeterWatts > 0:
                continue

            # producing too much power: reduce limit
            if powermeterWatts < (powermeterTargetPoint - powermeterTolerance):
                if newLimitSetpoint >= hoymilesMaxWatt:
                    ParsedData = requests.get(url = f'http://{ahoyIP}/api/record/live').json()
                    hoymilesActualPower = int(float(next(item for item in ParsedData['inverter'][0] if item['fld'] == 'P_AC')['val']))
                    logging.info("HM power: %s %s",hoymilesActualPower, " Watt")
                    newLimitSetpoint = hoymilesActualPower - abs(powermeterWatts) + abs(hoymilesBigJumpPowerOffset) # big jump to setpoint
                else:
                    newLimitSetpoint = newLimitSetpoint - abs(powermeterWatts) + abs(powermeterTargetPoint) # jump to setpoint
                logging.info("Too much energy producing: reducing limit")

            # producing too little power: increase limit
            elif powermeterWatts > (powermeterTargetPoint + powermeterTolerance):
                if newLimitSetpoint < hoymilesMaxWatt:
                    newLimitSetpoint = newLimitSetpoint - abs(powermeterWatts) + abs(powermeterTargetPoint)
                    logging.info("Not enough energy producing: increasing limit")
                else:
                    logging.info("Not enough energy producing: limit already at maximum")

            # check for upper and lower limits
            if newLimitSetpoint > hoymilesMaxWatt:
                newLimitSetpoint = hoymilesMaxWatt
            if newLimitSetpoint < hoymilesMinWatt:
                newLimitSetpoint = hoymilesMinWatt

            # set new limit to inverter
            if oldLimitSetpoint != newLimitSetpoint:
                setLimit(hoymilesInverterID, newLimitSetpoint)
        else:
            time.sleep(LoopIntervalInSeconds)

    except TypeError as e:
        logging.error(e)
        time.sleep(LoopIntervalInSeconds)
