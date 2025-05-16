from pymongo import MongoClient
from dotenv import load_dotenv
from os import getenv
import warnings
load_dotenv()


class MongoHandler:
    def __init__(self):

        warnings.filterwarnings("ignore", category=UserWarning)
        self.client = MongoClient(getenv("MONGO_URL"))
        self.db = self.client[getenv("DB_ENV")]

    
    