import requests, time
from requests.auth import HTTPBasicAuth
import os
import logging

ahoyIP = '192.168.10.57'
tasmotaIP = '192.168.10.90'
powermeterTargetPoint = int(-75) # this is the target power for powermeter in watts
powermeterTolerance = int(25) # this is the tolerance (pos and neg) around the target point. in this range no adjustment will be set
hoymilesInverterID = int(0) # number of inverter in Ahoy-Setup
hoymilesMaxWatt = int(1500) # maximum limit in watts (100%)
hoymilesMinWatt = int(hoymilesMaxWatt * 0.05) # minimum limit in watts, e.g. 5%
LoopIntervalInSeconds = int(20) # time for loop interval
slowApproximationLimit = int(hoymilesMaxWatt * 0.2) # max difference between SetpointLimit change to Approximate the power to new setpoint
SetLimitDelay = int(5) # min delay time after sending limit

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def setLimit(pHoymilesInverterID, pLimit):
    url = f"http://{ahoyIP}/api/ctrl"
    data = f'''{{"id": {pHoymilesInverterID}, "cmd": "limit_nonpersistent_absolute", "val": {pLimit}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    logging.info("setting new limit to %s %s",int(pLimit)," Watt")
    requests.post(url, data=data, headers=headers)
    time.sleep(SetLimitDelay)

def GetHoymilesAvailable():
    ParsedData = requests.get(url = f'http://{ahoyIP}/api/index').json()
    Reachable = bool(ParsedData["inverter"][0]["is_avail"])
    logging.info("HM reachable: %s",Reachable)
    return Reachable

def GetHoymilesActualPower():
    ParsedData = requests.get(url = f'http://{ahoyIP}/api/record/live').json()
    ActualPower = int(float(next(item for item in ParsedData['inverter'][0] if item['fld'] == 'P_AC')['val']))
    logging.info("HM power: %s %s",ActualPower, " Watt")
    return int(ActualPower)

def GetPowermeterWatts():
    ParsedData = requests.get(url = f'http://{tasmotaIP}/cm?cmnd=status%2010').json()
    Watts = int(ParsedData["StatusSNS"]["SML"]["curr_w"])
    logging.info("powermeter: %s %s",Watts, " Watt")
    return int(Watts)

def ApplyLimitsToSetpoint(pSetpoint):
    if pSetpoint > hoymilesMaxWatt:
        pSetpoint = hoymilesMaxWatt
    if pSetpoint < hoymilesMinWatt:
        pSetpoint = hoymilesMinWatt
    return pSetpoint

newLimitSetpoint = hoymilesMaxWatt
setLimit(hoymilesInverterID, newLimitSetpoint)
time.sleep(LoopIntervalInSeconds - SetLimitDelay)

while True:
    try:
        PreviousLimitSetpoint = newLimitSetpoint
        if GetHoymilesAvailable():
            for x in range(LoopIntervalInSeconds):
                powermeterWatts = GetPowermeterWatts()
                if powermeterWatts > 0:
                    newLimitSetpoint = hoymilesMaxWatt
                    setLimit(hoymilesInverterID, newLimitSetpoint)
                    if LoopIntervalInSeconds - SetLimitDelay - x <= 0:
                        break
                    else:
                        time.sleep(LoopIntervalInSeconds - SetLimitDelay - x)
                    break
                else:
                    time.sleep(1)
            if powermeterWatts > 0:
                continue

            # producing too much power: reduce limit
            if powermeterWatts < (powermeterTargetPoint - powermeterTolerance):
                if PreviousLimitSetpoint >= hoymilesMaxWatt:
                    hoymilesActualPower = GetHoymilesActualPower()
                    CalculatedLimit = hoymilesActualPower - abs(powermeterWatts) + abs(powermeterTargetPoint)
                    newLimitSetpoint = CalculatedLimit + abs((PreviousLimitSetpoint - CalculatedLimit) / 4)
                    if newLimitSetpoint > hoymilesActualPower:
                        newLimitSetpoint = hoymilesActualPower
                    logging.info("overproducing: reduce limit based on actual power")
                else:
                    newLimitSetpoint = PreviousLimitSetpoint - abs(powermeterWatts) + abs(powermeterTargetPoint)
                    # check if it is necessary to approximate to the setpoint with some more passes. this reduce overshoot
                    LimitDifference = abs(PreviousLimitSetpoint - newLimitSetpoint)
                    if LimitDifference > slowApproximationLimit:
                        logging.info("overproducing: reduce limit based on previous limit setpoint by approximation")
                        newLimitSetpoint = newLimitSetpoint + (LimitDifference / 4)
                    else:
                        logging.info("overproducing: reduce limit based on previous limit setpoint")

            # producing too little power: increase limit
            elif powermeterWatts > (powermeterTargetPoint + powermeterTolerance):
                if PreviousLimitSetpoint < hoymilesMaxWatt:
                    newLimitSetpoint = PreviousLimitSetpoint - abs(powermeterWatts) + abs(powermeterTargetPoint)
                    logging.info("Not enough energy producing: increasing limit")
                else:
                    logging.info("Not enough energy producing: limit already at maximum")

            # check for upper and lower limits
            newLimitSetpoint = ApplyLimitsToSetpoint(newLimitSetpoint)
            # set new limit to inverter
            if newLimitSetpoint != PreviousLimitSetpoint:
                setLimit(hoymilesInverterID, newLimitSetpoint)
        else:
            time.sleep(LoopIntervalInSeconds)

    except TypeError as e:
        logging.error(e)
        time.sleep(LoopIntervalInSeconds)
