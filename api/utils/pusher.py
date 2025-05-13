import requests


class InternalPusher:
    
    def single_push(self, to, title, body, data, ttl, isCritical=False):
        try:
            response = requests.post(
                "https://exp.host/--/api/v2/push/send",
                json={
                    "to": to,
                    "sound": "critical" if isCritical else "default",
                    "title": title,
                    "body": body,
                    "data": data,
                    "interruptionLevel": "critical" if isCritical else "active",
                    "badge": 0,
                    "ttl": ttl,
                    "priority": "high",

                }
            )
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to send push notification: {e}")
    
    def bulk_push(self, tokens, title, body, data, ttl, isCritical=False):
        try:
            response = requests.post(
                "https://exp.host/--/api/v2/push/send",
                json={
                    "to": tokens,
                    "sound": "critical" if isCritical else "default",
                    "title": title,
                    "body": body,
                    "data": data,
                    "interruptionLevel": "critical" if isCritical else "active",
                    "badge": 0,
                    "ttl": ttl,
                    "priority": "high",
                }
            )
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to send push notification: {e}")