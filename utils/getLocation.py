# obter localizações do traccar

import requests
import os


def getLocation():
    location = requests.get(f"{os.environ.get("TRACCAR_URL")}/api/positions", headers={"Authorization": f"bearer {os.environ.get("TRACCAR_KEY")}"}).json()
    device_location = next((loc for loc in location if loc['deviceId'] == int(os.environ.get("TRACCAR_DEVICE_ID"))), None)
    return device_location

