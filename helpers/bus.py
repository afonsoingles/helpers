from bases.helper import BaseHelper
from datetime import datetime
import os
import requests
import schedule
from utils.mongoHandler import MongoHandler

mongo = MongoHandler()

class busAlerts(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def run(self):
        print("[busAlerts] Started at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        enabledBusUsers = mongo.db.users.find({"userConfig.bus.enabled": True})
        for user in enabledBusUsers:
            print(f"[busAlerts] Processing user: {user['username']}")
            fetchBusLine = requests.get()
        print("[busAlerts] Finished at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def schedule(self):
        print("[busAlerts] Scheduling bus alerts")
        schedule.every(5).minutes.do(self.run)