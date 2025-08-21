from utils.ai import AI
from bases.helper import BaseHelper
import schedule
from datetime import datetime
from utils.getWeatherData import getTodayForecast
from main import logger
from utils.getRules import getValidRules
from utils.mailer import Mailer
from utils.pusher import Pusher
import os

ai = AI()
mailer = Mailer()
pusher = Pusher()

class Weathery(BaseHelper):
    def __init__(self):
        super().__init__(run_at_start=False)

    def run(self):
        logger.info(f"[Weathery] Started at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")
        rules = getValidRules()
        
        for rule in rules:

            if rule.get("fields", {}).get("disableWeathery"):
                logger.info(f"[Weathery] Rule {rule.get("fields", {}).get("ruleNumber")} triggered: {rule.get("fields", {}).get("comment")} - Weathery disabled")
                logger.info(f"[Weathery] Finished at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")
                return
        
        weatherForecast = getTodayForecast()
        logger.info(f"[Weathery] Obtained weather forecast")

        promptPusher = f"""Please write a push notification in Portuguese for Afonso.
        As it is a weather forecast, please include the temperature and the weather condition.
        The notification should be short and concise, with a maximum of 100 characters.
        Write fluent text in Portuguese, as if you were writing to a friend.
        You should talk about the weather (maximum and minimum) - You should refer the temperatures are the minimum or the maximum, if its going to rain or not, the temperture, the wind, and the humidity.
        Do not include any other information.
        The provided wind speed is in km/h.
        In Portuguese from Portugal, the word 'humidade' is used for humidity. Please provide humidity in 'XX%'
        Please start your notification with 'Hoje o tempo...' and then continue in fluent text, not with ':'
        Do not end the notification with goodbye'.



        Here is the OpenWeatherMap raw data: \n\n{weatherForecast}"""

        pusher.bulkPush(
            title="Previsão do tempo para hoje",
            body=ai.prompt(promptPusher),
            ttl=600,
            data={
                "helper": "weathery",
            },
        )
        logger.info(f"[Weathery] Pushed notification")
        logger.info(f"[Weathery] Finished at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")

    def schedule(self):
        schedule.every().day.at(f"08:40:00", os.environ.get("TIMEZONE")).do(self.run)
    
    def get_schedule_config(self):
        """Return schedule configuration for the execution queue system."""
        return {
            "type": "daily",
            "time": "08:40:00",
            "priority": 2,  # High priority for weather updates
            "expiry": 1800,  # 30 minutes expiry
            "enabled": True
        }