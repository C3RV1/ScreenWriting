import threading
import typing

import bson

if typing.TYPE_CHECKING:
    from server.ClientHandler import ClientHandler
from common.FountianParser import FountainParser
import os
from common.ScriptEndpoints import *
from common.Project import Document
from pymongo import database


class RealTimeUser:
    def __init__(self, handler: 'ClientHandler', rtd: 'RealTimeDocument'):
        self.rtd = rtd
        self.handler: 'ClientHandler' = handler
        self.patch_from_old_to_new = BlockPatch()
        self.current_branch = 0
        self.frozen_branches_timestamps = {}

    def ack_patch(self, patch: BlockPatch):
        self.handler.sock.send_endp(AckPatch(self.rtd.file_id, patch))

    def broadcast_patch(self, patch: BlockPatch):
        self.patch_from_old_to_new.add_change(patch)
        self.handler.sock.send_endp(
            PatchedScript(self.rtd.file_id, patch, self.rtd.document_timestamp)
        )

    def updated_patch(self, patch: BlockPatch, branch_id, branch_timestamp):
        with self.rtd.document_lock:
            frozen_branch = False
            if branch_id == self.current_branch:
                if branch_timestamp == self.rtd.document_timestamp:
                    # up to date
                    self.rtd.push_patch(patch, self)
                    self.patch_from_old_to_new = BlockPatch()
                else:
                    # freeze branch
                    self.frozen_branches_timestamps[self.current_branch] = branch_timestamp - 1
                    self.current_branch += 1
                    frozen_branch = True
            else:
                frozen_branch = True

            if frozen_branch:
                # Frozen branch

                # Drop changes before the freezing point
                self.patch_from_old_to_new.drop_changes_with_smaller_change_id(
                    self.frozen_branches_timestamps[branch_id]
                )
                for id_ in self.frozen_branches_timestamps.copy():
                    if id_ < branch_id:
                        self.frozen_branches_timestamps.pop(id_, None)

                patch.rebase_to(self.patch_from_old_to_new)
                self.rtd.push_patch(patch, self)
            self.ack_patch(patch)


class RealTimeDocument(Document):
    def __init__(self, file_id, blocks):
        super().__init__(file_id)
        self.document_lock = threading.RLock()
        self.blocks = blocks

        self.editing_users: list[RealTimeUser] = []
        self.document_timestamp = 0

    def push_patch(self, patch, rt_user):
        with self.document_lock:
            patch = patch.copy()
            patch.set_changes_id(self.document_timestamp)
            patch.apply_on_blocks(self.blocks)
            self.document_timestamp += 1
            for editing_user in self.editing_users:
                if editing_user is rt_user:
                    continue
                editing_user.broadcast_patch(patch)

    @classmethod
    def open_from_database(cls, db: database.Database, file_id: str,
                           project_id: str):
        document_collection = db["documents"]
        document = document_collection.find_one(
            {
                "_id": bson.ObjectId(file_id)
            }
        )

        if str(document["project_id"]) != project_id:
            return None

        parser = FountainParser()
        path = os.path.join("documents", file_id + ".fountain")
        if not os.path.isfile(path):
            return None

        with open(path, "r") as f:
            parser.parse(f.read())
        return cls(file_id, parser.blocks)

    def save(self):
        with self.document_lock:
            parser = FountainParser()
            parser.blocks = self.blocks
            serialized = parser.serialize()
            path = os.path.join("documents", self.file_id + ".fountain")
            with open(path, "r") as f:
                f.write(serialized)
