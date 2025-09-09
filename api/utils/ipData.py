import requests
import os
import json
from api.utils.redis import redisClient

class IPData:
    
    async def get_ip_data(self, ip):
        if str(ip).startswith("192.") and os.environ.get("DB_ENV") == "development":
            return {"country_code": "PT"}
        cachedData = await redisClient.get(f"ipData:{ip}")
        print(cachedData)
        if cachedData:
            return json.loads(cachedData)
        
        try:
            response = requests.get(f"https://api.ipdata.co/{ip}?api-key={os.environ.get('IPDATA_API_KEY')}")
            if response.status_code == 200:
                redisClient.set(f"ipData:{ip}", response.text)
                return response.json()
            else:
                hcResponse = requests.get(f"https://ip.hackclub.com/{ip}")
                if hcResponse.status_code == 200:
                    jsonResponse = hcResponse.json()
                    ipData = {
                        "country_code": jsonResponse["country_iso_code"]
                    }
                    redisClient.set(f"ipData:{ip}", json.dumps(ipData), ex=86400) #1d cache
                    return ipData
        except Exception as e:
            return None