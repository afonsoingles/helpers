from fastapi import HTTPException
from utils.mongoHandler import MongoHandler
from utils.redis import redisClient
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
            raise HTTPException(status_code=401, detail="Token inválido")

    async def get_user(self, email: str):
        cached = await redisClient.get(f"UserData:{email}")
        if cached:
            user = json.loads(cached)
            if user.get("blocked"):
                raise HTTPException(status_code=403, detail="Utilizador bloqueado")
            return user

        user = db.users.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=404, detail="Utilizador não encontrado")

        if user.get("blocked"):
            await redisClient.set(f"userData:{email}", json.dumps({"blocked": True}), ex=600)
            raise HTTPException(status_code=403, detail="Utilizador bloqueado")

        user.pop("_id", None)
        await redisClient.set(f"userData:{email}", json.dumps(user), ex=300)
        return user
