from common.EndpointConstructors import *
import re
import struct
import io
from common.Project import Project
from common.User import User


class CreateProject(EndpointConstructor):
    ENDPOINT_ID = EndpointID.CREATE_PROJECT
    MAX_DATA_SIZE = 256

    def __init__(self, name: str):
        super().__init__()
        self.name: str = name

    def to_bytes(self) -> bytes:
        name_encoded = self.name.encode("utf-8")
        return struct.pack("B", len(name_encoded)) + name_encoded

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 1:
            return None
        rdr = io.BytesIO(msg)
        name_length = struct.unpack("B", rdr.read(1))[0]
        if len(msg) != 1 + name_length:
            return
        return cls(rdr.read(name_length).decode("utf-8"))


class IdEndpoint(EndpointConstructor):
    MAX_DATA_SIZE = 24

    def __init__(self, id_: str):
        super().__init__()
        self.id = id_

    def to_bytes(self) -> bytes:
        if not re.match("^[a-fA-F0-9]{24}$", self.id):
            raise ValueError
        return self.id.encode("ascii")

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) != 24:
            return None
        if not re.match(b"^[a-fA-F0-9]{24}$", msg):
            return None
        return cls(msg.decode("ascii"))


class IdAndNameEndpoint(EndpointConstructor):
    MAX_DATA_SIZE = 256

    def __init__(self, id_: str, new_name: str):
        super().__init__()
        self.id: str = id_
        self.name = new_name

    def to_bytes(self) -> bytes:
        name_encoded = self.name.encode("utf-8")
        if not re.match("^[a-fA-F0-9]{24}$", self.id):
            raise ValueError
        return self.id.encode("ascii") + struct.pack("B", len(name_encoded)) + name_encoded

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 25:
            return None
        rdr = io.BytesIO(msg)
        id_ = rdr.read(24)
        if not re.match(b"^[a-fA-F0-9]{24}$", id_):
            return None
        name_length = struct.unpack("B", rdr.read(1))[0]
        return cls(id_.decode("ascii"), rdr.read(name_length).decode("utf-8"))


class DeleteProject(IdEndpoint):
    ENDPOINT_ID = EndpointID.DELETE_PROJECT


class RenameProject(IdAndNameEndpoint):
    ENDPOINT_ID = EndpointID.RENAME_PROJECT


class ServerScopeRequestError(EndpointConstructor):
    ENDPOINT_ID = EndpointID.ERROR_FULFILLING_SERVER_REQUEST
    MAX_DATA_SIZE = 256

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def to_bytes(self) -> bytes:
        message_encoded = self.message.encode("utf-8")
        return struct.pack("B", len(message_encoded)) + message_encoded

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 1:
            return None
        rdr = io.BytesIO(msg)
        message_length = struct.unpack("B", rdr.read(1))[0]
        if len(msg) != 1 + message_length:
            return None
        return cls(rdr.read(message_length).decode("utf-8"))


class CreatedProject(IdAndNameEndpoint):
    ENDPOINT_ID = EndpointID.CREATED_PROJECT


class RenamedProject(IdAndNameEndpoint):
    ENDPOINT_ID = EndpointID.RENAMED_PROJECT


class DeletedProject(IdEndpoint):
    ENDPOINT_ID = EndpointID.DELETED_PROJECT


class OpenProject(IdEndpoint):
    ENDPOINT_ID = EndpointID.OPEN_PROJECT


class SyncProject(EndpointConstructor):
    ENDPOINT_ID = EndpointID.SYNC_PROJECT

    def __init__(self, project: Project, other_users: list[User]):
        super().__init__()
        self.project: Project = project
        self.other_users: list[User] = other_users

    def to_bytes(self) -> bytes:
        msg = struct.pack("B", len(self.other_users))
        msg += self.project.to_bytes()
        for user in self.other_users:
            msg += user.to_bytes_public()
        return msg

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 1:
            return None
        rdr = io.BytesIO()
        user_count = struct.unpack("B", rdr.read(1))[0]
        project = Project.from_bytes(rdr)
        users = []
        for i in range(user_count):
            users.append(User.from_bytes_public(rdr))
        return cls(project, users)
