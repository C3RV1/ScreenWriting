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
        return struct.pack("!B", len(name_encoded)) + name_encoded

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 1:
            return None
        rdr = io.BytesIO(msg)
        name_length = struct.unpack("!B", rdr.read(1))[0]
        if len(msg) != 1 + name_length:
            return
        return cls(rdr.read(name_length).decode("utf-8"))


class DeleteProject(IdEndpoint):
    ENDPOINT_ID = EndpointID.DELETE_PROJECT


class RenameProject(IdAndNameEndpoint):
    ENDPOINT_ID = EndpointID.RENAME_PROJECT


class ServerScopeRequestError(RequestError):
    ENDPOINT_ID = EndpointID.ERROR_FULFILLING_SERVER_REQUEST


class CreatedProject(IdAndNameEndpoint):
    ENDPOINT_ID = EndpointID.CREATED_PROJECT


class RenamedProject(IdAndNameEndpoint):
    ENDPOINT_ID = EndpointID.RENAMED_PROJECT


class DeletedProject(IdEndpoint):
    ENDPOINT_ID = EndpointID.DELETED_PROJECT


class OpenProject(IdEndpoint):
    ENDPOINT_ID = EndpointID.OPEN_PROJECT


class OpenedProject(EndpointConstructor):
    ENDPOINT_ID = EndpointID.OPENED_PROJECT

    def __init__(self, user: User):
        super().__init__()
        self.user = user

    def to_bytes(self) -> bytes:
        return self.user.to_bytes_public()

    @classmethod
    def from_msg(cls, msg: bytes):
        rdr = io.BytesIO(msg)
        user = User.from_bytes_public(rdr)
        return cls(user)


class SyncProject(EndpointConstructor):
    ENDPOINT_ID = EndpointID.SYNC_PROJECT

    def __init__(self, project: Project, other_users: list[User]):
        super().__init__()
        self.project: Project = project
        self.other_users: list[User] = other_users

    def to_bytes(self) -> bytes:
        msg = struct.pack("!B", len(self.other_users))
        msg += self.project.to_bytes()
        for user in self.other_users:
            msg += user.to_bytes_public()
        return msg

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 1:
            return None
        rdr = io.BytesIO(msg)
        user_count = struct.unpack("!B", rdr.read(1))[0]
        project = Project.from_bytes(rdr)
        users = []
        for i in range(user_count):
            users.append(User.from_bytes_public(rdr))
        return cls(project, users)
