from common.EndpointConstructors import *
import struct
import io

from common.BlockPatches import BlockPatch


class ScriptScopeRequestError(RequestError):
    pass


class PatchScript(EndpointConstructor):
    ENDPOINT_ID = EndpointID.SCRIPT_PATCH

    def __init__(self, document_id: str, patch: BlockPatch, branch_id: int, document_timestamp: int):
        super().__init__()
        self.document_id = document_id
        self.patch: BlockPatch = patch
        self.branch_id: int = branch_id
        self.document_timestamp = document_timestamp

    def to_bytes(self) -> bytes:
        return self.document_id.encode("ascii") + struct.pack("!II", self.branch_id, self.document_timestamp)\
            + self.patch.to_bytes()

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 10:
            return None
        rdr = io.BytesIO(msg)
        file_id = rdr.read(24).decode("ascii")
        branch_id, document_timestamp = struct.unpack("!II", rdr.read(8))
        patch = BlockPatch.from_bytes(rdr)
        if patch is None:
            return None
        return cls(file_id, patch, branch_id, document_timestamp)


class PatchedScript(EndpointConstructor):
    ENDPOINT_ID = EndpointID.SCRIPT_PATCHED

    def __init__(self, document_id: str, patch: BlockPatch, document_timestamp: int):
        super().__init__()
        self.document_id = document_id
        self.patch: BlockPatch = patch
        self.document_timestamp = document_timestamp

    def to_bytes(self) -> bytes:
        return self.document_id.encode("ascii") + struct.pack("!I", self.document_timestamp)\
            + self.patch.to_bytes()

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 4:
            return None
        rdr = io.BytesIO(msg)
        file_id = rdr.read(24).decode("ascii")
        document_timestamp = struct.unpack("!I", rdr.read(4))[0]
        patch = BlockPatch.from_bytes(rdr)
        if patch is None:
            return None
        return cls(file_id, patch, document_timestamp)


class AckPatch(EndpointConstructor):
    ENDPOINT_ID = EndpointID.SCRIPT_PATCH_ACK

    def __init__(self, document_id: str, patch: BlockPatch):
        super().__init__()
        self.document_id = document_id
        self.patch: BlockPatch = patch

    def to_bytes(self) -> bytes:
        return self.document_id.encode("ascii") + self.patch.to_bytes()

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 4:
            return None
        rdr = io.BytesIO(msg)
        file_id = rdr.read(24).decode("ascii")
        patch = BlockPatch.from_bytes(rdr)
        if patch is None:
            return None
        return cls(file_id, patch)
