from utils.mongoHandler import MongoHandler
from api.utils.redis import redisClient
import api.errors.exceptions as exceptions
import os
import json
import jwt

db = MongoHandler().db

class AuthenticationDb:
    def __init__(self):
        self.secret = os.environ.get("SECRET_KEY")
        self.algorithm = os.environ.get("ALGORITHM")

    async def decode_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload.get("sub")
        except jwt.PyJWTError:
            raise exceptions.Unauthorized("Invalid or expired token", "invalid_token")
    async def get_user(self, email: str):
        cached = await redisClient.get(f"UserData:{email}")
        if cached:
            user = json.loads(cached)
            if user.get("blocked"):
                raise exceptions.Forbidden("User blocked", "user_blocked")
            return user

        user = db.users.find_one({"email": email})
        if not user:
            raise exceptions.NotFound("User not found", "user_not_found")

        if user.get("blocked"):
            await redisClient.set(f"userData:{email}", json.dumps({"blocked": True}), ex=600)
            raise exceptions.Forbidden("User blocked", "user_blocked")
        user.pop("_id", None)
        await redisClient.set(f"userData:{email}", json.dumps(user), ex=300)
        return user
