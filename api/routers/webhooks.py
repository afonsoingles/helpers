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

    githubHook = request.headers.get("X-GitHub-Hook-ID")

    if str(githubHook) != str(os.environ.get("GITHUB_HOOK_ID")):
        raise HTTPException(status_code=403, detail="Invalid GitHub Hook ID")
    
    print("[IMPORTANT - CRITICAL] Restarting to perform update")
    os.system(f"cd bash scripts/update.sh")
    return {"message": "Update script executed successfully"}
