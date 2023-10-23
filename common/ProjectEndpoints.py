import struct

from common.ServerEndpoints import *


class JoinDoc(IdEndpoint):
    ENDPOINT_ID = EndpointID.JOIN_DOC


class JoinedDoc(EndpointConstructor):
    ENDPOINT_ID = EndpointID.JOINED_DOC

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
