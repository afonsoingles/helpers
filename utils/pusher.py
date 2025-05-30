import requests
import os

class Pusher:

    def singlePush(self, to, title, body, data, ttl, sound=None, isCritical=False):
        try:
            r = requests.post(f"{os.environ.get('API:URL')}/v1/notifications/send", headers={
                "X-Secure-Key": os.environ.get("SECURE_KEY"),
            },
            json={
                "to": to,
                "title": title,
                "body": body,
                "data": data,
                "ttl": ttl,
                "sound": sound,
                "isCritical": isCritical,
            })
        except:
            return
    
    def bulkPush(self, title, body, data, ttl, sound, isCritical=False):
        try:
            r = requests.post(f"{os.environ.get('API_URL')}/v1/notifications/send", headers={
                "X-Secure-Key": os.environ.get("SECURE_KEY"),
            },
            json={
                "sendAll": True,
                "title": title,
                "body": body,
                "data": data,
                "ttl": ttl,
                "sound": sound,
                "isCritical": isCritical,
            })
        except:
            return