import threading
import typing
if typing.TYPE_CHECKING:
    from server.ClientHandler import ClientHandler
from common.FountianParser import FountainParser
import os
from common.ScriptEndpoints import *


class RealTimeUser:
    def __init__(self, handler: 'ClientHandler', rtd: 'RealTimeDocument'):
        self.rtd = rtd
        self.handler: 'ClientHandler' = handler
        self.branch_timestamp = 0
        self.patch_from_old_to_new = BlockPatch()
        self.current_branch_id = 0

    def ack_patch(self, patch: BlockPatch):
        self.handler.sock.send_endp(AckPatch(self.rtd.file_id, patch))

    def broadcast_patch(self, patch: BlockPatch):
        self.patch_from_old_to_new.add_change(patch)
        self.handler.sock.send_endp(
            PatchedScript(self.rtd.file_id, patch, self.rtd.document_timestamp)
        )

    def updated_patch(self, patch: BlockPatch, branch_id, branch_timestamp):
        if branch_id == self.current_branch_id and branch_timestamp == self.rtd.document_timestamp:
            branch_timestamp += 1
            self.rtd.push_patch(patch, self)
            self.patch_from_old_to_new = BlockPatch()
        elif branch_id == self.current_branch_id and branch_timestamp < self.rtd.document_timestamp:
            self.current_branch_id += 1
            patch.rebase_to(self.patch_from_old_to_new)
        elif branch_id < self.current_branch_id:
            patch.rebase_to(self.patch_from_old_to_new)
        self.ack_patch(patch)


class RealTimeDocument:
    def __init__(self, file_id, blocks):
        self.file_id = file_id

        self.document_lock = threading.Lock()
        self.blocks = blocks

        self.editing_users: list[RealTimeUser] = []
        self.document_timestamp = 0

    def push_patch(self, patch, rt_user):
        self.document_lock.acquire()
        patch.apply_on_blocks(self.blocks)
        self.document_timestamp += 1
        for editing_user in self.editing_users:
            if editing_user is rt_user:
                continue
            editing_user.broadcast_patch(patch)
        self.document_lock.release()

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
