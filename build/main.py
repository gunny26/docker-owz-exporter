#!/usr/bin/python3
# noqa: E501
"""
program to read data from OWZ Webserver end publish the date for prometheus
"""
import json
import logging
import os
import time
# non std modules
import requests
from urllib.parse import urlencode, quote_plus
from prometheus_client import start_http_server, Gauge


logging.basicConfig(level=logging.INFO)

APP_BASE_URL = os.environ["APP_BASE_URL"]  # "http://heizung.messner.click/ajax.app"
APP_USERNAME = os.environ["APP_USERNAME"]  # "Administrator"
APP_PASSWORD = os.environ["APP_PASSWORD"]  # 'sun1"NUS'
APP_LOG_LEVEL = os.environ.get("APP_LOG_LEVEL", "INFO")
APP_INTERVAL = int(os.environ.get("APP_INTERVAL", "120"))

if APP_LOG_LEVEL == "DEBUG":
    logging.getLogger().setLevel(logging.DEBUG)
elif APP_LOG_LEVEL == "INFO":
    logging.getLogger().setLevel(logging.INFO)
elif APP_LOG_LEVEL == "ERROR":
    logging.getLogger().setLevel(logging.ERROR)

for key, value in os.environ.items():
    logging.info(f"{key} : {value}")

PROM_EXPORTER_PORT = 9100  # fixed to make HEALTHCHECK working
DATAPOINTS = {
    # 468: Info('owz_uhrzeit', 'Uhrzeit'),
    # "Betriebsart Heizkreis 1": 564,
    # "Betriebsart Heizkreis 2": 605,
    # "Status Trinkwasser": 1844,
    # "Status Wärmepumpe": 2405,
    # "Status Pufferspeicher": 2408,
    # "Status Trinkwasser": 2409,
    # "Status Heizkreis 1": 2411,
    # "Status Heizkreis 2": 2414,
    2420: Gauge("owz_aussentemperatur", "Aussentemperatur"),
    2422: Gauge("owz_vorlauftemperatur_ist_hk1", "Vorlauftemperatur Istwert Heizkreis 1"),
    2425: Gauge("owz_vorlauftemperatur_ist_hk2", "Vorlauftemperatur Istwert Heizkreis 2"),
    # "Lüftungsstufe 1": 2430,
    # "Lüftungsstufe 2": 2431,
    # "Lüftungsstufe 3": 2432,
    2433: Gauge("owz_trinkwasser_ist_b3", "Trinkwassertemperatur-Istwert Oben (B3)"),
    2436: Gauge("owz_pufferspeicher_ist_b4", "Pufferspeichertemperatur-Istwert Oben (B4)"),
    2438: Gauge("owz_ruecklauftemperatur_wp", "Rücklauftemperatur Wärmepumpe"),
    2440: Gauge("owz_vorlauftemperatur_wp", "Vorlauftemperatur Wärmepumpe"),
}


def owz_login(session, base_url: str, username: str, password: str) -> None:
    payload = {
        'user': username,
        'pwd': password
    }
    payload_enc = urlencode(payload, quote_via=quote_plus)
    res = session.get(f"{base_url}/main.app?{payload_enc}", verify=False)
    if res.status_code != 200:
        logging.error(res.headers)
        logging.error(res.status_code)
        logging.error(res.text)


def owz_get_dp(session, base_url: str, plant_item_id: int) -> dict:
    payload = {
        'service': 'getDp',
        'plantItemId': plant_item_id,
    }
    payload_enc = urlencode(payload, quote_via=quote_plus)
    res = session.get(f"{base_url}/ajax.app?{payload_enc}", verify=False)
    if res.status_code == 200:
        return res.json()
    else:
        logging.error(res.headers)
        logging.error(res.status_code)
        logging.error(res.text)


def main():
    start_http_server(PROM_EXPORTER_PORT)
    while True:
        starttime = time.time()
        session = requests.session()
        owz_login(session, APP_BASE_URL, APP_USERNAME, APP_PASSWORD)
        for item_id, metric in DATAPOINTS.items():
            value = owz_get_dp(session, APP_BASE_URL, item_id).get("value")
            logging.info(item_id, value)
            metric.set(float(value))
        duration = time.time() - starttime
        sleep_time = max(APP_INTERVAL - duration, 0)  # no negatives
        time.sleep(sleep_time)


if __name__ == "__main__":
   main()
