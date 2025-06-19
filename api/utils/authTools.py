from utils.mongoHandler import MongoHandler
from api.utils.redis import redisClient
import api.errors.exceptions as exceptions
from passlib.context import CryptContext
import os
import json
import jwt

db = MongoHandler().db
pwdContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthenticationTools:
    def __init__(self):
        self.secret = os.environ.get("JWT_SIGNING_KEY")
        self.algorithm = os.environ.get("ALGORITHM")

    def create_token(self, email: str) -> str:
        return jwt.encode({"sub": email}, self.secret, algorithm=self.algorithm)
    
    async def decode_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload.get("sub")
        except jwt.PyJWTError as e:
            raise exceptions.Unauthorized("Invalid or expired token", "invalid_token")
        
    async def get_user(self, email: str, ignore_cache: bool = False):
        if not ignore_cache:
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
            await redisClient.set(f"UserData:{email}", json.dumps({"blocked": True}), ex=600)
            raise exceptions.Forbidden("User blocked", "user_blocked")
        user.pop("_id", None)
        user.pop("password", None)
        await redisClient.set(f"UserData:{email}", json.dumps(user), ex=600)
        return user

    async def create_user(self, username: str, email: str, password: str):
        
        user = {
            "id": int(db.users.count_documents({}) + 1),
            "username": username,
            "email": email,
            "password": self.hash_password(password),
            "blocked": False
        }
        db.users.insert_one(user)
        user.pop("_id", None)
        user.pop("password", None)
        await redisClient.set(f"UserData:{email}", json.dumps(user), ex=300)
        return user
    
    def hash_password(self, password: str) -> str:
        return pwdContext.hash(password)

    def check_password(self, password: str, hashed: str) -> bool:
        return pwdContext.verify(password, hashed)
    
    async def invalidate_cache(self, email: str):
        await redisClient.delete(f"UserData:{email}")
    