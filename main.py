import schedule
from utils.startup import Startup
import os
import asyncio
from dotenv import load_dotenv

startup = Startup()

load_dotenv()
print("[STARTUP] Helpers - Starting up...")



async def main():
    helpers = startup.discover_helpers()
    print(f"[STARTUP] Found {len(helpers)} helpers.")
    

    await asyncio.create_subprocess_exec(
        "python", "-m", "uvicorn", "api.main:app",
        "--host", "0.0.0.0",
        "--port", os.environ.get("API_PORT", "8000"),
        "--log-level", os.environ.get("API_LOG_LEVEL", "info")
    )
    await asyncio.gather(*(startup.run_helper(helper) for helper in helpers))
    print("[STARTUP] Startup done. Waiting for scheduled tasks...")
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[ERROR] Error during scheduled task execution: {e}")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
