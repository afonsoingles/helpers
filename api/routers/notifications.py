from fastapi import APIRouter, Request
from api.utils.pusher import InternalPusher
from utils.mongoHandler import MongoHandler
import api.errors.exceptions as exceptions
import datetime
import os



mongo = MongoHandler()
router = APIRouter()
pusher = InternalPusher()


@router.post("/v1/notifications/devices/add")
async def addDevice(request: Request):
    json = await request.json()

    mongo.db.devices.update_one(
        {"pushToken": json["pushToken"]},
        {
        "$set": {
            "deviceName": json["deviceName"],
            "pushToken": json["pushToken"],
            "platform": json["platform"],
            "supportsCritical": json["supportsCritical"],
            "lastSeen": datetime.datetime.now(datetime.timezone.utc),
        }
    },
    upsert=True,
    )
    return {"success": True, "message": "Device registered successfully"}


@router.get("/v1/notifications/devices")
async def getDevices(request: Request):
    auth = request.headers.get("X-Secure-Key")

    if auth != os.environ.get("SECURE_KEY"):
        raise exceptions.Unauthorized(message="Invalid Authentication key", type="invalid_key")
    
    

    devices = list(mongo.db.devices.find())
    for device in devices:
         device["_id"] = str(device["_id"])
    return devices


@router.get("/v1/notifications/history")
async def getNotificationHistory(request: Request):

    
    try:
        json = await request.json()
        device = json["deviceToken"]
    except:
        device = None

    if device:
        notifications = list(
            mongo.db.notifications.find(
                {"$or": [{"deviceToken": device}, {"deviceToken": "all"}]}
            ).sort("createdAt", -1).limit(50)
        )
    else:
        notifications = list(
            mongo.db.notifications.find().sort("createdAt", -1).limit(50)
        )
    
    for notification in notifications:
        notification["_id"] = str(notification["_id"])
    return notifications


@router.post("/v1/notifications/send")
async def sendNotification(request: Request):
    auth = request.headers.get("X-Secure-Key")
    json = await request.json()

    if auth != os.environ.get("SECURE_KEY"):
        raise exceptions.Unauthorized(message="Invalid Authentication key", type="invalid_key")
    

    try:
        isCritical = json["isCritical"]
    except:
        isCritical = False

    try:
        data = json["data"]
    except:
        data = {}
    
    try:
        sendAll = json["sendAll"]
    except:
        sendAll = False
    
    try:
        ttl = json["ttl"]
    except:
        ttl = 1

    try:
        sound = json["sound"]
    except:
        sound = "default"
    if sendAll:
        allDevices = mongo.db.devices.find()
        tokensList = []
        for device in allDevices:
            tokensList.append(device["pushToken"])
        
        pusher.bulk_push(
            tokensList,
            json["title"],
            json["body"],
            sound,
            data,
            ttl,
            isCritical,
        )
    else:
        pusher.single_push(
            json["deviceToken"],
            json["title"],
            json["body"],
            sound,
            data,
            ttl,
            isCritical,
        )

    try:
        deviceToken = json["deviceToken"]
    except:
        deviceToken = "all"
    
    mongo.db.notifications.insert_one(
        {
            "title": json["title"],
            "body": json["body"],
            "sound": sound,
            "data": data,
            "deviceToken": deviceToken,
            "isCritical": isCritical,
            "status": "sent",
            "createdAt": datetime.datetime.now(datetime.timezone.utc),
        }
    )
    return {"success": True, "message": "Notification sent successfully"}


