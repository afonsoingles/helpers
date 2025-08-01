from utils.mongoHandler import MongoHandler
from api.utils.redis import redisClient
import api.errors.exceptions as exceptions
import jwt

db = MongoHandler().db


class NotificationTools:


    async def get_paginated_user_notifications(self, userId, page: int = 1, limit: int = 20) -> list:
        notifications = list(
            db.notifications.find({"to": userId})
            .sort("createdAt", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        for notification in notifications:
            notification.pop("_id", None)

        return notifications
