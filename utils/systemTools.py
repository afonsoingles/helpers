from api.utils.redis import redisClient
import croniter
import datetime
import asyncio
import json

class SystemTools:

    async def register_helper(self, helper_id: str, helper_value: dict):
        await redisClient.set(f"internalAvailableHelpers:{helper_id}", helper_value)
    
    async def get_registered_helper(self, helper_id: str):
        redisResult = await redisClient.exists(f"internalAvailableHelpers:{helper_id}")
        if not redisResult:
            return None
        return json.loads(redisResult)
    
    async def clear_helpers(self):
        keys = await redisClient.keys("internalAvailableHelpers:*")
        if keys:
            await redisClient.delete(*keys)

    async def get_all_helpers(self):
        keys = await redisClient.keys("internalAvailableHelpers:*")
        helpers = []
        for key in keys:
            helperData = await redisClient.get(key)
            if helperData:
                helpers.append(json.loads(helperData))
        return helpers
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