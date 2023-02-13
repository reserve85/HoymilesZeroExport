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
LoopIntervalInSeconds = int(20) # interval time for setting limit to hoymiles
SetLimitDelay = int(5) # delay time after sending limit to Hoymiles
PollInterval = int(1) # polling interval for powermeter (must be < LoopIntervalInSeconds)

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
    if ParsedData == None:
      logging.info("Error: ParsedData is empty (in function GetHoymilesAvailable)")
      return False
    Reachable = bool(ParsedData["inverter"][0]["is_avail"])
    logging.info("HM reachable: %s",Reachable)
    return Reachable

def GetHoymilesActualPower():
    ParsedData = requests.get(url = f'http://{ahoyIP}/api/record/live').json()
    if ParsedData == None:
      logging.info("Error: ParsedData is empty (in function GetHoymilesActualPower)")
      return int(hoymilesMaxWatt)
    ActualPower = int(float(next(item for item in ParsedData['inverter'][0] if item['fld'] == 'P_AC')['val']))
    logging.info("HM power: %s %s",ActualPower, " Watt")
    return int(ActualPower)

def GetPowermeterWatts():
    ParsedData = requests.get(url = f'http://{tasmotaIP}/cm?cmnd=status%2010').json()
    if ParsedData == None:
      logging.info("Error: ParsedData is empty (in function GetPowermeterWatts)")
      return int(hoymilesMaxWatt)    
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
            for x in range(int(LoopIntervalInSeconds / PollInterval)):
                powermeterWatts = GetPowermeterWatts()
                if powermeterWatts > 0:
                    newLimitSetpoint = hoymilesMaxWatt
                    setLimit(hoymilesInverterID, newLimitSetpoint)
                    if int(LoopIntervalInSeconds) - SetLimitDelay - x * PollInterval <= 0:
                        break
                    else:
                        time.sleep(int(LoopIntervalInSeconds) - SetLimitDelay - x * PollInterval)
                    break
                else:
                    time.sleep(PollInterval)
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
