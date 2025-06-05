from bases.helper import BaseHelper
import schedule
from datetime import datetime
import os
import json
from utils.airtabler import Airtabler
from main import logger

airtabler = Airtabler(base_id=os.environ.get("AIRTABLE_BASE_ID"), api_key=os.environ.get("AIRTABLE_API_KEY"))

class rulesUpdater(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def run(self):
        logger.info(f"[rulesUpdater] Started at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")

        newData = airtabler.getAllData("rules")
        logger.info(f"[rulesUpdater] Obtained rules data")

        with open("data/rules.json", "w") as f:
            
            f.write(json.dumps(newData))
        logger.info(f"[rulesUpdater] Updated rules.json")





        logger.info(f"[rulesUpdater] Finished at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")

    def schedule(self):
       
        schedule.every().hour.at(":00").do(self.run)
