import enum
import io
import re
import struct


class EndpointID(enum.IntEnum):
    PING = 1
    PONG = 2

    LOGIN = 10  # Done
    LOGIN_RESULT = 11  # Done
    # LOGOUT = 12
    # LOGOUT_RESULT = 13

    # Logged in - Server wide updates
    ERROR_FULFILLING_SERVER_REQUEST = 19  # Done
    CREATE_PROJECT = 20  # Done
    DELETE_PROJECT = 30  # Done
    OPEN_PROJECT = 40  # Done
    RENAME_PROJECT = 50  # Done
    CLOSE_PROJECT = 60

    SYNC_PROJECT = 41  # Done

    CREATED_PROJECT = 22  # Done
    DELETED_PROJECT = 32  # Done
    OPENED_PROJECT = 42  # Done
    RENAMED_PROJECT = 52  # Done
    CLOSED_PROJECT = 62

    # Project wide updates
    ERROR_FULFILLING_PROJECT_REQUEST = 99
    JOIN_DOC = 100
    LEAVE_DOC = 110
    CREATE_DOC = 120
    DELETE_DOC = 130
    DELETE_DOC_FROM_TRASH = 140
    CREATE_FOLDER = 150
    DELETE_FOLDER = 160

    SYNC_DOC = 101

    JOINED_DOC = 102
    LEFT_DOC = 112
    CREATED_DOC = 122
    DELETED_DOC = 132
    DELETED_DOC_FROM_TRASH = 142
    CREATED_FOLDER = 152
    DELETED_FOLDER = 162

    # Doc wide updates
    SCRIPT_PATCH = 300  # Done
    SAVE_DOCUMENT = 310

    SCRIPT_PATCH_ACK = 301  # Done

    SCRIPT_PATCHED = 302  # Done

    # User updates - Broadcast project wide
    ERROR_FULFILLING_USER_REQUEST = 599
    CHANGE_USERNAME = 600
    CHANGE_USER_VISIBLE_NAME = 610
    # CHANGE_USER_PFP = 620

    CHANGED_USERNAME = 602
    CHANGED_USER_VISIBLE_NAME = 612
    # CHANGE_USER_PFP_RESULT = 622

    ARE_U_ALIVE = 901  # Done
    I_AM_ALIVE = 900  # Done
    CLOSE = 1000  # Done


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


class RequestError(EndpointConstructor):
    MAX_DATA_SIZE = 256

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def to_bytes(self) -> bytes:
        message_encoded = self.message.encode("utf-8")
        return struct.pack("!B", len(message_encoded)) + message_encoded

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 1:
            return None
        rdr = io.BytesIO(msg)
        message_length = struct.unpack("!B", rdr.read(1))[0]
        if len(msg) != 1 + message_length:
            return None
        return cls(rdr.read(message_length).decode("utf-8"))


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
        self.name: str = new_name

    def to_bytes(self) -> bytes:
        name_encoded = self.name.encode("utf-8")
        if not re.match("^[a-fA-F0-9]{24}$", self.id):
            raise ValueError
        return self.id.encode("ascii") + struct.pack("!B", len(name_encoded)) + name_encoded

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 25:
            return None
        rdr = io.BytesIO(msg)
        id_ = rdr.read(24)
        if not re.match(b"^[a-fA-F0-9]{24}$", id_):
            return None
        name_length = struct.unpack("!B", rdr.read(1))[0]
        return cls(id_.decode("ascii"), rdr.read(name_length).decode("utf-8"))


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
