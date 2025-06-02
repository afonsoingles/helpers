import os
import importlib
from bases.helper import BaseHelper
import asyncio


class Startup:

    def discover_helpers(self):
        helpers = []


        helperFiles = [file for file in os.listdir("helpers") if file.endswith('.py') ]


        for file in helperFiles:
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
    
    async def run_helper(self, helper):
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

    
    def force_exit(self, logger, apiProcess):
        logger.info("[SHUTDOWN] Killing all tasks...")
        try:
            if apiProcess:
                apiProcess.kill()
        except Exception as e:
            logger.error(f"Failed to kill API process: {e}")
        os._exit(1)

