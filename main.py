import asyncio
import os
import schedule
import logging
from dotenv import load_dotenv
from utils.startup import Startup
from utils.logger import Logger
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
import traceback

load_dotenv()

startup = Startup()
logger = Logger()

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    send_default_pii=True,
    _experiments={"enable_logs": True},
    integrations=[
        LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR
        ),
    ],
    traces_sample_rate=1.0,
    environment=os.environ.get("DB_ENV")
)

global apiProcess
global runningHelpers

apiProcess = None
runningHelpers = []



async def main():
    logger.info("[STARTUP] Starting up...")
    helpers = startup.discover_helpers()
    logger.info(f"[STARTUP] Found {len(helpers)} helpers.")

    try:
        apiProcess = await asyncio.create_subprocess_exec(
            "python", "-m", "uvicorn", "api.main:app",
            "--host", "0.0.0.0",
            "--port", os.environ.get("API_PORT", "8000"),
            "--log-level", os.environ.get("API_LOG_LEVEL", "info")
        )


        runningHelpers = [
            asyncio.create_task(startup.run_helper(helper)) for helper in helpers
        ]

        logger.info("[STARTUP] Startup complete. Waiting for scheduled tasks...")
        while True:
            try:
                schedule.run_pending()
                await asyncio.sleep(1)
            except Exception:
                print(f"{traceback.format_exc()}")

    except KeyboardInterrupt:
        logger.info("[SHUTDOWN] Keyboard interrupt received.")
        startup.force_exit(logger, apiProcess)
    except Exception:
        logger.error(traceback.format_exc())
        startup.force_exit(logger, apiProcess)
    finally:
        startup.force_exit(logger, apiProcess)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[SHUTDOWN] Keyboard interrupt received.")
        startup.force_exit(logger, apiProcess)
    except Exception:
        logger.error(traceback.format_exc())
        traceback.print_exc()
