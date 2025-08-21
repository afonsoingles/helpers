import asyncio
import os
from dotenv import load_dotenv
from utils.queued_startup import QueuedStartup
from utils.logger import Logger
from utils.github import GitHub
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

load_dotenv()

startup = QueuedStartup()
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
        traces_sample_rate=0.5,
        sample_rate=0.5,
        environment=os.environ.get("DB_ENV"),
        enable_tracing=True,
        release=gh.get_latest_commit(),
    )

global apiProcess

apiProcess = None

async def main():
    """
    Main application entry point using the new execution queue system.
    
    Implements the startup flow described in the problem statement:
    1. Register helpers in Redis
    2. Build initial 2-hour execution queue  
    3. Start dispatcher loop
    4. Start API server
    5. Run main event loop
    """
    logger.info("[STARTUP] Starting up with new execution queue system...")
    
    try:
        # Step 1: Execute the complete startup sequence
        await startup.startup_sequence()
        
        # Step 2: Start API server
        api_config = {
            "host": "0.0.0.0",
            "port": os.environ.get("API_PORT", "8000"),
            "log_level": os.environ.get("API_LOG_LEVEL", "info"),
            "limit_concurrency": os.environ.get("API_LIMIT_CONCURRENCY", "500")
        }
        
        apiProcess = await startup.start_api_server(api_config)
        
        # Step 3: Initialize API helper management
        from api.routers.helpers import init_helper_management
        init_helper_management(startup.execution_queue, startup.dispatcher)
        
        logger.info("[STARTUP] Startup complete. Entering main event loop...")
        
        # Step 4: Run main event loop
        await startup.run_main_loop()

    except KeyboardInterrupt:
        logger.info("[SHUTDOWN] Keyboard interrupt received.")
        startup.force_exit(apiProcess)
    except Exception as e:
        logger.error("Error running startup process", e)
        startup.force_exit(apiProcess)
    finally:
        startup.force_exit(apiProcess)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt as e:
        logger.error("[SHUTDOWN] Keyboard interrupt received.", e)
        startup.force_exit(apiProcess)
    except Exception as e:
        logger.error("Error in main thread", e)