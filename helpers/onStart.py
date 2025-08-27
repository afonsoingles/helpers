from bases.helper import BaseHelper
from utils.github import GitHub
from main import logger
from utils.pusher import Pusher
import time

gh = GitHub()
pusher = Pusher()

class onStart(BaseHelper):
    def __init__(self):
        super().__init__(
            id="onStart",
            name="Startup Service",
            description="This helper notifies people when the system starts",
            require_admin_activation=True,
            boot_run=True,
            priority=1,
            schedule=[],
            allow_execution_time_config=False,
        )

    def run(self):

        time.sleep(15) # wait a bit, so the API can start
        pusher.push(
            sender="Startup Service",
            recipient=self.user["id"],
            title="Helpers started",
            body=f"Hello! Helpers have been started and are running version {gh.get_latest_commit()}",
            ttl=30,
        )

        logger.info(f"[onStart] Pushed notification to user {self.user['id']} about startup.")

    def schedule(self):
        pass