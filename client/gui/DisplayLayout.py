import textwrap
from typing import Optional

from common.Blocks import Block, BlockType, Style

LINES_PER_PAGE = 57


class LineBlock(Block):
    def __init__(self, block_type, block_contents):
        super().__init__(block_type, block_contents)
        self.line_start = 0
        self.line_height = 0
        self.line_broken_text = []

    @classmethod
    def from_block(cls, block: Block):
        return cls(block.block_type, block.block_contents)

    @property
    def ending_line(self):
        return self.line_start + self.line_height

    def get_line_length(self, line_i):
        line_length = 0
        queue_style = self.line_broken_text.copy()
        while line_i > 0 and queue_style:
            v = queue_style.pop(0)
            if v == Style.LINE_BREAK:
                line_i -= 1
        while queue_style:
            v = queue_style.pop(0)
            if isinstance(v, str):
                line_length += len(v)
                continue
            if v == Style.LINE_BREAK:
                break
        return line_length

    def cursor_pos_to_block_pos(self, cursor_line, cursor_char):
        block_pos = 0
        queue_style = self.line_broken_text.copy()
        while cursor_line > 0 and queue_style:
            v = queue_style.pop(0)
            if v == Style.LINE_BREAK:
                cursor_line -= 1
            elif isinstance(v, str):
                block_pos += len(v)
            else:
                block_pos += 1

        while queue_style and cursor_char > 0:
            v = queue_style.pop(0)
            if isinstance(v, str):
                if len(v) < cursor_char:
                    cursor_char -= len(v)
                    block_pos += len(v)
                else:
                    block_pos += cursor_char
                    break
            elif v == Style.LINE_BREAK:
                continue
            else:
                block_pos += 1
        return block_pos

    def update_line_height(self, last_block: Optional['LineBlock']):
        length_wrap = {
            BlockType.CHARACTER: 58 - 43,
            BlockType.DIALOGUE: 35,
            BlockType.PARENTHETICAL: 32
        }.get(self.block_type, 58)

        complete_text = "".join([s for s in self.block_contents if isinstance(s, str)])
        line_split = textwrap.wrap(complete_text, width=length_wrap)

        self.line_broken_text = []
        block_contents = self.block_contents.copy()
        for line in line_split:
            while True:
                while not isinstance(block_contents[0], str):
                    self.line_broken_text.append(block_contents.pop(0))
                text = block_contents.pop(0)
                if len(text) < len(line):
                    self.line_broken_text.append(text)
                    line = line[len(text):]
                elif len(text) > len(line):
                    self.line_broken_text.append(text[:len(line)])
                    self.line_broken_text.append(Style.LINE_BREAK)
                    block_contents.insert(0, text[len(line)+1:])
                    break
                else:
                    self.line_broken_text.append(text)
                    self.line_broken_text.append(Style.LINE_BREAK)
                    break
        self.line_broken_text = self.line_broken_text[:-1]

        if last_block:
            self.line_start = last_block.ending_line
            block_advances = self.block_type not in (
                BlockType.DIALOGUE,
                BlockType.PARENTHETICAL,
                BlockType.PAGE_BREAK
            )
            if block_advances and last_block.block_type != BlockType.PAGE_BREAK:
                different_type = self.block_type != last_block.block_type
                if self.block_type not in (BlockType.ACTION, BlockType.NOTE) or different_type:
                    self.line_start += 1
        else:
            self.line_start = 1

        # Character must fit dialogue underneath
        if self.block_type == BlockType.CHARACTER and self.line_start % LINES_PER_PAGE > LINES_PER_PAGE - 2:
            self.line_start += self.line_start % LINES_PER_PAGE
        elif self.block_type == BlockType.PAGE_BREAK:
            self.line_height = LINES_PER_PAGE - self.line_start % LINES_PER_PAGE + 1
            return

        self.line_height = self.line_broken_text.count(Style.LINE_BREAK) + 1
