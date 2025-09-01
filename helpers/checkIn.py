from bases.helper import BaseHelper
import os
import requests
from main import logger

class checkIn(BaseHelper):
    def __init__(self, **kwargs):
        super().__init__(
            id="checkIn",
            name="Check In",
            description="Sends heartbeats to Better Stack to monitor CRON uptime.",
            boot_run=True,
            priority=2,
            schedule=["*/2 * * * *"],
            internal=True,
            allow_execution_time_config=False,
            **kwargs,
        )

    async def run(self):
        logger.info(f"[checkIn] Started! Sending heartbeat...")

        r = requests.get(os.environ.get("BETTER_STACK_HB"))

        logger.info(f"[checkIn] Heartbeat sent! Status code: {r.status_code}")
