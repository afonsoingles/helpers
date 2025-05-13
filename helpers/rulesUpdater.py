from bases.helper import BaseHelper
import schedule
from datetime import datetime
import os
import json
from utils.airtabler import Airtabler

airtabler = Airtabler(base_id=os.environ.get("AIRTABLE_BASE_ID"), api_key=os.environ.get("AIRTABLE_API_KEY"))

class rulesUpdater(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def run(self):
        print("[rulesUpdater] Started at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        newData = airtabler.getAllData("rules")
        print(f"[rulesUpdater] Obtained rules data")

        with open("data/rules.json", "w") as f:
            
            f.write(json.dumps(newData))
        print(f"[rulesUpdater] Updated rules.json")





        print("[rulesUpdater] Finished at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def schedule(self):
       
        schedule.every().hour.at(":00").do(self.run)

        for minute in range(30):
            schedule.every().day.at(f"08:{minute}:00").do(self.run)