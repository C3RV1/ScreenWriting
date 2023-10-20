from pymongo import database


class User:
    def __init__(self):
        self.username = None
        self.password_hash = None
        self.password_salt = None

    def load_from_database(self, db: database.Database, name: str):
        user_collection = db["users"]
        user_document = user_collection.find_one({"name": name})
        if user_document is None:
            return False
        self.password_salt = user_document["salt"].decode("ascii")
        self.password_hash = user_document["password_hash"]
        return True
