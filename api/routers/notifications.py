from fastapi import APIRouter, Request
from api.utils.pusher import InternalPusher
from utils.mongoHandler import MongoHandler
from api.utils.authTools import AuthenticationTools
from api.utils.notificationTools import NotificationTools
from api.decorators.auth import authRequired
import api.errors.exceptions as exceptions
import datetime
import os
import uuid
import pytz



mongo = MongoHandler()
router = APIRouter()
pusher = InternalPusher()
authTools = AuthenticationTools()
notificationTools = NotificationTools()


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


# Version 2
@router.post("/v2/notifications/devices")
@authRequired
async def v2_addDevice(request: Request):
    try:
        json = await request.json()
    except:
        raise exceptions.BadRequest(message="Invalid JSON data provided", type="invalid_json")
    
    deviceData = {
        "deviceId": str(uuid.uuid4()),
        "deviceName": json.get("name"),
        "pushToken": json.get("pushToken"),
        "allowCritical": json.get("allowsCritical", False),
        "platform": json.get("platform", "unknown"),
        "lastSeenAt": datetime.datetime.now(pytz.timezone(os.environ.get("TZ", "UTC"))).timestamp()
    }

    if not deviceData["pushToken"] or not deviceData["deviceName"]:
        raise exceptions.BadRequest(message="pushToken and name are required", type="missing_fields")
    
    for registeredDevice in request.state.user.get("pushConfiguration", []):
        if registeredDevice["deviceName"] == deviceData["deviceName"] or registeredDevice["pushToken"] == deviceData["pushToken"]:
            raise exceptions.BadRequest(message="Device with the same name or pushToken already exists", type="duplicate_device")

    request.state.user["pushConfiguration"].append(deviceData)
    await authTools.update_user(request.state.user["id"], request.state.user)

    return {"success": True, "message": "The device was registered successfully and is now able to receive push notifications.", "deviceId": str(deviceData["deviceId"])}


@router.put("/v2/notifications/devices/{deviceId}")
@authRequired
async def v2_updateDevice(request: Request, deviceId: str):
    try:
        json = await request.json()
    except:
        raise exceptions.BadRequest(message="Invalid JSON data provided", type="invalid_json")
    
    deviceData = {
        "deviceName": json.get("name"),
        "pushToken": json.get("pushToken"),
        "allowCritical": json.get("allowsCritical", False),
        "platform": json.get("platform", "unknown"),
        "lastSeenAt": datetime.datetime.now(pytz.timezone(os.environ.get("TZ", "UTC"))).timestamp()
    }

    if not deviceData["pushToken"] or not deviceData["deviceName"]:
        raise exceptions.BadRequest(message="pushToken and name are required", type="missing_fields")
    
    for registeredDevice in request.state.user.get("pushConfiguration", []):
        if registeredDevice["deviceId"] == deviceId:
            request.state.user["pushConfiguration"] = [
                device if device["deviceId"] != deviceId else {**device, **deviceData}
                for device in request.state.user["pushConfiguration"]
            ]
            await authTools.update_user(request.state.user["id"], request.state.user)
            return {"success": True, "message": "The device was updated successfully."}
    
    raise exceptions.NotFound(message="Device not found", type="device_not_found")


@router.post("/v2/notifications/devices/{deviceId}/checkIn")
@authRequired
async def v2_checkInDevice(request: Request, deviceId: str):
    for registeredDevice in request.state.user.get("pushConfiguration", []):
        if registeredDevice["deviceId"] == deviceId:
            registeredDevice["lastSeenAt"] = datetime.datetime.now(pytz.timezone(os.environ.get("TZ", "UTC"))).timestamp()
            await authTools.update_user(request.state.user["id"], request.state.user)
            return {"success": True, "message": "Device is alive!"}
    
    raise exceptions.NotFound(message="Device not found", type="device_not_found")


@router.delete("/v2/notifications/devices/{deviceId}")
@authRequired
async def v2_deleteDevice(request: Request, deviceId: str):
    for registeredDevice in request.state.user.get("pushConfiguration", []):
        if registeredDevice["deviceId"] == deviceId:
            request.state.user["pushConfiguration"] = [
                device for device in request.state.user["pushConfiguration"] if device["deviceId"] != deviceId
            ]
            await authTools.update_user(request.state.user["id"], request.state.user)
            return {"success": True, "message": "The device was removed successfully."}
    
    raise exceptions.NotFound(message="Device not found", type="device_not_found")


@router.get("/v2/notifications")
@authRequired
async def v2_getNotifications(request: Request, page: int = 1, limit: int = 20):
    try:
        int(request.query_params.get("page", 1))
        int(request.query_params.get("limit", 20))
    except:
        raise exceptions.BadRequest(message="Invalid pagination parameters", type="invalid_pagination")

    if page < 1 or limit < 1:
        raise exceptions.BadRequest(message="Page and limit must be positive integers", type="invalid_pagination")

    

    notificationsList = await notificationTools.get_paginated_user_notifications(request.state.user["id"], page, limit)

    return {"success": True, "notifications": notificationsList}


@router.post("/v2/notifications/send") # admin endpoint - authenticates with server secure key
async def v2_sendNotification(request: Request):
    secureKey = request.headers.get("X-Secure-Key")
    json = await request.json()

    if secureKey != os.environ.get("SECURE_KEY"):
        raise exceptions.Unauthorized(message="Invalid secure key", type="invalid_key")
    
    if not json.get("title") or not json.get("body") or not json.get("to") or not json.get("from"):
        raise exceptions.BadRequest(message="Missing required parameters", type="missing_fields")
    
    if json["to"] == "broadcast":
        allTokens = await authTools.get_all_push_tokens()
        pusher.bulk_push(
            allTokens,
            json["title"],
            json["body"],
            json.get("sound", "default"),
            json.get("data", {}),
            json.get("ttl", 1),
            json.get("isCritical", False),
        )
        await notificationTools.register_notification(
            sender="system",
            recipient="broadcasted",
            title=json["title"],
            body=json["body"],
            sound=json.get("sound", "default"),
            data=json.get("data", {}),
            ttl=json.get("ttl", 1),
            isCritical=json.get("isCritical", False),
        )
        return {"success": True, "message": "This message was broadcasted successfully to all users."}


    notificationData = {
        "sender": json.get("from", "system"),
        "recipient": json["to"],
        "title": json["title"],
        "body": json["body"],
        "sound": json.get("sound", "default"),
        "data": json.get("data", {}),
        "ttl": json.get("ttl", 1),
        "isCritical": json.get("isCritical", False),
    }

    userPushTokens = await authTools.get_user_push_tokens(json["to"])

    if not userPushTokens:
        raise exceptions.NotFound(message="Push configuration not found!", type="push_config_not_found")
    
    pusher.bulk_push(
        userPushTokens,
        notificationData["title"],
        notificationData["body"],
        notificationData["sound"],
        notificationData["data"],
        notificationData["ttl"],
        notificationData["isCritical"],
    )
    
    notificationData["createdAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await notificationTools.register_notification(
        sender=notificationData["sender"],
        recipient=notificationData["recipient"],
        title=notificationData["title"],
        body=notificationData["body"],
        sound=notificationData["sound"],
        data=notificationData["data"],
        ttl=notificationData["ttl"],
        isCritical=notificationData["isCritical"],
    )
    return {"success": True, "message": "Notification sent successfully"}



@router.post("/v2/notifications/admin/send") # only the admin site uses this
@authRequired(admin=True)
async def v2_sendNotification(request: Request):

    json = await request.json()


    
    if not json.get("title") or not json.get("body") or not json.get("to") or not json.get("from"):
        raise exceptions.BadRequest(message="Missing required parameters", type="missing_fields")
    
    if json["to"] == "broadcast":
        allTokens = await authTools.get_all_push_tokens()
        pusher.bulk_push(
            allTokens,
            json["title"],
            json["body"],
            json.get("sound", "default"),
            json.get("data", {}),
            json.get("ttl", 1),
            json.get("isCritical", False),
        )
        await notificationTools.register_notification(
            sender="system",
            recipient="broadcasted",
            title=json["title"],
            body=json["body"],
            sound=json.get("sound", "default"),
            data=json.get("data", {}),
            ttl=json.get("ttl", 1),
            isCritical=json.get("isCritical", False),
        )
        return {"success": True, "message": "This message was broadcasted successfully to all users."}


    notificationData = {
        "sender": json.get("from", "system"),
        "recipient": json["to"],
        "title": json["title"],
        "body": json["body"],
        "sound": json.get("sound", "default"),
        "data": json.get("data", {}),
        "ttl": json.get("ttl", 1),
        "isCritical": json.get("isCritical", False),
    }

    userPushTokens = await authTools.get_user_push_tokens(json["to"])

    if not userPushTokens:
        raise exceptions.NotFound(message="Push configuration not found!", type="push_config_not_found")
    
    pusher.bulk_push(
        userPushTokens,
        notificationData["title"],
        notificationData["body"],
        notificationData["sound"],
        notificationData["data"],
        notificationData["ttl"],
        notificationData["isCritical"],
    )
    
    notificationData["createdAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await notificationTools.register_notification(
        sender=notificationData["sender"],
        recipient=notificationData["recipient"],
        title=notificationData["title"],
        body=notificationData["body"],
        sound=notificationData["sound"],
        data=notificationData["data"],
        ttl=notificationData["ttl"],
        isCritical=notificationData["isCritical"],
    )
    return {"success": True, "message": "Notification sent successfully"}