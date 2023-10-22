from common.EndpointConstructors import *
import struct
import io

from common.BlockPatches import BlockPatch


class PatchScript(EndpointConstructor):
    ENDPOINT_ID = EndpointID.SCRIPT_PATCH

    def __init__(self, document_id: str, patch: BlockPatch, branch_id: int, document_timestamp: int):
        super().__init__()
        self.document_path = document_id
        self.patch: BlockPatch = patch
        self.branch_id: int = branch_id
        self.document_timestamp = document_timestamp

    def to_bytes(self) -> bytes:
        path_encoded = self.document_path.encode("ascii")
        return struct.pack("HII", len(path_encoded), self.branch_id, self.document_timestamp) + path_encoded\
            + self.patch.to_bytes()

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 4:
            return None
        rdr = io.BytesIO(msg)
        path_len, branch_id, document_timestamp = struct.unpack("HII", rdr.read(10))
        path = rdr.read(path_len).decode("ascii")
        patch = BlockPatch.from_bytes(rdr)
        return cls(path, patch, branch_id, document_timestamp)


class PatchedScript(EndpointConstructor):
    ENDPOINT_ID = EndpointID.SCRIPT_PATCHED

    def __init__(self, document_id: str, patch: BlockPatch, document_timestamp: int):
        super().__init__()
        self.document_path = document_id
        self.patch: BlockPatch = patch
        self.document_timestamp = document_timestamp

    def to_bytes(self) -> bytes:
        path_encoded = self.document_path.encode("ascii")
        return struct.pack("HI", len(path_encoded), self.document_timestamp) + path_encoded\
            + self.patch.to_bytes()

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 4:
            return None
        rdr = io.BytesIO(msg)
        path_len, document_timestamp = struct.unpack("HI", rdr.read(6))
        path = rdr.read(path_len).decode("ascii")
        patch = BlockPatch.from_bytes(rdr)
        return cls(path, patch, document_timestamp)


class AckPatch(EndpointConstructor):
    ENDPOINT_ID = EndpointID.SCRIPT_PATCH_ACK

    def __init__(self, document_id: str, patch: BlockPatch):
        super().__init__()
        self.document_path = document_id
        self.patch: BlockPatch = patch

    def to_bytes(self) -> bytes:
        path_encoded = self.document_path.encode("ascii")
        return struct.pack("H", len(path_encoded)) + path_encoded\
            + self.patch.to_bytes()

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 4:
            return None
        rdr = io.BytesIO(msg)
        path_len = struct.unpack("H", rdr.read(2))[0]
        path = rdr.read(path_len).decode("ascii")
        patch = BlockPatch.from_bytes(rdr)
        return cls(path, patch)