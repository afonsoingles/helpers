import requests
from utils.getLocation import getLocation
import os



def getDailyForecast(): # Daily forecast (3 days)

    device = getLocation()
    params = {
        'lon': device['longitude'],
        "lat": device['latitude'],
        'appid': os.environ.get('WEATHER_API_KEY'),
        'units': 'metric',
        'cnt': 3
    }
    response = requests.get("https://api.openweathermap.org/data/2.5/forecast/daily", params=params)

    return response.json()
    
def getTodayForecast(): # Daily forecast (1 day)

    device = getLocation()
    params = {
        'lon': device['longitude'],
        "lat": device['latitude'],
        'appid': os.environ.get('WEATHER_API_KEY'),
        'units': 'metric',
        'cnt': 1
    }
    response = requests.get("https://api.openweathermap.org/data/2.5/forecast/daily", params=params)

    return response.json()