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

    LINE_BREAK = 1


class Block:
    def __init__(self, block_type: BlockType, block_contents):
        self.block_type: BlockType = block_type
        self.block_contents: str = block_contents

    def fix_contents(self):
        self.block_contents = self.block_contents.replace("\n", " ")

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

    def get_line(self, line_i):
        if line_i >= len(self.line_split):
            return ""
        return self.line_split[line_i]

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

        self.line_split = textwrap.wrap(self.block_contents, width=length_wrap)
        self.line_height = len(self.line_split)
