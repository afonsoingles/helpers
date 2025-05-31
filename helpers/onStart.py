from bases.helper import BaseHelper
from utils.github import GitHub
from utils.pusher import Pusher
from datetime import datetime
import os
import requests
import time

gh = GitHub()
pusher = Pusher()

class onStart(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=True)

    def run(self):
        print("[onStart] Started at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        time.sleep(15) # wait a bit, so the API can start
        pusher.bulkPush(
            title="Helpers ON",
            body=f"Os helpers foram iniciados com sucesso e estão a executar o commit {gh.get_latest_commit()}",
            sound="bing.wav",
            data={},
            ttl=30
        )

        print(f"[onStart] Pushed notification")





        print("[onStart] Finished at: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def schedule(self):
       
        pass