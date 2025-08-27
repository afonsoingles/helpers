import os
import importlib
from bases.helper import BaseHelper
import asyncio
import datetime
from utils.logger import Logger
from utils.systemTools import SystemTools
from api.utils.authTools import AuthenticationTools

systemTools = SystemTools()
authTools = AuthenticationTools()


class Startup:

    def __init__(self, logger: Logger):
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
                        init_args = {param: getattr(obj, param, None) for param in obj.__init__.__annotations__.keys()}
                        instance = obj()
                        await systemTools.register_helper(instance.id, str(init_args))
                        loadedHelpers.append(instance.id)
                        self.logger.info(f"[STARTUP] Loaded helper: {instance.name} with ID: {instance.id}")
            except Exception as e:
                self.logger.warn(f"Unable to import helper on file {file}. Please check helper configuration!\nErr")

        return loadedHelpers
    
    async def build_initial_execution_queue(self):
        self.logger.info("[QUEUE] Building initial execution queue...")
        #TODO: handle para internal helpers
        activeUsers = await authTools.get_all_active_users()
        currentTime = int(datetime.datetime.now().timestamp())
        lookahedTime = currentTime + 2 * 3600  # 2h
        

        for user in activeUsers:
            userHelpers = user["services"]
            for helper in userHelpers:
                if helper["enabled"] == False:
                    continue
                
                helperConfig = await systemTools.get_registered_helper(helper["id"])
                if not helperConfig or helperConfig["disabled"] or helperConfig["internal"]:
                    self.logger.warn(f"[QUEUE] Helper {helper['id']} is not available. Skipping scheduling for user {user['id']}.")
                    continue
                
                if helperConfig["admin_only"] and not user["admin"]:
                    self.logger.warn(f"[QUEUE] Helper {helper['id']} is admin-only. Skipping scheduling for non-admin user {user['id']}.")
                    continue

                if helperConfig["boot_run"]:
                    self.logger.info(f"[QUEUE] Scheduling boot_run for helper {helper['id']} for user {user['id']}.")
                    await systemTools.queue_job(
                        helper_id=helper["id"],
                        user_id=user["id"],
                        execution_time=int(datetime.datetime.now().timestamp()), # repeat bc currentTime maybe be older
                        priority=helperConfig.get("priority", 3),
                        execution_expiry=helperConfig.get("timeout", 3600),
                    )
                    continue
                
                if helperConfig["allow_execution_time_config"]:
                    scheduleExpressions = helper["schedule"]
                else:
                    scheduleExpressions = helperConfig["schedule"]

                for expression in scheduleExpressions:
                    try:
                        timestamps = await systemTools.cron_to_timestamps(expression, currentTime, lookahedTime)
                        for ts in timestamps:
                            await systemTools.queue_job(
                                helper_id=helper["id"],
                                user_id=user["id"],
                                execution_time=ts,
                                priority=helperConfig["priority"],
                                execution_expiry=helperConfig["timeout"],
                            )
                    except Exception as e:
                        self.logger.error(f"[QUEUE] Invalid cron expression '{expression}' for helper {helper['id']}. Skipping.", e)
        
    
    async def run_dispatcher(self):
        while True:
            try:
                currentTime = int(datetime.datetime.now().timestamp())
                jobs = await systemTools.get_jobs_to_run(currentTime)

                for job in jobs:
                    try:
                        jobData = await systemTools.get_job_details(job)
                        executionTime = int(jobData.get("executionTime", 0))
                        executionExpiry = int(jobData.get("executionExpiry", 0))
                        userId = jobData.get("userId")
                        helperId = jobData.get("helperId")
                        jobId = jobData.get("jobId")

                        if currentTime > executionTime + executionExpiry:
                            await systemTools.update_job_status(jobId, "expired")
                        else:
                            await systemTools.update_job_status(jobId, "running")
                            await systemTools.run_helper(helperId, userId)
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

