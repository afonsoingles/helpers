from pymongo import MongoClient
from dotenv import load_dotenv
from os import getenv
load_dotenv()


class MongoHandler:
    def __init__(self):

        self.client = MongoClient(getenv("MONGO_URL"))
        self.db = self.client[getenv("DB_ENV")]

    
    