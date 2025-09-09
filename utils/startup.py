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


    def force_exit(self, apiProcess):
            self.logger.info("[SHUTDOWN] Killing all tasks...")
            try:
                if apiProcess:
                    apiProcess.kill()
            except Exception as e:
                self.logger.error(f"Failed to kill API process: {e}", e)
            os._exit(1)

