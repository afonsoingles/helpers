from fastapi import APIRouter, HTTPException, Request
from api.utils.pusher import InternalPusher
from utils.mongoHandler import MongoHandler
import datetime
import os
import requests


mongo = MongoHandler()
router = APIRouter()
pusher = InternalPusher()


@router.post("/devices/add")
async def addDevice(request: Request):
    json = await request.json()
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to register device")


@router.get("/history")
async def getNotificationHistory(request: Request):

    
    try:
        json = await request.json()
        device = json["deviceToken"]
    except:
        device = None
    try:
        if device:
            notifications = list(
            mongo.db.notifications.find(
                {"deviceToken": device}
            ).sort("createdAt", -1).limit(50)
            )
        else:
            notifications = list(
            mongo.db.notifications.find().sort("createdAt", -1).limit(50)
            )
        
        for notification in notifications:
            notification["_id"] = str(notification["_id"])
        return notifications
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch notification history")


@router.post("/send")
async def sendNotification(request: Request):
    auth = request.headers.get("X-Secure-Key")
    json = await request.json()

    if auth != os.environ.get("SECURE_KEY"):
        raise HTTPException(status_code=403, detail="Invalid authentication key")
    
    try:
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
        if sendAll:
            allDevices = mongo.db.devices.find()
            tokensList = []
            for device in allDevices:
                tokensList.append(device["pushToken"])
            
            pusher.bulk_push(
                tokensList,
                json["title"],
                json["body"],
                data,
                isCritical,
            )
        else:

            pusher.single_push(
                json["deviceToken"],
                json["title"],
                json["body"],
                data,
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
                "data": data,
                "deviceToken": deviceToken,
                "isCritical": isCritical,
                "status": "sent",
                "createdAt": datetime.datetime.now(datetime.timezone.utc),
            }
        )
        return {"success": True, "message": "Notification sent successfully"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Failed to send notification")

