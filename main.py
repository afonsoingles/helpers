import asyncio
import os
import schedule
from dotenv import load_dotenv
from utils.startup import Startup
from utils.logger import Logger
from utils.github import GitHub
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

load_dotenv()

startup = Startup()
logger = Logger()
gh = GitHub()

if os.environ.get("DB_ENV") == "production":
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        send_default_pii=True,
        _experiments={"enable_logs": True},
        integrations=[
            LoggingIntegration(),
        ],
        traces_sample_rate=1.0,
        environment=os.environ.get("DB_ENV"),
        enable_tracing=True,
        release=gh.get_latest_commit(),
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
            except Exception as e:
                logger.error("Error in scheduled tasks", e)

    except KeyboardInterrupt as e:
        logger.info("[SHUTDOWN] Keyboard interrupt received.")
        startup.force_exit(logger, apiProcess)
    except Exception as e:
        logger.error("Error running startup process", e)
        startup.force_exit(logger, apiProcess)
    finally:
        startup.force_exit(logger, apiProcess)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt as e:
        logger.error("[SHUTDOWN] Keyboard interrupt received.", e)
        startup.force_exit(logger, apiProcess)
    except Exception as e:
        logger.error("Error in main thread", e)
