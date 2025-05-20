import schedule
import importlib
import os
import asyncio
from dotenv import load_dotenv
from bases.helper import BaseHelper

load_dotenv()
print("[STARTUP] Helpers - Starting up...")

def discover_helpers():
    helpers = []
    helpers_dir = os.path.join(os.path.dirname(__file__), 'helpers')

    if not os.path.exists(helpers_dir):
        print("[STARTUP] No helpers found. Exiting.")
        quit()

    helper_files = [file for file in os.listdir(helpers_dir) if file.endswith('.py') and file != '__init__.py']
    if not helper_files:
        print("[STARTUP] No helpers found. Exiting.")
        quit()

    for file in helper_files:
        module_name = f"helpers.{file[:-3]}"
        try:
            module = importlib.import_module(module_name)
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type) and issubclass(obj, BaseHelper) and obj is not BaseHelper:
                    print(f"[STARTUP] Loaded helper: {obj.__name__}")
                    helpers.append(obj())
        except Exception as e:
            print(f"Error importing helper {module_name}: {e}")
    return helpers

#TODO: Add Monitors


async def run_helper(helper):
    if helper.run_at_start:
        try:
            print(f"[STARTUP] Run Helper: {helper.__class__.__name__}")
            await asyncio.to_thread(helper.run)
        except Exception as e:
            print(f"[ERROR] Error running helper {helper.__class__.__name__} at startup: {e}")
    try:
        await asyncio.to_thread(helper.schedule)
    except Exception as e:
        print(f"[ERROR] Error scheduling helper {helper.__class__.__name__}: {e}")


async def main():
    helpers = discover_helpers()
    print(f"[STARTUP] Found {len(helpers)} helpers.")
    

    await asyncio.create_subprocess_exec(
        "python", "-m", "uvicorn", "api.main:app",
        "--host", "0.0.0.0",
        "--port", os.environ.get("API_PORT", "8000"),
        "--log-level", os.environ.get("API_LOG_LEVEL", "info")
    )
    await asyncio.gather(*(run_helper(helper) for helper in helpers))
    print("[STARTUP] Startup done. Waiting for scheduled tasks...")
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[ERROR] Error during scheduled task execution: {e}")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
