import asyncio
import os
import schedule
from dotenv import load_dotenv
from utils.startup import Startup
from utils.logger import Logger
from utils.github import GitHub
from utils.queue_bridge import init_queue_system, start_queue_system, is_queue_enabled, setup_api_integration
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

load_dotenv()

startup = Startup()
logger = Logger()
gh = GitHub()

# Initialize queue system if enabled
queue_startup = None
queue_system_enabled = init_queue_system()

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
global runningHelpers

apiProcess = None
runningHelpers = []



async def main():
    """
    Main application entry point with support for both legacy and new execution systems.
    
    If ENABLE_EXECUTION_QUEUE=true, uses the new Redis-based execution queue.
    Otherwise, falls back to the legacy schedule-based system.
    """
    logger.info("[STARTUP] Starting up...")
    
    global apiProcess, runningHelpers, queue_startup
    
    try:
        # Start API server
        apiProcess = await asyncio.create_subprocess_exec(
            "python", "-m", "uvicorn", "api.main:app",
            "--host", "0.0.0.0",
            "--port", os.environ.get("API_PORT", "8000"),
            "--log-level", os.environ.get("API_LOG_LEVEL", "info"),
            "--limit-concurrency", os.environ.get("API_LIMIT_CONCURRENCY", "500"),
        )
        
        # Choose execution system
        if is_queue_enabled():
            logger.info("[STARTUP] Using new execution queue system")
            
            # Start the queue system
            queue_startup = await start_queue_system()
            
            if queue_startup:
                # Setup API integration
                setup_api_integration()
                logger.info("[STARTUP] Queue system startup complete. Entering event loop...")
                
                # Run the queue system's main loop
                await queue_startup.run_main_loop()
            else:
                logger.error("[STARTUP] Failed to start queue system, falling back to legacy system")
                await run_legacy_system()
        else:
            logger.info("[STARTUP] Using legacy schedule-based system")
            await run_legacy_system()

    except KeyboardInterrupt:
        logger.info("[SHUTDOWN] Keyboard interrupt received.")
        await shutdown_systems()
    except Exception as e:
        logger.error("Error running startup process", e)
        await shutdown_systems()

async def run_legacy_system():
    """Run the legacy schedule-based helper system."""
    global runningHelpers
    
    helpers = startup.discover_helpers()
    logger.info(f"[STARTUP] Found {len(helpers)} helpers.")
    
    runningHelpers = [
        asyncio.create_task(startup.run_helper(helper)) for helper in helpers
    ]
    logger.info("[STARTUP] Legacy startup complete. Waiting for scheduled tasks...")
    
    while True:
        try:
            schedule.run_pending()
            await asyncio.sleep(1)
        except Exception as e:
            logger.error("Error in scheduled tasks", e)

async def shutdown_systems():
    """Clean shutdown of all systems."""
    global apiProcess, runningHelpers, queue_startup
    
    # Shutdown queue system if running
    if queue_startup:
        try:
            await queue_startup.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down queue system: {e}")
    
    # Cancel legacy helper tasks
    if runningHelpers:
        for task in runningHelpers:
            if not task.done():
                task.cancel()
        try:
            await asyncio.gather(*runningHelpers, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error shutting down helper tasks: {e}")
    
    # Kill API process
    startup.force_exit(apiProcess)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt as e:
        logger.error("[SHUTDOWN] Keyboard interrupt received.", e)
        if apiProcess:
            startup.force_exit(apiProcess)
    except Exception as e:
        logger.error("Error in main thread", e)
