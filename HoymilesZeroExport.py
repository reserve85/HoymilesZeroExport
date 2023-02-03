import requests, time
from requests.auth import HTTPBasicAuth
import os
import logging

ahoyIP = '192.168.10.57'
tasmotaIP = '192.168.10.90'

hoymilesInverterID = 0
hoymilesMaxWatt = 1500 # maximum limit in watts (100%)
hoymilesMinWatt = int(hoymilesMaxWatt / 10) # minimum limit in watts (should be around 10% of maximum inverter power)
hoymilesPosOffsetInWatt = 50 # positive poweroffset in Watt, used to allow some watts more to produce. It's like a reserve

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def setLimit(hoymilesInverterID, Limit):
    url = f"http://{ahoyIP}/api/ctrl"
    data = f'''{{"id": {hoymilesInverterID}, "cmd": "limit_nonpersistent_absolute", "val": {Limit}}}'''
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    logging.info("setting new limit to ",Limit," Watt")
    requests.post(url, data=data, headers=headers)

while True:
    try:
        ParsedData = requests.get(url = f'http://{ahoyIP}/api/index').json()
        hoymilesIsReachable = ParsedData["inverter"][0]["is_avail"]

        ParsedData = requests.get(url = f'http://{ahoyIP}/api/record/live').json()
        hoymilesActualPower = next(item for item in ParsedData['inverter'][0] if item['fld'] == 'P_AC')['val']

        ParsedData = requests.get(url = f'http://{ahoyIP}/api/record/config').json()
        hoymilesActualLimit =int(float(ParsedData['inverter'][0][0]['val']) * 0.01 * hoymilesMaxWatt)

        ParsedData = requests.get(url = f'http://{tasmotaIP}/cm?cmnd=status%2010').json()
        powermeterWatts = int(ParsedData["StatusSNS"]["SML"]["curr_w"])

        newLimitSetpoint = hoymilesActualLimit

        logging.info("HM reachable: %s",hoymilesIsReachable)
        logging.info("HM power: %s %s",hoymilesActualPower, "Watt")
        logging.info("powermeter: %s %s",powermeterWatts, "Watt")
        logging.info("HM Limit: %s",hoymilesActualLimit)

        if hoymilesIsReachable:
            # producing too much power: reduce limit
            if powermeterWatts < 0 - hoymilesPosOffsetInWatt:
                if hoymilesActualLimit >= hoymilesMaxWatt:
                    newLimitSetpoint = hoymilesActualPower + powermeterWatts + hoymilesPosOffsetInWatt
                else:
                    newLimitSetpoint = hoymilesActualLimit - abs(powermeterWatts) + hoymilesPosOffsetInWatt
                logging.info("Too much energy producing: reducing limit")

            # producing too little power: increase limit
            if powermeterWatts > 0:
                if hoymilesActualLimit < hoymilesMaxWatt:
                    newLimitSetpoint = hoymilesActualLimit + abs(powermeterWatts) + hoymilesPosOffsetInWatt
                    logging.info("Not enough energy producing: increasing limit")
                else:
                    logging.info("Not enough energy producing: limit already at maximum")

            # check for upper and lower limits
            if newLimitSetpoint > hoymilesMaxWatt:
                newLimitSetpoint = hoymilesMaxWatt
            if newLimitSetpoint < hoymilesMinWatt:
                newLimitSetpoint = hoymilesMinWatt

            # set new limit to inverter
            if hoymilesActualLimit != newLimitSetpoint:
                setLimit(hoymilesInverterID, newLimitSetpoint)

        time.sleep(10)

    except TypeError as e:
        logging.error(e)
        time.sleep(10)
