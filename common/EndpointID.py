import enum
import re
import struct
import io


class EndpointID(enum.IntEnum):
    PING = 1
    PONG = 2

    LOGIN = 10  # Done
    LOGIN_RESULT = 11  # Done
    # LOGOUT = 12
    # LOGOUT_RESULT = 13

    # Logged in - Server wide updates
    ERROR_FULFILLING_SERVER_REQUEST = 19
    CREATE_PROJECT = 20  # Done
    DELETE_PROJECT = 30  # Done
    OPEN_PROJECT = 40
    RENAME_PROJECT = 50  # Done

    SYNC_PROJECT = 41

    CREATED_PROJECT = 22
    DELETED_PROJECT = 32
    OPENED_PROJECT = 42
    RENAMED_PROJECT = 52

    # Project wide updates
    ERROR_FULFILLING_PROJECT_REQUEST = 99
    JOIN_DOC = 100
    LEAVE_DOC = 110
    CREATE_DOC = 120
    DELETE_DOC = 130
    CREATE_FOLDER = 140

    SYNC_DOC = 101

    JOINED_DOC = 102
    LEFT_DOC = 112
    CREATED_DOC = 122
    DELETED_DOC = 132
    CREATED_FOLDER = 142

    # Doc wide updates
    ERROR_FULFILLING_DOC_UPDATES = 299
    ACQUIRE_BLOCK = 300
    RELEASE_BLOCK = 310
    UPDATE_BLOCK = 320
    ADD_BLOCK = 330
    REMOVE_BLOCK = 340
    SYNC_BLOCK_REQUEST = 350

    SYNC_BLOCK = 351

    ACQUIRED_BLOCK = 302
    RELEASED_BLOCK = 312
    UPDATED_BLOCK = 322
    BLOCK_ADDED = 332
    REMOVED_BLOCK = 342

    # User updates - Broadcast project wide
    ERROR_FULFILLING_USER_REQUEST = 599
    CHANGE_USERNAME = 600
    CHANGE_USER_VISIBLE_NAME = 610
    # CHANGE_USER_PFP = 620

    CHANGED_USERNAME = 602
    CHANGED_USER_VISIBLE_NAME = 612
    # CHANGE_USER_PFP_RESULT = 622

    ARE_U_ALIVE = 901
    I_AM_ALIVE = 900
    CLOSE = 1000


class EndpointConstructor:
    MAX_DATA_SIZE = 4096
    ENDPOINT_ID = 0

    def __init__(self):
        pass

    def to_bytes(self) -> bytes:
        return b""

    @classmethod
    def from_msg(cls, msg: bytes):
        return cls()


class LoginRequest(EndpointConstructor):
    MAX_DATA_SIZE = 128
    ENDPOINT_ID = EndpointID.LOGIN

    def __init__(self, username: str, password: bytes):
        super().__init__()
        self.username: str = username
        self.password: bytes = password

    def to_bytes(self) -> bytes:
        username_encoded = self.username.encode("ascii")
        return struct.pack("BB", len(username_encoded), len(self.password)) + username_encoded + self.password

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 2:
            return None
        rdr = io.BytesIO(msg)
        username_length, password_length = struct.unpack("BB", rdr.read(2))

        if len(msg) != 2 + username_length + password_length:
            return None

        return cls(
            rdr.read(username_length).decode("ascii"),
            rdr.read(password_length)
        )


class LoginErrorCode:
    SUCCESSFUL = 0
    BAD_REQUEST = 1
    INVALID_CREDENTIALS = 2


class LoginResult(EndpointConstructor):
    ENDPOINT_ID = EndpointID.LOGIN_RESULT

    def __init__(self, error_code, project_list):
        super().__init__()
        self.error_code: LoginErrorCode = error_code
        self.project_list = project_list

    def to_bytes(self) -> bytes:
        msg = struct.pack("B", self.error_code)
        if self.error_code != 0:
            return msg

        for project_name, project_id in self.project_list:
            encoded_project_name = project_name.encode("utf-8")
            msg += struct.pack("B", len(encoded_project_name)) + encoded_project_name
            msg += project_id.encode("ascii")  # 24 hex character
        return msg

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 1:
            return None
        rdr = io.BytesIO(msg)
        error_code = struct.unpack("B", rdr.read(1))[0]
        if error_code != 0:
            return cls(error_code, [])

        project_list = []
        project_count = struct.unpack("B", rdr.read(1))[0]
        for i in range(project_count):
            project_name_length = struct.unpack("B", rdr.read(1))[0]
            project_name = rdr.read(project_name_length)
            project_id = rdr.read(24)
            project_list.append((project_name, project_id))
        return cls(error_code, project_list)


class AreYouAlive(EndpointConstructor):
    ENDPOINT_ID = EndpointID.ARE_U_ALIVE
    MAX_DATA_SIZE = 0


class IAmAlive(EndpointConstructor):
    ENDPOINT_ID = EndpointID.I_AM_ALIVE
    MAX_DATA_SIZE = 0


class Close(EndpointConstructor):
    ENDPOINT_ID = EndpointID.CLOSE
    MAX_DATA_SIZE = 0


class Ping(EndpointConstructor):
    ENDPOINT_ID = EndpointID.PING
    MAX_DATA_SIZE = 0


class Pong(EndpointConstructor):
    ENDPOINT_ID = EndpointID.PONG
    MAX_DATA_SIZE = 0


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
        self.new_name = new_name

    def to_bytes(self) -> bytes:
        name_encoded = self.new_name.encode("utf-8")
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
