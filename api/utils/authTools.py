from utils.mongoHandler import MongoHandler
from api.utils.redis import redisClient
import api.errors.exceptions as exceptions
from passlib.context import CryptContext
import uuid
import os
import json
import jwt
import datetime

db = MongoHandler().db
pwdContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthenticationTools:
    def __init__(self):
        self.secret = os.environ.get("JWT_SIGNING_KEY")
        self.algorithm = os.environ.get("ALGORITHM")

    # Token related

    def create_token(self, email: str) -> str:
        return jwt.encode({"sub": email}, self.secret, algorithm=self.algorithm)
    
    async def decode_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload.get("sub")
        except jwt.PyJWTError as e:
            raise exceptions.Unauthorized("Invalid authentication token", "invalid_token")
    
    # Password related
    def check_password(self, password: str, hashed: str) -> bool:
        return pwdContext.verify(password, hashed)
    
    def hash_password(self, password: str) -> str:
        return None if not password else pwdContext.hash(password)

    # User related
    async def get_user_by_email(self, email: str, bypassCache: bool = False, raw: bool = False) -> dict:
        if not bypassCache:
            lookupId = await redisClient.get(f"lookup.users.byEmail:{email}")
            cachedUser = await redisClient.get(f"userData:{lookupId}")
            if cachedUser:
                return json.loads(cachedUser)
        
        user = db.users.find_one({"email": email})
        if user and not raw:
            user.pop("passwordHash", None)
        
        if user:
            user.pop("_id", None)
            return user

    async def get_user_by_id(self, userId: str, bypassCache: bool = False, raw: bool = False) -> dict:
        if not bypassCache:
            cachedUser = await redisClient.get(f"userData:{userId}")
            if cachedUser:
                return json.loads(cachedUser)
        
        user = db.users.find_one({"id": userId})
        if user and not raw:
            user.pop("passwordHash", None)
        
        if user:
            user.pop("_id", None)
            return user

    async def get_user_by_username(self, username: str, bypassCache: bool = False, raw: bool = False) -> dict:
        if not bypassCache:
            lookupId = await redisClient.get(f"lookup.users.byUsername:{username}")
            cachedUser = await redisClient.get(f"userData:{lookupId}")
            if cachedUser:
                return json.loads(cachedUser)
        
        user = db.users.find_one({"username": username})
        if user and not raw:
            user.pop("passwordHash", None)
        
        if user:
            user.pop("_id", None)
            return user

    
    async def create_user(self, userData: dict) -> dict:

        userData = {"id": str(uuid.uuid4()), **userData}

        db.users.insert_one(userData)

        userData.pop("_id", None)
        userData.pop("passwordHash", None)
        
        await redisClient.set(f"userData:{userData['id']}", json.dumps(userData), ex=18000)
        await redisClient.set(f"lookup.users.byEmail:{userData['email']}", userData['id'], ex=18000)
        await redisClient.set(f"lookup.users.byUsername:{userData['username']}", userData['id'], ex=18000)

    async def delete_user(self, user: str) -> None:
        db.users.delete_one({"id": user["id"]})
        await redisClient.delete(f"userData:{user["id"]}")
        
        lookupByEmail = await redisClient.get(f"lookup.users.byEmail:{user["email"]}")
        if lookupByEmail:
            await redisClient.delete(f"lookup.users.byEmail:{user["email"]}")
        
        lookupByUsername = await redisClient.get(f"lookup.users.byUsername:{user["username"]}")
        if lookupByUsername:
            await redisClient.delete(f"lookup.users.byUsername:{user["username"]}")
    
    async def update_user(self, userId, data: dict) -> None:
        await self.delete_user_cache(userId)
        data["updatedAt"] = datetime.datetime.now(datetime.timezone.utc)
        db.users.update_one({"id": userId}, {"$set": data})
        await redisClient.set(f"userData:{userId}", json.dumps(data), ex=18000)
        await redisClient.set(f"lookup.users.byEmail:{data["email"]}", userId, ex=18000)
        await redisClient.set(f"lookup.users.byUsername:{data["username"]}", userId, ex=18000) 
    
    async def delete_user_cache(self, userId: str) -> None:
        user = await self.get_user_by_id(userId)
        if not user:
            return
        
        await redisClient.delete(f"userData:{userId}")
        lookupByEmail = await redisClient.get(f"lookup.users.byEmail:{user["email"]}")
        if lookupByEmail:
            await redisClient.delete(f"lookup.users.byEmail:{user["email"]}")
        
        lookupByUsername = await redisClient.get(f"lookup.users.byUsername:{user["username"]}")
        if lookupByUsername:
            await redisClient.delete(f"lookup.users.byUsername:{user["username"]}")
    
    async def get_paginated_users(self, page: int = 1, limit: int = 10, search: str = None) -> list:
        query = {}
        if search:
            query = {
                "$or": [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                    {"username": {"$regex": search, "$options": "i"}}
                ]
            }
        
        users = list(db.users.find(query).skip((page - 1) * limit).limit(limit))
        for user in users:
            user.pop("_id", None)
            user.pop("passwordHash", None)
        
        return users
    
    async def block_user(self, userId: str, reason: str) -> dict:
        user = await self.get_user_by_id(userId)
        if not user:
            raise exceptions.NotFound("User not found", "user_not_found")
        

        user["status"] = "suspended"
        if not user.get("moderationReason"):
            user["moderationReason"] = None
        user["moderationReason"] = reason
        await self.update_user(userId, user)
        
        return user
    
    async def unblock_user(self, userId: str, reason) -> dict:
        user = await self.get_user_by_id(userId)
        if not user:
            raise exceptions.NotFound("User not found", "user_not_found")
        
        user["status"] = "active"
        user["moderationReason"] = reason
        await self.update_user(userId, user)
        
        return user
    
    async def reset_password(self, userId: str, newPassword: str) -> dict:
        user = await self.get_user_by_id(userId)
        if not user:
            raise exceptions.NotFound("User not found", "user_not_found")
        
        hashedPassword = self.hash_password(newPassword)
        user["passwordHash"] = hashedPassword
        await self.update_user(userId, user)
        
        return user
    
    # Notification tokens related
    async def get_all_push_tokens(self) -> list:
        users = db.users.find({"pushConfiguration": {"$exists": True, "$ne": []}})
        pushTokens = []
        for user in users:
            if "pushConfiguration" in user:
                for config in user["pushConfiguration"]:
                    if "pushToken" in config:
                        pushTokens.append(config["pushToken"])
        return pushTokens
    
    async def get_user_push_tokens(self, userId: str) -> list:
        user = await self.get_user_by_id(userId)
        if not user or "pushConfiguration" not in user:
            return []
        
        pushTokens = []
        for config in user["pushConfiguration"]:
            if "pushToken" in config:
                pushTokens.append(config["pushToken"])
        
        return pushTokens