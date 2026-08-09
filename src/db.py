import os

from pymongo import MongoClient

_client = None


def get_client():
    global _client
    if _client is None:
        _client = MongoClient(
            os.environ["MONGODB_URI"],
            maxPoolSize=1,
            serverSelectionTimeoutMS=5000,
        )
    return _client


def get_db():
    return get_client()[os.environ.get("MONGODB_DB", "app")]
