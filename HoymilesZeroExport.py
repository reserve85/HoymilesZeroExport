import requests, time
from requests.auth import HTTPBasicAuth
import os
import logging

ahoyIP = '192.168.10.57' # in settings/inverter set interval to 6 seconds!
tasmotaIP = '192.168.10.90'
powermeterTargetPoint = int(-75) # this is the target power for powermeter in watts
powermeterTolerance = int(25) # this is the tolerance (pos and neg) around the target point. in this range no adjustment will be set
hoymilesInverterID = int(0) # number of inverter in Ahoy-Setup
hoymilesMaxWatt = int(1500) # maximum limit in watts (100%)
hoymilesMinWatt = int(hoymilesMaxWatt * 0.05) # minimum limit in watts, e.g. 5%
slowApproximationLimit = int(hoymilesMaxWatt * 0.2) # max difference between SetpointLimit change to Approximate the power to new setpoint
loopIntervalInSeconds = int(20) # interval time for setting limit to hoymiles
setLimitDelay = int(5) # delay time after sending limit to Hoymiles
pollInterval = int(1) # polling interval for powermeter (must be < loopIntervalInSeconds)
jumpToMaxlimitOnGridUsage = bool(True) # when powermeter > 0: (true): always jump to maxLimit of inverter; (false): increase limit based on previous limit

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def SetLimit(pHoymilesInverterID, pLimit):
    url = f"http://{ahoyIP}/api/ctrl"
    data = f'''{{"id": {pHoymilesInverterID}, "cmd": "limit_nonpersistent_absolute", "val": {pLimit}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    logging.info("setting new limit to %s %s",int(pLimit)," Watt")
    try:
        requests.post(url, data=data, headers=headers)
    except:
        logging.info("error: %s is not reachable!", url)
    time.sleep(setLimitDelay)

def GetHoymilesAvailable():
    url = f'http://{ahoyIP}/api/index'
    try:
        ParsedData = requests.get(url).json()
    except:
        logging.info("error: %s is not reachable!", url)
        return False
    if ParsedData == None:
        logging.info("Error: ParsedData is empty (in function GetHoymilesAvailable)")
        return False
    Reachable = bool(ParsedData["inverter"][0]["is_avail"])
    logging.info("HM reachable: %s",Reachable)
    return Reachable

def GetHoymilesActualPower():
    url = f'http://{ahoyIP}/api/record/live'
    try:
        ParsedData = requests.get(url).json()
    except:
        logging.info("error: %s is not reachable!", url)
        return int(0)
    if ParsedData == None:
        logging.info("Error: ParsedData is empty (in function GetHoymilesActualPower)")
        return int(0)
    ActualPower = int(float(next(item for item in ParsedData['inverter'][0] if item['fld'] == 'P_AC')['val']))
    logging.info("HM power: %s %s",ActualPower, " Watt")
    return int(ActualPower)

def GetPowermeterWatts():
    url = f'http://{tasmotaIP}/cm?cmnd=status%2010'
    try:
        ParsedData = requests.get(url).json()
    except:
        logging.info("error: %s is not reachable!", url)
        return int(0)
    if ParsedData == None:
        logging.info("Error: ParsedData is empty (in function GetPowermeterWatts)")
        return int(0)
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
SetLimit(hoymilesInverterID, newLimitSetpoint)
time.sleep(loopIntervalInSeconds - setLimitDelay)

while True:
    try:
        PreviousLimitSetpoint = newLimitSetpoint
        if GetHoymilesAvailable():
            for x in range(int(loopIntervalInSeconds / pollInterval)):
                powermeterWatts = GetPowermeterWatts()
                if powermeterWatts > 0:
                    if jumpToMaxlimitOnGridUsage:
                        newLimitSetpoint = hoymilesMaxWatt
                    else:
                        newLimitSetpoint = PreviousLimitSetpoint + powermeterWatts + abs(powermeterTargetPoint)
                    newLimitSetpoint = ApplyLimitsToSetpoint(newLimitSetpoint)
                    SetLimit(hoymilesInverterID, newLimitSetpoint)
                    if int(loopIntervalInSeconds) - setLimitDelay - x * pollInterval <= 0:
                        break
                    else:
                        time.sleep(int(loopIntervalInSeconds) - setLimitDelay - x * pollInterval)
                    break
                else:
                    time.sleep(pollInterval)
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
                SetLimit(hoymilesInverterID, newLimitSetpoint)
        else:
            time.sleep(loopIntervalInSeconds)

    except Exception as e:
        if hasattr(e, 'message'):
            print(e.message)
        else:
            print(e)
        time.sleep(loopIntervalInSeconds)
