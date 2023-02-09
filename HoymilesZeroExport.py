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
hoymilesMinWattInPercent = int(5) # minimum limit in watts, e.g. 5%
hoymilesBigJumpPercent = int(20) # indicates a "big jump" in percent of hoymilesMaxWatt
hoymilesBigJumpOffsetInPercent = int(20) # Additional offset in percent of the "Jump-Watts", used for calculation to jump from max Limit to calculated limit
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
        hoymilesIsReachable = bool(ParsedData["inverter"][hoymilesInverterID]["is_avail"])
        if not hoymilesIsReachable:
            logging.info("HM reachable: %s",hoymilesIsReachable)

        if hoymilesIsReachable:
            # check all the time if powermeterWatts > 0...
            for x in range(LoopIntervalInSeconds):
                ParsedData = requests.get(url = f'http://{tasmotaIP}/cm?cmnd=status%2010').json()
                powermeterWatts = int(ParsedData["StatusSNS"]["SML"]["curr_w"])
                # if powermeter > 0 -> immediatelly increase limit to 100%
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
            logging.info("powermeter: %s %s",powermeterWatts, " Watt")
            if powermeterWatts > 0:
                continue

            # producing too much power: reduce limit
            if powermeterWatts < (powermeterTargetPoint - powermeterTolerance):
                # check if the new limit step exceed hoymilesBigJumpPercent
                if abs((powermeterWatts - powermeterTargetPoint) / hoymilesMaxWatt) * 100 >= hoymilesBigJumpPercent:
                    # ok, it is a "big jump", calc new setpoint and add 20% of the JumpWatts to be safe
                    ParsedData = requests.get(url = f'http://{ahoyIP}/api/record/live').json()
                    hoymilesActualPower = int(float(next(item for item in ParsedData['inverter'][hoymilesInverterID] if item['fld'] == 'P_AC')['val']))
                    logging.info("HM power: %s %s",hoymilesActualPower, " Watt")
                    newLimitSetpoint = hoymilesActualPower - abs(powermeterWatts) + abs(powermeterTargetPoint)
                    newLimitSetpoint = newLimitSetpoint + abs(int((hoymilesMaxWatt - newLimitSetpoint) * hoymilesBigJumpOffsetInPercent / 100))
                else:
                    newLimitSetpoint = newLimitSetpoint - abs(powermeterWatts) + abs(powermeterTargetPoint) # jump to setpoint
                logging.info("Too much energy producing: reducing limit")

            # producing not enough power: increase limit
            elif powermeterWatts > (powermeterTargetPoint + powermeterTolerance):
                if newLimitSetpoint < hoymilesMaxWatt:
                    newLimitSetpoint = newLimitSetpoint - abs(powermeterWatts) + abs(powermeterTargetPoint)
                    logging.info("Not enough energy producing: increasing limit")
                else:
                    logging.info("Not enough energy producing: limit already at maximum")

            # check for upper and lower limits
            if newLimitSetpoint > hoymilesMaxWatt:
                newLimitSetpoint = hoymilesMaxWatt
            if newLimitSetpoint < (hoymilesMaxWatt * hoymilesMinWattInPercent / 100):
                newLimitSetpoint = (hoymilesMaxWatt * hoymilesMinWattInPercent / 100)

            # set new limit to inverter
            if oldLimitSetpoint != newLimitSetpoint:
                setLimit(hoymilesInverterID, newLimitSetpoint)
        else:
            time.sleep(LoopIntervalInSeconds)

    except TypeError as e:
        logging.error(e)
        time.sleep(LoopIntervalInSeconds)
