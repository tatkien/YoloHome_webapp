"""YoloHome Gateway

Runs on the gateway host (e.g. a Raspberry Pi connected to one or more YoloKit
devices over serial / I2C / GPIO).  Responsibilities:

  1. Send a heartbeat to the backend every HEARTBEAT_INTERVAL seconds so the
     dashboard knows each device is online.
  2. Read sensor values from each kit and ingest them into the backend feed.
  3. Poll for pending commands and forward them to the kit.

Configuration is done via environment variables (or a .env file):

    BACKEND_URL        Base URL of the YoloHome backend  (default: http://localhost:8000)
    HEARTBEAT_INTERVAL Seconds between heartbeat calls (default: 30)
    POLL_INTERVAL      Seconds between command-poll cycles (default: 5)

    DEVICES            JSON array of device descriptors, one per physical kit:

        DEVICES='[
          {"device_id": 1, "device_key": "dev_abc...", "feed_id": 2},
          {"device_id": 3, "device_key": "dev_xyz...", "feed_id": 4},
          {"device_id": 5, "device_key": "dev_ijk..."}
        ]'

        Each entry:
          device_id  (int, required)   — ID registered in the backend
          device_key (str, required)   — Raw key returned on device creation
          feed_id    (int, optional)   — Feed to push sensor readings into

Usage:
    python gateway.py
"""

import json
import logging
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("gateway")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))  # seconds
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))  # seconds

_raw_devices = os.environ.get("DEVICES", "")
if not _raw_devices:
    raise SystemExit(
        "DEVICES environment variable is required.\n"
        'Example: DEVICES=\'[{"device_id": 1, "device_key": "dev_abc", "feed_id": 2}]\''
    )

try:
    DEVICES: list[dict] = json.loads(_raw_devices)
except json.JSONDecodeError as exc:
    raise SystemExit(f"DEVICES is not valid JSON: {exc}") from exc

for _entry in DEVICES:
    if "device_id" not in _entry or "device_key" not in _entry:
        raise SystemExit(
            f"Each entry in DEVICES must have 'device_id' and 'device_key'. Got: {_entry}"
        )

# ---------------------------------------------------------------------------
# Backend helpers
# ---------------------------------------------------------------------------

def _headers(device_key: str) -> dict[str, str]:
    return {"X-Device-Key": device_key}


def send_heartbeat(device_id: int, device_key: str) -> bool:
    """POST /devices/{id}/heartbeat — signals the device is online."""
    url = f"{BACKEND_URL}/api/v1/devices/{device_id}/heartbeat"
    try:
        resp = requests.post(url, headers=_headers(device_key), timeout=10)
        resp.raise_for_status()
        log.info("Heartbeat OK  (device %d)", device_id)
        return True
    except requests.RequestException as exc:
        log.warning("Heartbeat failed (device %d): %s", device_id, exc)
        return False


def ingest_value(feed_id: int, value: str, device_key: str) -> bool:
    """POST /feeds/{id}/ingest — push a sensor reading to the backend."""
    url = f"{BACKEND_URL}/api/v1/feeds/{feed_id}/ingest"
    try:
        resp = requests.post(url, headers=_headers(device_key), json={"value": value}, timeout=10)
        resp.raise_for_status()
        log.info("Ingested value=%r to feed %d", value, feed_id)
        return True
    except requests.RequestException as exc:
        log.warning("Ingest failed (feed %d): %s", feed_id, exc)
        return False


def poll_commands(device_id: int, device_key: str) -> list[dict]:
    """GET /devices/{id}/commands/pending — fetch pending commands."""
    url = f"{BACKEND_URL}/api/v1/devices/{device_id}/commands/pending"
    try:
        resp = requests.get(url, headers=_headers(device_key), timeout=10)
        resp.raise_for_status()
        commands = resp.json()
        if commands:
            log.info("Received %d command(s) for device %d", len(commands), device_id)
        return commands
    except requests.RequestException as exc:
        log.warning("Command poll failed (device %d): %s", device_id, exc)
        return []


def ack_command(device_id: int, device_key: str, command_id: int, result: dict | None = None) -> bool:
    """PATCH /devices/{id}/commands/{cid}/ack — acknowledge a command."""
    url = f"{BACKEND_URL}/api/v1/devices/{device_id}/commands/{command_id}/ack"
    try:
        resp = requests.patch(url, headers=_headers(device_key), json={"result": result}, timeout=10)
        resp.raise_for_status()
        log.info("Acked command %d (device %d)", command_id, device_id)
        return True
    except requests.RequestException as exc:
        log.warning("Ack failed for command %d (device %d): %s", command_id, device_id, exc)
        return False


def validate_devices() -> None:
    """Fail fast at startup if any device_id / device_key pair is wrong."""
    for dev in DEVICES:
        device_id = dev["device_id"]
        device_key = dev["device_key"]
        url = f"{BACKEND_URL}/api/v1/devices/{device_id}/heartbeat"
        try:
            resp = requests.post(url, headers=_headers(device_key), timeout=10)
        except requests.RequestException as exc:
            raise SystemExit(f"Cannot reach backend for device {device_id}: {exc}") from exc

        if resp.status_code == 404:
            raise SystemExit(f"device_id={device_id} does not exist in the backend.")
        if resp.status_code == 401:
            raise SystemExit(f"device_key is invalid for device {device_id}.")
        resp.raise_for_status()
        log.info("Validated device %d OK", device_id)


# ---------------------------------------------------------------------------
# Kit I/O  (replace these stubs with real serial / GPIO calls)
# ---------------------------------------------------------------------------

def read_sensor(device_id: int) -> str | None:
    """Read a value from the physical YoloKit identified by device_id.

    Replace this stub with your actual hardware read, e.g.:
        import serial
        line = ser.readline().decode().strip()
        return line
    """
    return None  # stub — no hardware attached


def apply_command(device_id: int, command: dict) -> dict:
    """Forward a command payload to the physical YoloKit and return the result.

    Replace this stub with your actual hardware write, e.g.:
        ser.write(json.dumps(command["payload"]).encode() + b"\\n")
        return {"applied": True}
    """
    log.info("Applying command payload for device %d: %s", device_id, command.get("payload"))
    return {"applied": True}  # stub


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    log.info(
        "Gateway starting  devices=%d  backend=%s  heartbeat=%ds  poll=%ds",
        len(DEVICES), BACKEND_URL, HEARTBEAT_INTERVAL, POLL_INTERVAL,
    )
    for dev in DEVICES:
        log.info("  device_id=%d  feed_id=%s", dev["device_id"], dev.get("feed_id"))

    validate_devices()

    last_heartbeat: dict[int, float] = {dev["device_id"]: 0.0 for dev in DEVICES}

    while True:
        now = time.monotonic()

        for dev in DEVICES:
            device_id: int = dev["device_id"]
            device_key: str = dev["device_key"]
            feed_id: int | None = dev.get("feed_id")

            # --- Heartbeat ---
            if now - last_heartbeat[device_id] >= HEARTBEAT_INTERVAL:
                send_heartbeat(device_id, device_key)
                last_heartbeat[device_id] = now

            # --- Sensor read → ingest ---
            if feed_id is not None:
                value = read_sensor(device_id)
                if value is not None:
                    ingest_value(feed_id, value, device_key)

            # --- Command poll → apply → ack ---
            for command in poll_commands(device_id, device_key):
                result = apply_command(device_id, command)
                ack_command(device_id, device_key, command["id"], result)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
