import re
import textwrap
from enum import IntEnum
from typing import Optional
from PySide6 import QtGui


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


class Block:
    def __init__(self, block_type: BlockType, block_contents: list):
        self.block_type: BlockType = block_type
        self.block_contents: list = block_contents

    @classmethod
    def from_text(cls, block_type: BlockType, block_contents: str):
        return cls(block_type, style_contents(block_contents))

    def fix_contents(self):
        return un_style_contents(self.block_contents)

    def __repr__(self):
        return f"{self.block_type.name} block: {repr(self.block_contents)}"


class RenderBlock(Block):
    def __init__(self, block_type: BlockType, block_contents):
        super().__init__(block_type, block_contents)
        self.starting_line = 0
        self.line_height = 0
        self.line_split = []

    @property
    def ending_line(self):
        return self.starting_line + self.line_height

    @classmethod
    def from_block(cls, block: Block):
        return cls(block.block_type, block.block_contents)

    def draw_line(self, painter: QtGui.QPainter, x_pos, y_pos, line_i):
        if line_i >= self.line_height:
            return ""
        current_style = set()
        line_split_c = self.line_split.copy()
        while line_i > 0 and line_split_c:
            v = line_split_c.pop(0)
            if isinstance(v, str):
                continue
            if v == Style.LINE_BREAK:
                line_i -= 1
                continue
            if v in current_style:
                current_style.remove(v)
            else:
                current_style.add(v)

        font = painter.font()
        if self.block_type == BlockType.SCENE_HEADING:
            font.setWeight(QtGui.QFont.Weight.Bold)
        else:
            font.setWeight(QtGui.QFont.Weight.Normal)
        painter.setFont(font)

        line_length = 0
        while line_split_c:
            v = line_split_c.pop(0)
            if isinstance(v, str):
                font = painter.font()
                font.setItalic(Style.ITALICS in current_style)
                font.setBold(Style.BOLD in current_style)
                font.setUnderline(Style.UNDERLINE in current_style)
                painter.setFont(font)
                painter.drawText(x_pos, y_pos, v)
                x_pos += painter.fontMetrics().horizontalAdvance(v)
                line_length += len(v)
                continue
            if v == Style.LINE_BREAK:
                line_i -= 1
                break
            if v in current_style:
                current_style.remove(v)
            else:
                current_style.add(v)

        return line_length

    def update_line_height(self, last_block: Optional['RenderBlock']):
        if last_block:
            self.starting_line = last_block.ending_line
            block_advances = self.block_type not in (BlockType.DIALOGUE, BlockType.PARENTHETICAL, BlockType.PAGE_BREAK)
            if block_advances and last_block.block_type != BlockType.PAGE_BREAK:
                different_type = self.block_type != last_block.block_type
                if self.block_type not in (BlockType.ACTION, BlockType.NOTE) or different_type:
                    self.starting_line += 1
        else:
            self.starting_line = 1

        # Character must fit dialogue underneath
        if self.block_type == BlockType.CHARACTER and self.starting_line % LINES_PER_PAGE > LINES_PER_PAGE - 2:
            self.starting_line += self.starting_line % LINES_PER_PAGE
        elif self.block_type == BlockType.PAGE_BREAK:
            self.line_height = LINES_PER_PAGE - self.starting_line % LINES_PER_PAGE + 1
            return

        length_wrap = {
            BlockType.CHARACTER: 58-43,
            BlockType.DIALOGUE: 35,
            BlockType.PARENTHETICAL: 32
        }.get(self.block_type, 58)

        def process_style(text_2: str):
            if "\n" in text_2:
                result = [Style.LINE_BREAK]
                for text_ in text_2.splitlines():
                    result.extend(process_style(text_))
                    result.append(Style.LINE_BREAK)
                return result[1:-1]
            elif g := re.match(r"^(.*)(?<!\\)\*\*(\S.*)(?<![\\\s])\*\*(.*)$", text_2):
                return process_style(g.group(1)) + [
                    Style.BOLD, g.group(2), Style.BOLD
                ] + process_style(g.group(3))
            elif g := re.match(r"^(.*)(?<!\\)\*(\S.*)(?<![\\\s])\*(.*)$", text_2):
                return process_style(g.group(1)) + [
                    Style.ITALICS, g.group(2), Style.ITALICS
                ] + process_style(g.group(3))
            elif g := re.match(r"^(.*)(?<!\\)_(\S.*)(?<![\\\s])_(.*)$", text_2):
                return process_style(g.group(1)) + [
                    Style.UNDERLINE, g.group(2), Style.UNDERLINE
                ] + process_style(g.group(3))
            return [text_2.replace(r"\*", '*').replace(r"\_", "_")]
        self.line_split = process_style(textwrap.fill(self.block_contents, width=length_wrap))
        print(self.line_split)
        self.line_height = self.line_split.count(Style.LINE_BREAK) + 1

    def revert_to_normal(self):
        result = ""
        line_split_c = self.line_split.copy()
        while line_split_c:
            v = line_split_c.pop(0)
            if isinstance(v, str):
                result += v.replace("*", r'\*').replace("_", r"\_")
                continue
            if v == Style.LINE_BREAK:
                continue
            if v == Style.ITALICS:
                result += "*"
            elif v == Style.BOLD:
                result += "**"
            else:
                result += "_"
        self.block_contents = result
