import dataclasses


@dataclasses.dataclass
class Config:
    LISTENING_ADDR = ('0.0.0.0', 8684)
    MAX_BIND = 5
    MAX_TRASH_CAN_DAYS = 10
    MAX_PROJECT_NAME_LENGTH = 64
