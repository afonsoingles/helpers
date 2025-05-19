from bases.helper import BaseHelper
import schedule
from datetime import datetime
from utils.mongoHandler import MongoHandler
from api.utils.pusher import InternalPusher

pusher = InternalPusher()
mongo = MongoHandler()

class rulesUpdater(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=False)

    def run(self):
        print("[criticalPusher] Started at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        allDevices = mongo.db.devices.find()
        tokensList = []
        for device in allDevices:
            tokensList.append(device["pushToken"])
        
        for i in range(50):
            try:
                r = pusher.bulk_push(tokensList, title=" ", body=" ", data={"type": "criticalAlert"}, sound="sos.wav", ttl=100, isCritical=True)
                print("[criticalPusher] Bulk push response: ", r)
                print("[criticalPusher] Pushed!")
            except:
                print("[criticalPusher] Error in bulk push")
                continue






        print("[criticalPusher] Finished at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def schedule(self):
        return
        schedule.every().day.at("08:57:00").do(self.run)
        schedule.every().day.at("09:09:00").do(self.run)
        schedule.every().day.at("09:23:00").do(self.run)
        schedule.every().day.at("09:38:00").do(self.run)
        schedule.every().day.at("09:50:00").do(self.run)
        schedule.every().day.at("10:06:00").do(self.run)

        schedule.every().day.at("10:20:00").do(self.run)
        schedule.every().day.at("10:22:34").do(self.run)
        schedule.every().day.at("10:26:54").do(self.run)
        schedule.every().day.at("10:28:00").do(self.run)
        schedule.every().day.at("10:29:00").do(self.run)
        schedule.every().day.at("10:30:00").do(self.run)
        schedule.every().day.at("10:32:00").do(self.run)
        schedule.every().day.at("10:34:00").do(self.run)