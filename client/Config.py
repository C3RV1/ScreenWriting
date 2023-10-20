import dataclasses
import os


@dataclasses.dataclass
class ClientConfig:
    crt_folder_path: os.PathLike = "./certs"
    CONNECT_PORT = 8684
