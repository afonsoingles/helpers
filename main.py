import asyncio
import os
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

load_dotenv()

from utils.startup import Startup
from utils.logger import Logger
from utils.github import GitHub
from utils.systemTools import SystemTools
from utils.queueTools import QueueTools


systemTools = SystemTools()
logger = Logger()
startup = Startup(logger)
queueTools = QueueTools(logger)
gh = GitHub()

if os.environ.get("DB_ENV") == "production":
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        send_default_pii=True,
        _experiments={"enable_logs": True},
        integrations=[
            LoggingIntegration(),
        ],
        traces_sample_rate=0.5,
        sample_rate=0.5,
        environment=os.environ.get("DB_ENV"),
        enable_tracing=True,
        release=gh.get_latest_commit(),
    )

global apiProcess




async def main():
    logger.info(f"[STARTUP] Hello! Helpers is booting up!")
    logger.info(f"[STARTUP] You are in {os.environ.get('DB_ENV', 'development')} mode")
    await systemTools.clear_helpers()
    logger.info("[STARTUP] Cleared helpers cache on redis.")

    loadedHelpers = await startup.discover_helpers()
    logger.info(f"[STARTUP] Found {len(loadedHelpers)} helpers.")

    await queueTools.build_initial_execution_queue()
    logger.info("[STARTUP] Built initial execution queue.")

    try:
        apiProcess = await asyncio.create_subprocess_exec(
            "python", "-m", "uvicorn", "api.main:app",
            "--host", "0.0.0.0",
            "--port", os.environ.get("API_PORT", "8000"),
            "--log-level", os.environ.get("API_LOG_LEVEL", "info"),
            "--limit-concurrency", os.environ.get("API_LIMIT_CONCURRENCY", "500"),
        )

        logger.info(f"[STARTUP] Launched API process with PID {apiProcess.pid}.")
        logger.info(f"[STARTUP] Startup complete. Enabling dispatcher.")

        await asyncio.gather(
            startup.run_dispatcher(),
            #sliding_window_expansion()
        )

    except KeyboardInterrupt as e:
        logger.info("[SHUTDOWN] Shutting down.")
        startup.force_exit(apiProcess)
    except Exception as e:
        logger.error("[STARTUP] Shutting down due to internal error", e)
        startup.force_exit(apiProcess)
    finally:
        startup.force_exit(apiProcess)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Something went wrong!", e)