from bases.helper import BaseHelper
from datetime import datetime
import os
import requests
import schedule
from utils.mongoHandler import MongoHandler

mongo = MongoHandler()

class alerts(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def run(self):
        print("[alerts] Started at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        fetchAlerts = requests.get("https://api-dev.fogos.pt/v2/incidents/active").json()
        for incident in fetchAlerts.get("data", []):
            mongo.db.occurrences.update_one(
                {"id": incident["id"]},
                {"$set": {
                    "id": incident["id"],
                    "date": incident["date"],
                    "hour": incident["hour"],
                    "air": incident["aerial"],
                    "water": incident["meios_aquaticos"],
                    "terraine": incident["terrain"],
                    "man": incident["man"],
                    "dico": incident["dico"],
                    "lat": incident["lat"],
                    "lon": incident["lng"],
                    "typeId": incident["naturezaCode"],
                    "type": incident["natureza"],
                    "status": incident["status"],
                    "statusCode": incident["statusCode"],
                }},
                upsert=True
            )
        print(f"[alerts] Updated {len(fetchAlerts.get('data', []))} occurrences in the database")
        print("[alerts] Finished at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def schedule(self):
        schedule.every(5).minutes.do(self.run)