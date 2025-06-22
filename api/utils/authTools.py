from utils.mongoHandler import MongoHandler
from api.utils.redis import redisClient
import api.errors.exceptions as exceptions
from passlib.context import CryptContext
import uuid
import os
import json
import jwt

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