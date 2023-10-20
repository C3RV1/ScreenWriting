from server.ClientHandler import ClientHandler
from common.FountianParser import FountainParser
import os


class RealTimeDocument:
    def __init__(self, file_id, blocks):
        self.file_id = file_id
        self.blocks = blocks

        self.editing_users: list[ClientHandler] = []
        self.user_to_acquired_block: dict[ClientHandler] = {}

    @classmethod
    def open_from_file_id(cls, file_id):
        parser = FountainParser()
        path = os.path.join("documents", file_id + ".fountain")
        if not os.path.isfile(path):
            return None
        with open(path, "r") as f:
            parser.parse(f.read())
        return cls(file_id, parser.blocks)

    def save(self):
        pass
