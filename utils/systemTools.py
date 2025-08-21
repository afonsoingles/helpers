from api.utils.redis import redisClient


class SystemTools:

    async def register_helper(self, helperId: str, helperValue: dict):
        await redisClient.set(f"internalAvailableHelpers:{helperId}", helperValue)
    
