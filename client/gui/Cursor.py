from client.gui.DisplayLayout import LineBlock
from common.BlockPatches import *
from common.Blocks import Block, BlockType

CHARACTER_PADDING = {
    BlockType.CHARACTER: 43-5,
    BlockType.DIALOGUE: 29-5,
    BlockType.PARENTHETICAL: 33-5,
    BlockType.CENTERED: 43-5,
    BlockType.DUAL_DIALOGUE: 43-5
}

DEFAULT_CHARACTER_PADDING = 19-5


class CursorSetPositionChange(BlockChanged):
    def __init__(self, position, block_i, cursor_i):
        super().__init__()
        self.block_id = block_i
        self.position = position
        self.cursor_i = cursor_i  # 0 for first, 1 for second?


class CursorViewRange:
    def __init__(self, block_i: int, block_start: int, block_length: int):
        self.block_i = block_i
        self.block_start = block_start
        self.block_length = block_length

    @property
    def block_end(self):
        return self.block_start + self.block_length

    def __repr__(self):
        return f"({self.block_i}: {self.block_start}-{self.block_end})"


class CursorView:
    def __init__(self, blocks: list[Block], cursor_view_range: list[CursorViewRange]):
        self.blocks = blocks
        self.cursor_view_range: list[CursorViewRange] = cursor_view_range

    def delete(self) -> BlockPatch:
        patch = BlockPatch()
        for view_range in self.cursor_view_range:
            # Todo remove block if contents fully removed
            patch.add_adapting(BlockDataRemoveChange(
                view_range.block_start,
                view_range.block_end - view_range.block_start,
                view_range.block_i)
            )
        return patch

    def add_at_end(self, new_text: str) -> BlockPatch:
        patch = BlockPatch()
        view_range = self.cursor_view_range[-1]
        patch.add_change(BlockDataAddChange(view_range.block_end, [new_text], view_range.block_i))
        return patch

    def __repr__(self):
        return f"<Cursor View into=[{', '.join([repr(r) for r in self.cursor_view_range])}>"


class Cursor:
    def __init__(self, blocks: list[LineBlock]):
        self.blocks: list[LineBlock] = blocks
        self.block_i = 0
        self.line_in_block = 0
        self.char_in_line = 0

    def move_block(self, block_move):
        old_block = self.blocks[self.block_i]
        self.block_i += block_move
        block_moved = False
        if self.block_i < 0:
            self.block_i = 0
            self.line_in_block = 0
            self.char_in_line = 0
            block_moved = True
        elif self.block_i >= len(self.blocks):
            self.block_i = len(self.blocks) - 1
            self.line_in_block = self.blocks[self.block_i].line_height - 1
            self.char_in_line = self.blocks[self.block_i].get_line_length(self.line_in_block)
            block_moved = True
        new_block = self.blocks[self.block_i]

        characters_padding_new = CHARACTER_PADDING.get(new_block.block_type, DEFAULT_CHARACTER_PADDING)
        characters_padding_old = CHARACTER_PADDING.get(old_block.block_type, DEFAULT_CHARACTER_PADDING)
        self.char_in_line += characters_padding_old - characters_padding_new
        return block_moved

    def move_line(self, line_move):
        self.line_in_block += line_move
        moved_line = False
        if self.line_in_block < 0:
            if self.move_block(-1):
                return False
            self.line_in_block = self.blocks[self.block_i].line_height - 1
            moved_line = True
        elif self.line_in_block >= self.blocks[self.block_i].line_height:
            if self.move_block(1):
                return False
            self.line_in_block = 0
            moved_line = True
        self.char_in_line = min(self.blocks[self.block_i].get_line_length(self.line_in_block), self.char_in_line)
        self.char_in_line = max(0, self.char_in_line)
        return moved_line

    def move_char(self, char_move):
        self.char_in_line += char_move
        if self.char_in_line < 0:
            if self.move_line(-1):
                self.char_in_line = self.blocks[self.block_i].get_line_length(self.line_in_block)
                return True
            self.char_in_line = self.blocks[self.block_i].get_line_length(self.line_in_block)
        elif self.char_in_line > self.blocks[self.block_i].get_line_length(self.line_in_block):
            if self.move_line(1):
                self.char_in_line = 0
                return True
            self.char_in_line = 0
        self.char_in_line = min(self.blocks[self.block_i].get_line_length(self.line_in_block), self.char_in_line)

    def copy(self):
        cursor = Cursor(self.blocks)
        cursor.char_in_line = self.char_in_line
        cursor.line_in_block = self.line_in_block
        cursor.block_i = self.block_i
        return cursor

    def __sub__(self, other: 'Cursor'):
        # Should return a CursorView, which includes all the ranges and blocks
        # Between the cursors, without including the style ones.

        # These cursor views should provide an easy interface for adding
        # or removing characters...
        cursor_view_blocks = []
        first_cursor = min(self, other).copy()
        second_cursor = max(self, other).copy()

        current_block = first_cursor.block_i
        while current_block <= second_cursor.block_i:
            block = self.blocks[first_cursor.block_i]

            if current_block == first_cursor.block_i:
                block_start = block.cursor_pos_to_block_pos(first_cursor.line_in_block, first_cursor.char_in_line)
            else:
                block_start = 0

            if current_block == second_cursor.block_i:
                block_end = block.cursor_pos_to_block_pos(second_cursor.line_in_block, second_cursor.char_in_line)
            else:
                block_end = block.get_block_len()

            ranges = block.exclude_styles(block_start, block_end)
            for range_ in ranges:
                cursor_view_blocks.append(CursorViewRange(current_block, range_[0], range_[1]))

            current_block += 1
        return CursorView(self.blocks, cursor_view_blocks)

    def to_block_pos(self):
        block = self.blocks[self.block_i]
        return self.block_i, block.cursor_pos_to_block_pos(self.line_in_block, self.char_in_line)

    def from_block_pos(self, block_i, block_pos):
        self.block_i = block_i
        block = self.blocks[block_i]
        self.line_in_block, self.char_in_line = block.block_pos_to_cursor_pos(block_pos)

    def __eq__(self, other: 'Cursor'):
        # Should compare the block_i, char_in_line, and line_in_block
        block_eq = self.block_i == other.block_i
        line_eq = self.line_in_block == other.line_in_block
        char_eq = self.char_in_line == other.char_in_line
        return block_eq and line_eq and char_eq

    def __lt__(self, other: 'Cursor'):
        # Should compare the block_i, char_in_line, and line_in_block
        if self.block_i != other.block_i:
            return self.block_i < other.block_i
        if self.line_in_block != other.line_in_block:
            return self.line_in_block < other.line_in_block
        return self.char_in_line < other.char_in_line

    def __le__(self, other: 'Cursor'):
        # Should compare the block_i, char_in_line, and line_in_block
        return self < other or self == other