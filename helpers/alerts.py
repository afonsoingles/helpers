from bases.helper import BaseHelper
from datetime import datetime
from main import logger
import requests
import schedule
from math import radians, sin, cos, sqrt, atan2
from utils.mongoHandler import MongoHandler
from utils.getLocation import getLocation
from utils.pusher import Pusher

mongo = MongoHandler()
pusher = Pusher()

class alerts(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371 * 1000
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c
    
    def run(self):
        logger.info(f"[alerts] Started at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")

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


        logger.info(f"[alerts] Updated {len(fetchAlerts.get('data', []))} occurrences in the database")
        closedOccurrences = mongo.db.occurrences.update_many(
            {"id": {"$nin": list(incident["id"] for incident in fetchAlerts.get("data", []))}},
            {"$set": {"status": "Terminada", "statusCode": 12}}
        )
        
        logger.info(f"[alerts] Closed {closedOccurrences.modified_count} occurrences in the database")

        userLocation = getLocation()


        user_lat = float(userLocation["latitude"])
        user_lon = float(userLocation["longitude"])
        nearby_occurrences = []
        



        for occurrence in mongo.db.occurrences.find({"statusCode": {"$ne": 12}}):
            distance = self._haversine(occurrence["lat"], occurrence["lon"], user_lat, user_lon)
            if distance <= 2000:  # 2km
                nearby_occurrences.append(occurrence)
        

        if nearby_occurrences:
            for occurrence in nearby_occurrences:
                if occurrence.get("alertSent", False) == True:
                    continue
                body_message = f"Existe um incêndio perto de si. Estão envolvidos {occurrence['man']} operacionais"
                if occurrence["air"] != 0:
                    body_message += f" e {occurrence['air']} meios aéreos"
                
                pusher.bulkPush(
                    title="🚨 Ocorrência perto de si",
                    body=body_message,
                    ttl=30,
                    data={},
                    isCritical=True,
                )
                mongo.db.occurrences.update_one(
                    {"id": occurrence["id"]},
                    {"$set": {"alertSent": True}}
                )
        else:
            logger.info("[alerts] No occurrences near the user.")

        logger.info(f"[alerts] Finished at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")

    def schedule(self):
        schedule.every(5).minutes.do(self.run)