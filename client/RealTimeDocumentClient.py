import copy

from common.BlockPatches import Block
from common.ScriptEndpoints import *

from client.Net import Net

from client.visual_document.Cursor import CursorSetPositionChange


class RealTimeDocumentClient:
    def __init__(self, blocks, file_id: str, net: Net):
        self.blocks: list[Block] = blocks
        self.blocks_advanced: list[Block] = copy.deepcopy(blocks)
        self.advance_patch = BlockPatch()
        self.branch_id = 0
        self.document_timestamp = 0

        self.file_id = file_id
        self.net = net

        self.on_rebase = None
        self.on_change = None

    def move_cursor(self, cursor_position: CursorSetPositionChange):
        # TODO: Make cursor position also changes,
        #       but do not send them to the server. (or do? shared cursors?)
        #       Probably add it to the end, removing if there
        #       are any other previously.
        #       ---
        #       When rebasing, apply the last cursor set position.
        pass

    def send_change(self, patch: BlockPatch):
        # We suppose the patch has already been applied to advanced.
        # patch.apply_on_blocks(self.blocks_advanced)

        self.advance_patch.add_change(patch)
        self.net.sock.send_endp(PatchScript(self.file_id, patch, self.branch_id, self.document_timestamp))
        print(f"Sent change. Next one should be {self.document_timestamp}")

        # The expected document timestamp increases by one.
        self.document_timestamp += 1

    def ack_change(self, msg: AckPatch):
        print("Ack'd change.")
        msg.patch.apply_on_blocks(self.blocks)
        self.advance_patch.remove_change(msg.patch)
        print(self.advance_patch.change_queue)

    def got_change(self, msg: PatchedScript):
        print(f"Got change. Doc timestamp: {msg.document_timestamp} Expected: {self.document_timestamp}")
        msg.patch.apply_on_blocks(self.blocks)
        if msg.document_timestamp < self.document_timestamp:
            # Must rebase :D
            # If the change has a lower document timestamp than the local one,
            # Then the change was made previous to local ones.
            print("Rebasing")
            self.branch_id += 1
            self.blocks_advanced: list[Block] = copy.deepcopy(self.blocks)
            self.advance_patch.rebase_to(msg.patch)
            self.advance_patch.apply_on_blocks(self.blocks_advanced)
            self.on_rebase(self.blocks_advanced)
        else:
            # We are up-to-date.
            msg.patch.apply_on_blocks(self.blocks_advanced)
        self.on_change()

        # The expected document timestamp increases by one.
        self.document_timestamp += 1

