from common.Blocks import Block
from common.EndpointConstructors import *


class IdAndUsernameEndpoint(EndpointConstructor):
    def __init__(self, file_id: str, username: str):
        super().__init__()
        self.file_id: str = file_id
        self.username: str = username

    def to_bytes(self) -> bytes:
        username_encoded = self.username.encode("ascii")
        return self.file_id.encode("ascii") + struct.pack("!B", len(username_encoded)) + username_encoded

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 24:
            return None
        rdr = io.BytesIO(msg)
        file_id = rdr.read(24).decode("ascii")
        username_len = struct.unpack("!B", rdr.read(1))[0]
        if len(msg) != 25 + username_len:
            return
        username = rdr.read(username_len).decode("ascii")
        return cls(file_id, username)


class JoinDoc(IdEndpoint):
    ENDPOINT_ID = EndpointID.JOIN_DOC


class LeaveDoc(IdEndpoint):
    ENDPOINT_ID = EndpointID.LEAVE_DOC


class JoinedDoc(IdAndUsernameEndpoint):
    ENDPOINT_ID = EndpointID.JOINED_DOC


class LeftDoc(IdAndUsernameEndpoint):
    ENDPOINT_ID = EndpointID.LEFT_DOC


class SyncDoc(EndpointConstructor):
    ENDPOINT_ID = EndpointID.SYNC_DOC
    MAX_DATA_SIZE = 0x100000  # in bytes ~= 1 MB

    def __init__(self, file_id: str, document_timestamp: int, blocks: list[Block]):
        super().__init__()
        self.file_id = file_id
        self.document_timestamp = document_timestamp
        self.blocks = blocks

    def to_bytes(self) -> bytes:
        msg = self.file_id.encode("ascii")
        msg += struct.pack("II", len(self.blocks), self.document_timestamp)
        for block in self.blocks:
            msg += block.to_bytes()
        return msg

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 24+8:
            return None
        rdr = io.BytesIO(msg)
        file_id = rdr.read(24).decode("ascii")
        block_count, document_timestamp = struct.unpack("II", rdr.read(8))
        blocks = []
        for i in range(block_count):
            blocks.append(Block.from_bytes(rdr))
        return cls(file_id, document_timestamp, blocks)


class PathEndpoint(EndpointConstructor):
    def __init__(self, path: str):
        super().__init__()
        self.path: str = path

    def to_bytes(self) -> bytes:
        path_encoded = self.path.encode("ascii")
        return struct.pack("!B", len(path_encoded)) + path_encoded

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 24:
            return None
        rdr = io.BytesIO(msg)
        path_len = struct.unpack("!B", rdr.read(1))[0]
        path = rdr.read(path_len).decode("ascii")
        return cls(path)


class CreateDoc(PathEndpoint):
    ENDPOINT_ID = EndpointID.CREATE_DOC


class CreatedDoc(EndpointConstructor):
    def __init__(self, path: str, file_id: str):
        super().__init__()
        self.file_id: str = file_id
        self.path: str = path

    def to_bytes(self) -> bytes:
        path_encoded = self.path.encode("ascii")
        return self.file_id.encode("ascii") + struct.pack("!B", len(path_encoded)) + path_encoded

    @classmethod
    def from_msg(cls, msg: bytes):
        rdr = io.BytesIO(msg)
        file_id = rdr.read(24).decode("ascii")
        path_len = struct.unpack("!B", rdr.read(1))[0]
        if len(msg) != 25 + path_len:
            return
        path = rdr.read(path_len).decode("ascii")
        return cls(file_id, path)


class CreateFolder(PathEndpoint):
    ENDPOINT_ID = EndpointID.CREATE_FOLDER


class CreatedFolder(PathEndpoint):
    ENDPOINT_ID = EndpointID.CREATED_FOLDER


class ProjectScopeRequestError(RequestError):
    ENDPOINT_ID = EndpointID.ERROR_FULFILLING_PROJECT_REQUEST
