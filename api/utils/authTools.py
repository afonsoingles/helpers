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
            raise exceptions.Unauthorized("Invalid or expired token", "invalid_token")
    
    # Password related
    def check_password(self, password: str, hashed: str) -> bool:
        return pwdContext.verify(password, hashed)
    
    def hash_password(self, password: str) -> str:
        return None if password is None else pwdContext.hash(password)

    # User related
    async def get_user_by_email(self, email: str) -> dict:
        lookupId = redisClient.get(f"lookup.users.byEmail:{email}")
        cachedUser = await redisClient.get(f"userData:{lookupId}")
        if cachedUser:
            return json.loads(cachedUser)
        
        user = await db.users.find_one({"email": email})
        if user:
            user.pop("_id", None)
            user.pop("passwordHash", None)
        
        return user if user else None
    
    async def get_user_by_id(self, userId: str) -> dict:
        cachedUser = await redisClient.get(f"userData:{userId}")
        if cachedUser:
            return json.loads(cachedUser)
        
        user = await db.users.find_one({"id": userId})
        if user:
            user.pop("_id", None)
            user.pop("passwordHash", None)
        
        return user if user else None
    
    async def get_user_by_username(self, username: str) -> dict:
        lookupId = redisClient.get(f"lookup.users.byUsername:{username}")
        cachedUser = await redisClient.get(f"userData:{lookupId}")
        if cachedUser:
            return json.loads(cachedUser)
        
        user = await db.users.find_one({"username": username})
        if user:
            user.pop("_id", None)
            user.pop("passwordHash", None)
        return user if user else None
    
    async def create_user(self, userData: dict) -> dict:

        userData["id"] = str(uuid.uuid4())

        db.users.insert_one(userData)

        userData.pop("passwordHash", None)
        
        redisClient.set(f"userData:{userData['id']}", json.dumps(userData))
        redisClient.set(f"lookup.users.byEmail:{userData['email']}", userData['id'])
        redisClient.set(f"lookup.users.byUsername:{userData['username']}", userData['id'])