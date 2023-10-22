import copy

from common.BlockPatches import Block
from common.ScriptEndpoints import *
from client.Net import Net
import threading


class RealTimeDocumentClient:
    def __init__(self, blocks, file_id: str, net: Net):
        self.blocks: list[Block] = blocks
        self.blocks_advanced: list[Block] = copy.deepcopy(blocks)
        self.advance_patch = BlockPatch()
        self.branch_id = 0
        self.document_timestamp = 0

        self.file_id = file_id
        self.net = net
        self.document_lock = threading.Lock()

    def send_change(self, patch: BlockPatch):
        self.document_lock.acquire()
        patch.apply_on_blocks(self.blocks)
        self.advance_patch.add_change(patch)
        self.document_timestamp += 1
        self.net.sock.send_endp(PatchScript(self.file_id, patch, self.branch_id, self.document_timestamp))
        self.document_lock.release()

    def ack_change(self, msg: AckPatch):
        self.document_lock.acquire()
        msg.patch.apply_on_blocks(self.blocks)
        self.advance_patch.remove_change(msg.patch)
        self.document_lock.release()

    def got_change(self, msg: PatchedScript):
        self.document_lock.acquire()
        msg.patch.apply_on_blocks(self.blocks)
        if msg.document_timestamp > self.document_timestamp:
            # Must rebase :D
            self.branch_id += 1
            self.blocks_advanced: list[Block] = copy.deepcopy(self.blocks)
            self.advance_patch.rebase_to(msg.patch)
            self.advance_patch.apply_on_blocks(self.blocks_advanced)
        self.document_timestamp = msg.document_timestamp
        self.document_lock.release()