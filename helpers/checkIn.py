from bases.helper import BaseHelper
from datetime import datetime
import os
import requests
from main import logger
import schedule

class checkIn(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def run(self):
        logger.info(f"[checkIn] Started at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")

        r = requests.get(os.environ.get("BETTER_STACK_HB"))

        logger.info(f"[checkIn] Heartbeat - {r.status_code}, response: {r.text}")





        logger.info(f"[checkIn] Finished at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")

    def schedule(self):
       
        schedule.every(2).minutes.do(self.run)