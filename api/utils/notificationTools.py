from utils.mongoHandler import MongoHandler
from api.utils.redis import redisClient
import datetime
import uuid

db = MongoHandler().db


class NotificationTools:


    async def get_paginated_user_notifications(self, userId, ts, page: int = 1, limit: int = 20) -> list:
        notifications = list(
            db.notifications.find(
            {
                "$and": [
                {"$or": [{"to": userId}, {"to": "broadcasted"}]},
                {"createdAt": {"$gt": datetime.datetime.fromtimestamp(ts).isoformat()}},
                ]
            }
            )
            .sort("createdAt", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        for notification in notifications:
            notification.pop("_id", None)

        return notifications
    
    async def register_notification(self, sender, recipient, title, body, sound, data, ttl, isCritical):
        notification = {
            "id": str(uuid.uuid4()),
            "from": sender,
            "to": recipient,
            "title": title,
            "body": body,
            "sound": sound,
            "data": data,
            "ttl": ttl,
            "isCritical": isCritical,
            "channel": "default" if not isCritical else "critical",
            "createdAt": str(datetime.datetime.now(datetime.UTC)),
        }
        db.notifications.insert_one(notification)
        await redisClient.set(
            f"notification:{notification['id']}",
            str(notification),
            ex=ttl * 60 if ttl else 5600,
        )
