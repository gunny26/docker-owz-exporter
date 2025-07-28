#!/usr/bin/python3
"""
OWZ Heating System Prometheus Exporter
Reads data from OWZ heating control system and exports metrics for Prometheus.
"""
import logging
import os
import signal
import sys
import time
from urllib.parse import urlencode, quote_plus

import requests
from prometheus_client import start_http_server, Gauge


# Configuration from environment
APP_BASE_URL = os.environ["APP_BASE_URL"]
APP_USERNAME = os.environ["APP_USERNAME"]
APP_PASSWORD = os.environ["APP_PASSWORD"]
APP_LOG_LEVEL = os.environ.get("APP_LOG_LEVEL", "INFO")
APP_INTERVAL = int(os.environ.get("APP_INTERVAL", "120"))
PROM_EXPORTER_PORT = int(os.environ.get("PROMETHEUS_PORT", "9100"))

# Setup logging
logging.basicConfig(
    level=getattr(logging, APP_LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Datapoints configuration
DATAPOINTS = {
    2420: Gauge("owz_aussentemperatur", "Außentemperatur in °C"),
    2422: Gauge("owz_vorlauftemperatur_ist_hk1", "Vorlauftemperatur Istwert Heizkreis 1 in °C"),
    2425: Gauge("owz_vorlauftemperatur_ist_hk2", "Vorlauftemperatur Istwert Heizkreis 2 in °C"),
    2433: Gauge("owz_trinkwasser_ist_b3", "Trinkwassertemperatur-Istwert Oben (B3) in °C"),
    2436: Gauge("owz_pufferspeicher_ist_b4", "Pufferspeichertemperatur-Istwert Oben (B4) in °C"),
    2438: Gauge("owz_ruecklauftemperatur_wp", "Rücklauftemperatur Wärmepumpe in °C"),
    2440: Gauge("owz_vorlauftemperatur_wp", "Vorlauftemperatur Wärmepumpe in °C"),
}

# Global state
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False


def owz_login(session: requests.Session) -> bool:
    """Login to OWZ system"""
    try:
        payload = {"user": APP_USERNAME, "pwd": APP_PASSWORD}
        payload_enc = urlencode(payload, quote_via=quote_plus)

        response = session.get(f"{APP_BASE_URL}/main.app?{payload_enc}", verify=False, timeout=30)
        response.raise_for_status()

        logger.debug("Successfully logged in")
        return True
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return False


def owz_get_dp(session: requests.Session, plant_item_id: int) -> float:
    """Get datapoint value from OWZ system"""
    try:
        payload = {"service": "getDp", "plantItemId": plant_item_id}
        payload_enc = urlencode(payload, quote_via=quote_plus)

        response = session.get(f"{APP_BASE_URL}/ajax.app?{payload_enc}", verify=False, timeout=30)
        response.raise_for_status()

        data = response.json()
        value = data.get("value")

        if value is None:
            raise ValueError(f"No value returned for datapoint {plant_item_id}")

        return float(value)
    except Exception as e:
        logger.error(f"Failed to get datapoint {plant_item_id}: {e}")
        raise


def main():
    """Main application loop"""
    global running

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Starting OWZ Prometheus Exporter on port {PROM_EXPORTER_PORT}")
    logger.info(f"Scrape interval: {APP_INTERVAL} seconds")

    start_http_server(PROM_EXPORTER_PORT)

    while running:
        start_time = time.time()
        failed_metrics = 0

        try:
            session = requests.Session()

            if not owz_login(session):
                logger.error("Login failed, skipping this cycle")
                time.sleep(min(APP_INTERVAL, 60))  # Wait but not too long
                continue

            # Collect all datapoints
            for item_id, metric in DATAPOINTS.items():
                try:
                    value = owz_get_dp(session, item_id)
                    metric.set(value)
                    logger.debug(f"Updated {metric._name}: {value}")
                except Exception:
                    failed_metrics += 1

            if failed_metrics == 0:
                logger.info("Successfully scraped all metrics")
            else:
                logger.warning(f"Failed to scrape {failed_metrics}/{len(DATAPOINTS)} metrics")

        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}")

        # Calculate sleep time
        duration = time.time() - start_time
        sleep_time = max(APP_INTERVAL - duration, 0)

        if sleep_time > 0 and running:
            time.sleep(sleep_time)

    logger.info("Exporter shutdown complete")


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        logger.error(f"Missing required environment variable: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
