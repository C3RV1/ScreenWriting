import dataclasses
import os


@dataclasses.dataclass
class Config:
    crt_folder_path: os.PathLike = "./certs"
    CONNECT_PORT = 8684
