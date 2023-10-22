from common.EndpointConstructors import *
from common.User import User
import struct
import io


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

    def __init__(self, error_code, project_list, user):
        super().__init__()
        self.error_code: LoginErrorCode = error_code
        self.project_list = project_list
        self.user: User = user

    def to_bytes(self) -> bytes:
        msg = struct.pack("B", self.error_code)
        if self.error_code != LoginErrorCode.SUCCESSFUL:
            return msg

        msg += struct.pack("B", len(self.project_list))
        for project_name, project_id in self.project_list:
            encoded_project_name = project_name.encode("utf-8")
            msg += struct.pack("B", len(encoded_project_name)) + encoded_project_name
            msg += project_id.encode("ascii")  # 24 hex character
        return msg + self.user.to_bytes_public()

    @classmethod
    def from_msg(cls, msg: bytes):
        if len(msg) < 1:
            return None
        rdr = io.BytesIO(msg)
        error_code = struct.unpack("B", rdr.read(1))[0]
        if error_code != 0:
            return cls(error_code, [], None)

        project_list = []
        project_count = struct.unpack("B", rdr.read(1))[0]
        for i in range(project_count):
            project_name_length = struct.unpack("B", rdr.read(1))[0]
            project_name = rdr.read(project_name_length).decode("utf-8")
            project_id = rdr.read(24).decode("ascii")
            project_list.append((project_name, project_id))
        return cls(error_code, project_list, User.from_bytes_public(rdr))