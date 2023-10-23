import io
import struct


class User:
    def __init__(self, username, visible_name):
        self.username: str = username
        self.visible_name: str = visible_name

    def to_bytes_public(self) -> bytes:
        username_encoded = self.username.encode("ascii")
        visible_name_encode = self.visible_name.encode("utf-8")
        return struct.pack("!BB", len(username_encoded), len(visible_name_encode))\
            + username_encoded + visible_name_encode

    @classmethod
    def from_bytes_public(cls, rdr: io.BytesIO):
        username_length, visible_name_length = struct.unpack("!BB", rdr.read(2))
        username = rdr.read(username_length).decode("ascii")
        visible_name = rdr.read(visible_name_length).decode("utf-8")
        return cls(username, visible_name)
