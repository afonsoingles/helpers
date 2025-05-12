from fastapi import APIRouter, HTTPException, Request
from api.utils.pusher import InternalPusher
from utils.mongoHandler import MongoHandler
import datetime
import os



mongo = MongoHandler()
router = APIRouter()
pusher = InternalPusher()


@router.post("/github")
async def githubWebhook(request: Request):
    print(request.headers)
    print(request.json())
