import requests
import os

class Pusher:

    def singlePush(self, to, title, body, data, ttl, sound=None, isCritical=False) -> dict:
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
            return r.json()
        except:
            return
    
    def bulkPush(self, title, body, data, ttl, sound=None, isCritical=False) -> dict:
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
            return r.json()
        except:
            return
    
    def push(self, sender, recipient, title, body, sound=None, data={}, ttl=0, isCritical=False):

        r = requests.post(f"{os.environ.get('API_URL')}/v2/notifications/send", headers={
            "X-Secure-Key": os.environ.get("SECURE_KEY"),
        },
        json={
            "from": sender,
            "to": recipient,
            "title": title,
            "body": body,
            "sound": sound,
            "data": data,
            "ttl": ttl,
            "isCritical": isCritical,
        })

        return r.json()
