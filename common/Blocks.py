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
    SEPARATOR = 7
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
    style_since_last = set()
    un_styled = ""
    style_queue = block_contents.copy()

    def add_style():
        nonlocal un_styled
        styles = {
            Style.ITALICS: "*",
            Style.UNDERLINE: "_",
            Style.BOLD: "**"
        }
        # When removing style add in reverse order
        for style_, symbol in list(styles.items())[::-1]:
            if style_ in current_style:
                continue
            if (style_ in current_style) != (style_ in style_since_last):
                un_styled += symbol
        for style_, symbol in styles.items():
            if style_ not in current_style:
                continue
            if (style_ in current_style) != (style_ in style_since_last):
                un_styled += symbol

    while style_queue:
        processing = style_queue.pop(0)
        if isinstance(processing, str):
            add_style()
            un_styled += processing
            style_since_last = current_style.copy()
            continue
        if processing not in current_style:
            current_style.add(processing)
            for i, style in enumerate(style_queue):
                if isinstance(style, str):
                    if style.startswith(" "):
                        style_queue[i] = style.lstrip()
                        un_styled += style[:len(style)-len(style_queue[i])]
                    break
        else:
            current_style.remove(processing)
            if un_styled.endswith(" "):
                un_styled_stripped = un_styled.rstrip()
                white_chars = un_styled[len(un_styled_stripped)-len(un_styled):]
                style_queue.insert(0, white_chars)
    add_style()
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

    def get_at(self, block_pos):
        block_queue = self.block_contents.copy()
        while block_pos > 0 and block_queue:
            v = block_queue.pop(0)
            if isinstance(v, str):
                if len(v) > block_pos:
                    return v[block_pos]
                block_pos -= len(v)
            else:
                if block_pos == 0:
                    return v
                block_pos -= 1
        return None

    def exclude_styles(self, start, end):
        ranges = []
        block_queue = self.block_contents.copy()
        current_range = [0, 0]
        block_pos = 0
        while end > 0 and block_queue:
            v = block_queue.pop(0)
            if isinstance(v, str):
                if len(v) >= start:
                    range_start = max(start, 0)
                    current_range[0] = block_pos + range_start
                    if len(v) > end:
                        current_range[1] += end - range_start
                    else:
                        current_range[1] += len(v) - range_start
                end -= len(v)
                start -= len(v)
                block_pos += len(v)
            else:
                if start <= 0:
                    ranges.append(current_range.copy())
                    current_range[0] += current_range[1] + 1
                    current_range[1] = 0
                start -= 1
                end -= 1
                block_pos += 1
        ranges.append(current_range)
        return ranges

    def get_block_len(self):
        length = 0
        for v in self.block_contents:
            if isinstance(v, str):
                length += len(v)
            else:
                length += 1
        return length

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


if __name__ == '__main__':
    from common.FountianParser import FountainParser
    parser = FountainParser()
    with open("test.fountain", "rb") as f:
        parser.parse(f.read().decode("utf-8"))
    block = parser.blocks[47]
    print(block, block.exclude_styles(0, block.get_block_len()))
    for cont in block.block_contents:
        if isinstance(cont, str):
            print(len(cont), end=' ')
        else:
            print(cont, end=' ')
    print()
