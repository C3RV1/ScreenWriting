import enum
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
    # Maybe incorporate max_data_size and id here

    def __init__(self):
        pass

    def to_bytes(self) -> bytes:
        return b""

    @classmethod
    def from_msg(cls, msg: bytes):
        return cls()


class LoginRequest(EndpointConstructor):
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


class LoginResult(EndpointConstructor):
    def __init__(self, error_code, project_list):
        super().__init__()
        self.error_code: int = error_code
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
    pass


class IAmAlive(EndpointConstructor):
    pass


class Close(EndpointConstructor):
    pass


class Ping(EndpointConstructor):
    pass


class Pong(EndpointConstructor):
    pass


class LoginErrorCode:
    SUCCESSFUL = 0
    BAD_REQUEST = 1
    INVALID_CREDENTIALS = 2
