from common.User import User
from pymongo import database


class ServerUser(User):
    def __init__(self, username, visible_name, hash_, salt):
        super().__init__(username, visible_name)
        self.password_hash: bytes = hash_
        self.password_salt: bytes = salt

    @classmethod
    def load_from_database(cls, db: database.Database, name: str):
        user_collection = db["users"]
        user_document = user_collection.find_one({"name": name})
        if user_document is None:
            return None
        return cls(name, user_document["visible_name"],
                   user_document["password_hash"],
                   user_document["salt"].encode("ascii"))
