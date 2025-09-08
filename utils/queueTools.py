from api.utils.redis import redisClient
import uuid
import croniter
import datetime
import asyncio
from utils.logger import Logger
from utils.systemTools import SystemTools
from api.utils.authTools import AuthenticationTools

systemTools = SystemTools()
authTools = AuthenticationTools()


class QueueTools:
    def __init__(self, logger):
        self.logger = logger

    async def queue_job(self, helper_id: str, user_id: str, execution_time: int, priority: int, execution_expiry: int):
        jobData = {
            "executionId": str(uuid.uuid4()),
            "userId": user_id,
            "helperId": helper_id,
            "executionTime": execution_time, # scheduled time
            "executionScore": execution_time * 10 + (6 - priority),
            "priority": priority,
            "executionExpiry": execution_expiry,
            "status": "queued"
        }

        await redisClient.hset(f"executionJob:{jobData['executionId']}", mapping=jobData)

        await redisClient.zadd("internalExecutionQueue", {jobData['executionId']: jobData['executionScore']})

    async def dequeue_job(self, execution_id: str):
        await redisClient.zrem("internalExecutionQueue", execution_id)
        await redisClient.hset(f"executionJob:{execution_id}", mapping={"status": "cancelled"})
    
    async def update_queue_for_user(self, user_id):
        userData = await authTools.get_user_by_id(user_id)
        userJobs = await redisClient.zrange("internalExecutionQueue", 0, -1)
        for job in userJobs:
            job = str(job).replace("executionJob:", "")
            jobDetails = await self.get_job_details(job)
            if jobDetails.get("userId") == user_id:
                await self.dequeue_job(jobDetails["executionId"])
        
        userHelpers = userData["services"]
        currentTime = int(datetime.datetime.now().timestamp())
        lookahedTime = currentTime + 2 * 3600  # 2h

        for helper in userHelpers:
            if helper["enabled"] == False:
                continue
            
            if userData["region"] not in helperConfig["region_lock"] and helperConfig["region_lock"] != ["*"]:
                self.logger.warn(f"[QUEUE] Helper {helper['id']} is not available in user {user_id} region ({userData["region"]}). Skipping scheduling.")
                continue
            helperConfig = await systemTools.get_registered_helper(helper["id"])
            if not helperConfig or helperConfig["disabled"] or helperConfig["internal"]:
                self.logger.warn(f"[QUEUE] Helper {helper['id']} is not available. Skipping scheduling for user {user_id}.")
                continue
            
            if helperConfig["admin_only"] and not userData["admin"]:
                self.logger.warn(f"[QUEUE] Helper {helper['id']} is admin-only. Skipping scheduling for non-admin user {user_id}.")
                continue

            if helperConfig["boot_run"]:
                continue
            
            if helperConfig["allow_execution_time_config"]:
                scheduleExpressions = helper["schedule"]
            else:
                scheduleExpressions = helperConfig["schedule"]

            for expression in scheduleExpressions:
                try:
                    timestamps = systemTools.cron_to_timestamps(expression, currentTime, lookahedTime)
                    for ts in timestamps:
                        await self.queue_job(
                            helper_id=helper["id"],
                            user_id=user_id,
                            execution_time=ts,
                            priority=helperConfig["priority"],
                            execution_expiry=helperConfig["timeout"],
                        )
                except Exception as e:
                    self.logger.error(f"[QUEUE] Invalid cron expression '{expression}' for helper {helper['id']}. Skipping.", e)
        
    async def get_jobs_to_run(self, time: int):
        jobs = await redisClient.zrangebyscore("internalExecutionQueue", "-inf", time * 10)
        valid_jobs = []
        for job in jobs:
            job_details = await self.get_job_details(job)
            if job_details["status"] == "queued":
                valid_jobs.append(job)
        return valid_jobs
        
    async def get_job_details(self, execution_id: str):
        return await redisClient.hgetall(f"executionJob:{execution_id}")
    
    async def update_job_status(self, id: str, status: str):
        await redisClient.hset(f"executionJob:{id}", "status", status)
    
    async def clear_queue(self):
        keys = await redisClient.keys("executionJob:*")
        if keys:
            await redisClient.delete(*keys)
        await redisClient.delete("internalExecutionQueue")

    async def build_initial_execution_queue(self):
        self.logger.info("[QUEUE] Building initial execution queue...")
        activeUsers = await authTools.get_all_active_users()
        allHelpers = await systemTools.get_all_helpers()
        currentTime = int(datetime.datetime.now().timestamp())
        lookahedTime = currentTime + 2 * 3600  # 2h
        
        for helper in allHelpers:
            if helper["internal"] == True and not helper["disabled"]:

                if helper["boot_run"]:
                    self.logger.info(f"[QUEUE] Scheduling boot_run for internal helper {helper['id']}.")
                    await self.queue_job(
                        helper_id=helper["id"],
                        user_id="internal",
                        execution_time=int(datetime.datetime.now().timestamp()),
                        priority=helper.get("priority", 3),
                        execution_expiry=helper.get("timeout", 3600),
                    )
                
                for expression in helper["schedule"]:
                    try:
                        timestamps = systemTools.cron_to_timestamps(expression, currentTime, lookahedTime)
                        for ts in timestamps:
                            await self.queue_job(
                                helper_id=helper["id"],
                                user_id="internal",
                                execution_time=ts,
                                priority=helper.get("priority", 3),
                                execution_expiry=helper.get("timeout", 3600),
                            )

                            self.logger.info(f"[QUEUE] Scheduled internal helper {helper['id']} at {ts}.")
                    except Exception as e:
                        self.logger.error(f"[QUEUE] Invalid cron expression '{expression}' for internal helper {helper['id']}. Skipping.", e)

        self.logger.info("[QUEUE] Done processing internal helpers. Processing user helpers...")

        for user in activeUsers:
            try:
                self.logger.info(f"[QUEUE] Processing user {user['id']}...")
                userHelpers = user["services"]
                for helper in userHelpers:
                    self.logger.info(f"[QUEUE] Processing helper {helper['id']} for user {user['id']}...")
                    if not helper["enabled"]:
                        self.logger.info(f"[QUEUE] Helper {helper['id']} is disabled for user {user['id']}. Skipping.")
                        continue
                    helperConfig = await systemTools.get_registered_helper(helper["id"])
                    if not helperConfig or helperConfig["disabled"] or helperConfig["internal"]:
                        self.logger.warn(f"[QUEUE] Helper {helper['id']} is not available. Skipping scheduling for user {user['id']}.")
                        continue
                    
                    if user["region"] not in helperConfig["region_lock"] and helperConfig["region_lock"] != ["*"]:
                        self.logger.warn(f"[QUEUE] Helper {helper['id']} is not available in user {user['id']} region ({user['region']}). Skipping scheduling.")
                        continue

                    if helperConfig["admin_only"] and not user["admin"]:
                        self.logger.warn(f"[QUEUE] Helper {helper['id']} is admin-only. Skipping scheduling for non-admin user {user['id']}.")
                        continue

                    if helperConfig["boot_run"]:
                        self.logger.info(f"[QUEUE] Scheduling boot_run for helper {helper['id']} for user {user['id']}.")
                        await self.queue_job(
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
                            timestamps = systemTools.cron_to_timestamps(expression, currentTime, lookahedTime)
                            for ts in timestamps:
                                await self.queue_job(
                                    helper_id=helper["id"],
                                    user_id=user["id"],
                                    execution_time=ts,
                                    priority=helperConfig["priority"],
                                    execution_expiry=helperConfig["timeout"],
                                )
                        except Exception as e:
                            self.logger.error(f"[QUEUE] Invalid cron expression '{expression}' for helper {helper['id']}. Skipping.", e)
            except Exception as e:
                self.logger.error(f"[QUEUE] Error processing user {user['id']}. Skipping", e)

        self.logger.info("[QUEUE] Finished building initial execution queue.")
    
    async def queue_updater_realtime(self):
        self.logger.info("[REALTIME QUEUE] Starting real-time queue updater...")
        while True:
            try:
                currentTime = int(datetime.datetime.now().timestamp())
                lookAhead = currentTime + 10 * 60  # 10m
                allHelpers = await systemTools.get_all_helpers()
                activeUsers = await authTools.get_all_active_users()

                for user in activeUsers:
                    try:
                        self.logger.info(f"[REALTIME QUEUE] Processing user {user['id']}...")
                        userHelpers = user["services"]
                        for helper in userHelpers:
                            self.logger.info(f"[REALTIME QUEUE] Processing helper {helper['id']} for user {user['id']}...")
                            if not helper["enabled"]:
                                self.logger.info(f"[REALTIME QUEUE] Helper {helper['id']} is disabled for user {user['id']}. Skipping.")
                                continue
                            helperConfig = await systemTools.get_registered_helper(helper["id"])

                            if helperConfig["boot_run"]:
                                continue
                            
                            if user["region"] not in helperConfig["region_lock"] and helperConfig["region_lock"] != ["*"]:
                                self.logger.warn(f"[REALTIME QUEUE] Helper {helper['id']} is not available in user {user['id']} region ({user['region']}). Skipping scheduling.")
                                continue

                            if not helperConfig or helperConfig["disabled"] or helperConfig["internal"]:
                                self.logger.warn(f"[REALTIME QUEUE] Helper {helper['id']} is not available. Skipping scheduling for user {user['id']}.")
                                continue

                            if helperConfig["admin_only"] and not user["admin"]:
                                self.logger.warn(f"[REALTIME QUEUE] Helper {helper['id']} is admin-only. Skipping scheduling for non-admin user {user['id']}.")
                                continue

                            if helperConfig["allow_execution_time_config"]:
                                schedule_expressions = helper["schedule"]
                            else:
                                schedule_expressions = helperConfig["schedule"]

                            for expression in schedule_expressions:

                                try:
                                    timestamps = systemTools.cron_to_timestamps(expression, currentTime, lookAhead)
                                    for ts in timestamps:
                                        # Check if the job is already scheduled
                                        existingJobs = await self.get_jobs_to_run(lookAhead)
                                        

                                        jobAlreadyScheduled = False
                                        for job in existingJobs:
                                            jobDetails = await self.get_job_details(job)
                                            if jobDetails.get("helperId") == helper["id"] and jobDetails.get("userId") == user["id"] and int(jobDetails.get("executionTime")) == int(ts):
                                                self.logger.info(f"[REALTIME QUEUE] Job for helper {helper['id']} and user {user['id']} at {ts} already scheduled. Skipping.")
                                                jobAlreadyScheduled = True
                                                break

                                        if not jobAlreadyScheduled:
                                            # Schedule the job if not already scheduled
                                            await self.queue_job(
                                                helper_id=helper["id"],
                                                user_id=user["id"],
                                                execution_time=ts,
                                                priority=helperConfig.get("priority", 3),
                                                execution_expiry=helperConfig.get("timeout", 3600),
                                            )
                                            self.logger.info(f"[REALTIME QUEUE] Scheduled job for helper {helper['id']} and user {user['id']} at {ts}.")
                                except Exception as e:
                                    self.logger.error(f"[REALTIME QUEUE] Invalid cron expression '{expression}' for helper {helper['id']}. Skipping.", e)
                    except Exception as e:
                        self.logger.error(f"[REALTIME QUEUE] Error processing user {user['id']}. Skipping.", e)
                
                self.logger.info(f"[REALTIME QUEUE] Done processing user helpers. Processing internal helpers...")

                for helper in allHelpers:
                    if helper["internal"] == True and not helper["disabled"]:
                        self.logger.info(f"[REALTIME QUEUE] Processing internal helper {helper['id']}...")
                        for expression in helper["schedule"]:
                            try:
                                timestamps = systemTools.cron_to_timestamps(expression, currentTime, lookAhead)
                                existingJobs = await self.get_jobs_to_run(lookAhead)
                                for ts in timestamps:
                                    # Check if the job is already scheduled
                                    jobAlreadyScheduled = False
                                    for job in existingJobs:
                                        jobDetails = await self.get_job_details(job)
                                        if jobDetails.get("helperId") == helper["id"] and int(jobDetails.get("executionTime")) == int(ts) and jobDetails.get("userId") == "internal":
                                            self.logger.info(f"[REALTIME QUEUE] Job for internal helper {helper['id']} at {ts} already scheduled. Skipping.")
                                            jobAlreadyScheduled = True
                                            break
                                    
                                    if not jobAlreadyScheduled:
                                        # Schedule the job if not already scheduled
                                        await self.queue_job(
                                            helper_id=helper["id"],
                                            user_id="internal",
                                            execution_time=ts,
                                            priority=helper.get("priority", 3),
                                            execution_expiry=helper.get("timeout", 3600),
                                        )
                                        self.logger.info(f"[REALTIME QUEUE] Scheduled job for internal helper {helper['id']} at {ts}.")
                            except Exception as e:
                                self.logger.error(f"[REALTIME QUEUE] Invalid cron expression '{expression}' for internal helper {helper['id']}. Skipping.", e)
                
                self.logger.info("[REALTIME QUEUE] Done processing internal helpers.")
                self.logger.info("[REALTIME QUEUE] Expanded execution queue by 10 minutes.")
                await asyncio.sleep(600)  # Run every 10 minutes
            except Exception as e:
                self.logger.error("[REALTIME QUEUE] Error in real-time queue updater.", e)
