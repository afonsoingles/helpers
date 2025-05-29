from bases.helper import BaseHelper
from datetime import datetime
import os
import requests
import schedule
from utils.mongoHandler import MongoHandler
from utils.pusher import Pusher

mongo = MongoHandler()
pusher = Pusher()

class busAlerts(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def run(self):
        print("[busAlerts] Started at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        enabledBusUsers = mongo.db.users.find({"userConfig.bus.enabled": True, "blocked": False})
        for user in enabledBusUsers:
            print(f"[busAlerts] Processing user: {user['username']}")
            realtimeData = requests.get(f"https://api.carrismetropolitana.pt/stops/{str(user['userConfig']['bus']['pickupStop'])}/realtime").json()

            nextBus = None
            for bus in realtimeData:
                if str(bus["line_id"]) not in user["userConfig"]["bus"]["lines"]:
                    continue
                
                try:
                    scheduledArrival = datetime.strptime(bus["scheduled_arrival"], '%H:%M:%S').time()
                    scheduledPickupTimes = [datetime.strptime(time, '%H:%M:%S').time() for time in user["userConfig"]["bus"]["scheduledPickupTimes"]]
                except:

                    continue
                
                if scheduledArrival not in scheduledPickupTimes:
                    continue
                
                if bus["scheduled_arrival_unix"] < datetime.now().timestamp():
                    continue

                nextBus = bus
                break

            
            if not nextBus:
                print(f"[busAlerts] No upcoming buses for user {user['username']}")
                continue
            
            print(f"[busAlerts] Next bus found for user {user['username']}: ", nextBus["line_id"])
            if not nextBus.get("estimated_arrival_unix"):
                print(f"[busAlerts] No estimated arrival time for user {user['username']}")
                continue
            

            
            currentTime = datetime.now()

            busEstimatedArrival = datetime.fromtimestamp(nextBus["estimated_arrival_unix"])
            userReminder = user["userConfig"]["bus"]["reminderTime"]
            timeDiff = (busEstimatedArrival - currentTime).total_seconds()
            busScheduledArrival = datetime.fromtimestamp(nextBus["scheduled_arrival_unix"])
            

            alert_data = {
                "username": user["username"],
                "vehicle_id": nextBus["vehicle_id"],
                "pickup_stop": user["userConfig"]["bus"]["pickupStop"],
                "scheduled_arrival": busScheduledArrival.strftime('%Y-%m-%d %H:%M:%S'),
                "estimated_arrival": busEstimatedArrival.strftime('%Y-%m-%d %H:%M:%S'),
                "estimated_difference": timeDiff,
                "alert_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            existing_alert = mongo.db.busAlerts.find_one({
                "username": user["username"],
                "vehicle_id": nextBus["vehicle_id"],
                "pickup_stop": user["userConfig"]["bus"]["pickupStop"]
            })

            if existing_alert:
                previous_estimated_arrival = datetime.strptime(existing_alert["estimated_arrival"], '%Y-%m-%d %H:%M:%S')
                previous_difference = (busEstimatedArrival - previous_estimated_arrival).total_seconds() / 60
                if existing_alert.get("observed_arrival", None):
                    continue

                if nextBus.get("observed_arrival", None):
                    observed_arrival = datetime.strptime(nextBus["observed_arrival"], '%Y-%m-%d %H:%M:%S')
                    observed_difference = (busEstimatedArrival - observed_arrival).total_seconds() / 60
                    alert_data["observed_arrival"] = nextBus["observed_arrival"]
                    alert_data["observed_difference"] = observed_difference
                    mongo.db.busAlerts.update_one(
                        {"_id": existing_alert["_id"]},
                        {"$set": alert_data}
                    )
                    print(f"[busAlerts] Bus has arrived.")
                    continue
                if previous_difference < 10:
                    print(f"[busAlerts] Skipping alert for user {user['username']} as estimated arrival hasn't changed significantly.")
                    continue
                else:
                    arrival_status = "earlier" if timeDiff < 0 else "later"
                    alert_data["arrival_status"] = arrival_status

                    # todo: add user-based notifications
                    pusher.bulkPush(
                        title=f"O autocarro {nextBus['line_id']} irá chegar {"mais cedo" if alert_data["arrival_status"] == "earlier" else "mais tarde"}",
                        body=f"O autocarro irá chegar à paragem às {busEstimatedArrival.strftime('%H:%M:%S')}.",
                        ttl=30,
                        data={}
                    )

                    mongo.db.busAlerts.insert_one(alert_data)
                    print(f"[busAlerts] Updated alert for user {user['username']} with new estimated arrival time.")
                    continue

            if timeDiff <= userReminder * 60:
                pusher.bulkPush(
                    title=f"Autocarro {nextBus['line_id']} a caminho",
                    body=f"O autocarro irá chegar à paragem às {busEstimatedArrival.strftime('%H:%M:%S')}.",
                    ttl=30,
                    data={}
                )
                
                mongo.db.busAlerts.insert_one(alert_data)
                print(f"[busAlerts] Alert sent for user {user['username']} for bus {nextBus['line_id']} arriving at {busEstimatedArrival.strftime('%H:%M:%S')}.")


    def schedule(self):
        schedule.every(1).minutes.do(self.run)