from api.utils.redis import redisClient
import uuid
import croniter
import datetime
import asyncio


class SystemTools:

    async def register_helper(self, helper_id: str, helper_value: dict):
        await redisClient.set(f"internalAvailableHelpers:{helper_id}", helper_value)
    
    async def get_registered_helper(self, helper_id: str):
        return await redisClient.get(f"internalAvailableHelpers:{helper_id}")
    
    async def clear_helpers(self):
        keys = await redisClient.keys("internalAvailableHelpers:*")
        if keys:
            await redisClient.delete(*keys)
    
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
    
    async def get_jobs_to_run(self, time: int):
        job_ids = await redisClient.zrangebyscore("internalExecutionQueue", "-inf", time)
        return [job_id.decode("utf-8").replace("executionJob:", "") for job_id in job_ids]
        
    async def get_job_details(self, execution_id: str):
        return await redisClient.hgetall(f"executionJob:{execution_id}")
    
    async def update_job_status(self, id: str, status: str):
        await redisClient.hset(f"executionJob:{id}", "status", status)

    async def cron_to_timestamps(self, expression, start, end):
        base = datetime.datetime.fromtimestamp(start)
        cron = croniter.croniter(expression, base)
        times = []

        while True:
            nextTime = cron.get_next(datetime.datetime)
            if nextTime.timestamp() > end:
                break

            times.append(int(nextTime.timestamp()))
        
        return times
        
    async def run_helper(self, helperId, userData):

        helperModule = __import__(f"helpers.{helperId}", fromlist=[helperId])
        helper = getattr(helperModule, "BaseHelper")(user=userData)

        asyncio.create_task(helper.run())
        return