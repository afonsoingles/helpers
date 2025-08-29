import os
import importlib
from bases.helper import BaseHelper
import asyncio
import datetime
import json
from utils.logger import Logger
from utils.systemTools import SystemTools
from api.utils.authTools import AuthenticationTools
from utils.queueTools import QueueTools

systemTools = SystemTools()
authTools = AuthenticationTools()


class Startup:

    def __init__(self, logger: Logger):
        self.queueTools = QueueTools(logger)
        self.logger = logger

   

    async def discover_helpers(self):
        helperFiles = [file for file in os.listdir("helpers") if file.endswith('.py')]
        loadedHelpers = []

        for file in helperFiles:
            try:
                helper = importlib.import_module(f"helpers.{file[:-3]}")
                for attr in dir(helper):
                    obj = getattr(helper, attr)
                    if isinstance(obj, type) and issubclass(obj, BaseHelper) and obj is not BaseHelper:
                        instance = obj()
                        init_args = dict(instance.__dict__)
                        await systemTools.register_helper(instance.id, json.dumps(init_args))
                        loadedHelpers.append(instance.id)
                        self.logger.info(f"[STARTUP] Loaded helper: {instance.name} with ID: {instance.id}")
            except Exception as e:
                self.logger.warn(f"Unable to import helper on file {file}. Please check helper configuration!\n{e}")

        return loadedHelpers

        
    async def run_dispatcher(self):
        while True:
            try:
                currentTime = int(datetime.datetime.now().timestamp())
                jobs = await self.queueTools.get_jobs_to_run(currentTime)

                for job in jobs:
                    self.logger.info(f"[DISPATCHER] Processing job {job}...")
                    try:
                        jobData = await self.queueTools.get_job_details(job)
                        executionTime = int(jobData.get("executionTime", 0))
                        executionExpiry = int(jobData.get("executionExpiry", 0))
                        userId = jobData.get("userId")
                        helperId = jobData.get("helperId")
                        jobId = job

                        if currentTime > executionTime + executionExpiry:
                            await self.queueTools.update_job_status(jobId, "expired")
                        else:
                            await self.queueTools.update_job_status(jobId, "running")
                            userData = await authTools.get_user_by_id(userId)
                            await systemTools.run_helper(helperId, userData)
                            self.logger.info(f"[DISPATCHER] Dispatched job {jobId} for execution.")

                    except Exception as e:
                        self.logger.error(f"[DISPATCHER] Error processing job {jobId}", e)
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error("[DISPATCHER] Error in dispatcher loop", e)

    """async def sliding_window_expansion():
        while True:
            try:
                current_time = int(time.time())
                lookahead_time = current_time + 2 * 3600  # 2 hours ahead
                new_lookahead_time = lookahead_time + 300  # Extend by 5 minutes

                active_users = await mongo.db.users.find({"blocked": False}).to_list(length=None)

                for user in active_users:
                    active_helpers = user.get("active_helpers", [])
                    for helper_id in active_helpers:
                        execution_time = lookahead_time
                        while execution_time <= new_lookahead_time:
                            await systemTools.queue_job(
                                helper_id=helper_id,
                                user_id=user["_id"],
                                execution_time=execution_time,
                                priority=3,  # Default priority
                                execution_expiry=3600  # 1 hour expiry
                            )
                            execution_time += 300  # Schedule every 5 minutes

                logger.info("[SLIDING WINDOW] Expanded execution queue by 5 minutes.")
                await asyncio.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error("[SLIDING WINDOW] Error in sliding window expansion", e)"""

    def force_exit(self, apiProcess):
            self.logger.info("[SHUTDOWN] Killing all tasks...")
            try:
                if apiProcess:
                    apiProcess.kill()
            except Exception as e:
                self.logger.error(f"Failed to kill API process: {e}", e)
            os._exit(1)

