from bases.helper import BaseHelper
import datetime
from main import logger
from utils.pusher import Pusher
import requests
import time

pusher = Pusher()

class busAlerts(BaseHelper):
    def __init__(self, **kwargs):
        super().__init__(
            id="busAlerts",
            name="Bus Alerts",
            description="Get notified when a bus is approaching your stop",
            params={
                "lineId": "int",
                "pickupStopId": "int",
                "scheduledPickupTime": "str",
                "weekendEnabled": "bool",
            },
            priority=1,
            allow_execution_time_config=True,
            **kwargs,
        )

    async def run(self):
        logger.info(f"[busAlerts] Starting for {self.user["id"]}...")
        busParams = next((s for s in self.user["services"] if s["id"] == "busAlerts"), None)["params"]
        
        if busParams["weekendEnabled"] == False and datetime.datetime.now().weekday() >= 5:
            logger.info(f"[busAlerts] Weekend alerts are disabled for user {self.user['id']}. Skipping.")
            return
        
        carrisArrivalData = requests.get(f"https://api.carrismetropolitana.pt/v2/arrivals/by_stop/{str(busParams['pickupStopId'])}").json()
        if carrisArrivalData == []:
            logger.warn(f"[busAlerts] No data available for stop {busParams['pickupStopId']} for user {self.user['id']}.")
            return
        
        for arrival in carrisArrivalData:
            if arrival["line_id"] == str(busParams["lineId"]) and arrival["scheduled_arrival"] == busParams["scheduledPickupTime"]:
                secondsToArrive = arrival["scheduled_arrival_unix"] - int(datetime.datetime.now().timestamp())
                logger.warn(f"bus time diff: {secondsToArrive}")
                while True:
                    if secondsToArrive <= 300:
                        pusher.push(
                            sender="Bus Alerts",
                            recipient=self.user["id"],
                            title="Your bus is arriving!",
                            body=f"Your bus (line {str(busParams['lineId'])}) is arriving at your stop at {arrival['scheduled_arrival']}. Get ready!",
                            data={"customScreenOpen": "busAlerts"},
                            ttl=100
                        )

                        logger.info(f"[busAlerts] Pushed notification to user {self.user['id']}!")
                        break
                    await time.sleep(5)
                
