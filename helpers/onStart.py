from bases.helper import BaseHelper
from datetime import datetime
import os
import requests
import time

class onStart(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def run(self):
        print("[onStart] Started at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        time.sleep(15) # wait a bit, so the API can start
        r = requests.post(f"{os.environ.get('API_URL')}/v1/notifications/send", headers={
            "X-Secure-Key": os.environ.get("SECURE_KEY"),
        }, json={
            "title": "Nova versão!",
            "body": "A API foi atualizada para o commit mais recente.",
            "sendAll": True,
            "isCritical": False,
            "sound": "bing.wav"
        })

        print(f"[onStart] Pushed notification. Output: {r.status_code} - {r.text}")





        print("[onStart] Finished at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def schedule(self):
       
        pass