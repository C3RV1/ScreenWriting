import io
import struct
from enum import IntEnum

LINES_PER_PAGE = 57


class BlockType(IntEnum):
    ACTION = 0
    SCENE_HEADING = 1
    CHARACTER = 2
    DIALOGUE = 3
    PARENTHETICAL = 4
    TRANSITION = 5
    CENTERED = 6
    PAGE_BREAK = 7
    NOTE = 8
    DUAL_DIALOGUE = 9


class Style(IntEnum):
    ITALICS = 0
    BOLD = 1
    UNDERLINE = 2
    LINE_BREAK = 3
    TEXT = 4


def style_contents(block_contents: str):
    """length_wrap = {
        BlockType.CHARACTER: 58 - 43,
        BlockType.DIALOGUE: 35,
        BlockType.PARENTHETICAL: 32
    }.get(block.block_type, 58)"""
    block_styled = []
    current_style = set()
    current_str = ""
    styles = (
        (Style.BOLD, "**"),
        (Style.ITALICS, "*"),
        (Style.UNDERLINE, "_")
    )
    while len(block_contents) > 0:
        if block_contents[0] == "\\" and block_contents[1:2] in ("*", "_"):
            current_str += block_contents[1:2]
            block_contents = block_contents[2:]
            continue
        for style, char in styles:
            if block_contents.startswith(char):
                if style in current_style and current_str[-1:] != " ":
                    block_contents = block_contents[len(char):]
                    current_style.remove(style)
                    if current_str != "":
                        block_styled.append(current_str)
                    block_styled.append(style)
                    current_str = ""
                    break
                elif style not in current_style and block_contents[len(char):len(char)+1] != " ":
                    block_contents = block_contents[len(char):]
                    current_style.add(style)
                    if current_str != "":
                        block_styled.append(current_str)
                    block_styled.append(style)
                    current_str = ""
                    break
        else:
            current_str += block_contents[0]
            block_contents = block_contents[1:]
    if current_str != "":
        block_styled.append(current_str)
    return block_styled


def un_style_contents(block_contents: list):
    current_style = set()
    un_styled = ""
    style_queue = block_contents.copy()
    while style_queue:
        processing = style_queue.pop(0)
        if isinstance(processing, str):
            un_styled += processing
            continue
        if processing not in current_style:
            current_style.add(processing)
            for i, style in enumerate(style_queue):
                if isinstance(style, str):
                    if style.startswith(" "):
                        style_queue[i] = style.lstrip()
                        un_styled += style[:len(style)-len(style_queue[i])]
                    break
        elif processing in current_style:
            current_style.remove(processing)
            if un_styled.endswith(" "):
                un_styled_stripped = un_styled.rstrip()
                white_chars = un_styled[len(un_styled_stripped)-len(un_styled):]
                style_queue.insert(0, white_chars)
        if processing == Style.ITALICS:
            un_styled += "*"
        elif processing == Style.BOLD:
            un_styled += "**"
        elif processing == Style.UNDERLINE:
            un_styled += "_"
    return un_styled


def encode_styled(styled: list) -> bytes:
    msg = struct.pack("!H", len(styled))
    for v in styled:
        if isinstance(v, str):
            enc = v.encode("utf-8")
            msg += struct.pack("!BH", Style.TEXT, len(enc)) + enc
        else:
            msg += struct.pack("!B", v)
    return msg


def decode_styled(rdr: io.BytesIO) -> list:
    contents_length = struct.unpack("!H", rdr.read(2))[0]
    contents = []
    for i in range(contents_length):
        content_type = struct.unpack("!B", rdr.read(1))[0]
        if content_type == Style.TEXT:
            text_len = struct.unpack("!H", rdr.read(2))[0]
            contents.append(rdr.read(text_len).decode("utf-8"))
        else:
            contents.append(content_type)
    return contents


class Block:
    def __init__(self, block_type: BlockType, block_contents: list):
        self.block_type: BlockType = block_type
        self.block_contents: list = block_contents

    def copy(self):
        return Block(self.block_type, self.block_contents)

    @classmethod
    def from_text(cls, block_type: BlockType, block_contents: str):
        return cls(block_type, style_contents(block_contents))

    def fix_contents(self):
        return un_style_contents(self.block_contents)

    def __repr__(self):
        return f"{self.block_type.name} block: {repr(self.block_contents)}"

    def to_bytes(self) -> bytes:
        msg = struct.pack("!B", self.block_type)
        return msg + encode_styled(self.block_contents)

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO) -> 'Block':
        block_type = struct.unpack("!B", rdr.read(1))[0]
        contents = decode_styled(rdr)
        return Block(block_type, contents)


