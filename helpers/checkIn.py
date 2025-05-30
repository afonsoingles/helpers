from bases.helper import BaseHelper
from datetime import datetime
import os
import requests
import time
import schedule

class checkIn(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def run(self):
        print("[checkIn] Started at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        r = requests.get(os.environ.get("BETTER_STACK_HB"))

        print(f"[checkIn] Heartbeat - {r.status_code}, response: {r.text}")





        print("[checkIn] Finished at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def schedule(self):
       
        schedule.every(2).minutes.do(self.run)