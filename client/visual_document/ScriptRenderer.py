from enum import Enum

from common.BlockPatches import *
from common.Blocks import Style, BlockType, LINES_PER_PAGE

from client.visual_document.DisplayLayout import LineBlock
from client.visual_document.Cursor import Cursor, CHARACTER_PADDING, DEFAULT_CHARACTER_PADDING


class Alignment(float, Enum):
    LEFT = 0
    CENTER = 0.5
    RIGHT = 1


class ScriptRenderer:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.blocks: list[LineBlock] = []
        self.starting_cursor = Cursor(self.blocks)
        self.ending_cursor = Cursor(self.blocks)

        self.last_block = -1
        self.last_character_block = -1

        self.show_cursors = False

    def base_page_drawer(self, page_i: int):
        pass

    def separator_drawer(self, y_pos: int, page_i: int):
        pass

    def cursor_drawer(self, x_pos: int, y_pos: int, page_i: int):
        pass

    def set_current_weight(self, block_type: BlockType):
        pass

    def text_drawer(self, x_pos: int, y_pos: int, page_i: int, text: str, is_highlighted: str,
                    current_style: set[Style]):
        pass

    def get_block_alignment(self, block_type: BlockType) -> Alignment:
        if block_type == BlockType.CENTERED:
            return Alignment.CENTER
        if block_type == BlockType.TRANSITION:
            return Alignment.RIGHT
        return Alignment.LEFT

    def set_blocks(self, blocks: list[Block]):
        self.blocks = blocks
        self.ensure_all_are_line_blocks()
        self.starting_cursor.blocks = blocks
        self.ending_cursor.blocks = blocks

    def find_first_block_of_page(self, page_i):
        for i, block in enumerate(self.blocks):
            if block.block_type == BlockType.CHARACTER:
                self.last_character_block = i
            elif block.block_type not in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                self.last_character_block = -1
            if block.ending_line > page_i * LINES_PER_PAGE:
                return i
        return len(self.blocks)

    def render_more_contd(self, page_i, is_more):
        if self.last_character_block == -1:
            return
        x_pos = CHARACTER_PADDING[BlockType.CHARACTER]

        character_block = self.blocks[self.last_character_block]

        y_pos = -1 if not is_more else LINES_PER_PAGE
        if not is_more:
            x_pos, _ = self.draw_with_style(x_pos, y_pos, page_i, character_block.line_broken_text,
                                            max_line=1)
            char_name = "".join([v for v in character_block.line_broken_text if isinstance(v, str)])
            if not char_name.strip().endswith(" (CONT'D)"):
                self.draw_with_style(x_pos, y_pos, page_i, [" (CONT'D)"])
        else:
            self.draw_with_style(x_pos, y_pos, page_i, ["(MORE)"])

    def draw_with_style(self, x_pos, y_pos, page_i, style_text: list, alignment=Alignment.LEFT,
                        line_start=0, max_line=-1, cursor_start: Cursor = None, cursor_end: Cursor = None):
        def normalize_cursor_to_block(cursor: Cursor):
            if not cursor:
                return -1, 0
            if cursor.block_i < self.last_block:
                return -1, 0
            elif cursor.block_i > self.last_block:
                return 1000000, 0  # Exceed max line
            return cursor.line_in_block, cursor.char_in_line

        current_style = set()
        block = self.blocks[self.last_block]
        x_start = x_pos
        current_line = 0
        x_pos -= block.get_line_length(line_start) * alignment.value
        style_text = style_text.copy()
        c_start_line, c_start_char = normalize_cursor_to_block(cursor_start)
        c_end_line, c_end_char = normalize_cursor_to_block(cursor_end)
        c_start_line -= line_start
        c_end_line -= line_start

        def draw_cursor(cursor_start_line, cursor_start_char):
            if not self.show_cursors:
                return
            if 0 <= cursor_start_line < max_line:
                cursor_start_pos = x_pos + cursor_start_char
                cursor_y_pos = y_pos + cursor_start_line
                self.cursor_drawer(cursor_start_pos, cursor_y_pos, page_i)

        draw_cursor(c_start_line, c_start_char)
        draw_cursor(c_end_line, c_end_char)

        while style_text and current_line < max_line:
            v = style_text.pop(0)

            def draw_text(text, is_highlighted):
                nonlocal x_pos
                self.text_drawer(x_pos, y_pos, page_i, text, is_highlighted, current_style)
                x_pos += len(text)

            if isinstance(v, str):
                if current_line < line_start:
                    continue

                if self.set_current_weight is not None:
                    self.set_current_weight(block.block_type)

                if block.block_type == BlockType.PARENTHETICAL and line_start == 0:
                    x_pos -= 1
                    draw_text("(", False)

                # Draw text highlighted
                if c_start_line == current_line == c_end_line:
                    # End and start on same line
                    if c_start_char < 0:
                        c_start_char = 0
                    if c_end_char < 0:
                        c_end_char = 0
                    draw_text(v[:c_start_char], False)
                    draw_text(v[c_start_char:c_end_char], True and self.show_cursors)
                    draw_text(v[c_end_char:], False)
                    c_start_char -= len(v)
                    c_end_char -= len(v)
                elif c_start_line == current_line:
                    # Starting line to end
                    if c_start_char < 0:
                        c_start_char = 0
                    draw_text(v[:c_start_char], False)
                    draw_text(v[c_start_char:], True and self.show_cursors)
                    c_start_char -= len(v)
                elif c_end_line == current_line:
                    if c_end_char < 0:
                        c_end_char = 0
                    # From starting line to end
                    draw_text(v[:c_end_char], True and self.show_cursors)
                    draw_text(v[c_end_char:], False)
                    c_end_char -= len(v)
                    pass
                elif c_start_line < current_line < c_end_line:
                    # Whole line selected
                    draw_text(v, True and self.show_cursors)
                else:
                    draw_text(v, False)
            if v == Style.LINE_BREAK:
                if current_line >= line_start:
                    y_pos += 1
                    x_pos = x_start
                current_line += 1
                x_pos -= block.get_line_length(current_line) * alignment.value
                continue
            if v in current_style:
                current_style.remove(v)
            else:
                current_style.add(v)
            if block.block_type == BlockType.PARENTHETICAL and len(style_text) == 0:
                draw_text(")", False)
        return x_pos, y_pos

    def draw_page(self, page_i):
        self.last_block = self.find_first_block_of_page(page_i)

        if self.last_block >= len(self.blocks):
            return False

        self.base_page_drawer(page_i)

        first_cursor = min(self.starting_cursor, self.ending_cursor)
        second_cursor = max(self.starting_cursor, self.ending_cursor)

        while self.last_block < len(self.blocks):
            block = self.blocks[self.last_block]
            if block.block_type == BlockType.SEPARATOR:
                line_in_page = block.line_start
                line_in_page = max(0, line_in_page)
                self.separator_drawer(line_in_page, page_i)
                if line_in_page + block.line_height >= LINES_PER_PAGE:
                    break
                self.last_block += 1
                continue
            elif block.block_type == BlockType.CHARACTER:
                self.last_character_block = self.last_block

            characters_padding = CHARACTER_PADDING.get(block.block_type, DEFAULT_CHARACTER_PADDING)
            x_pos = characters_padding

            # Starting to render block

            line_in_page = block.line_start - LINES_PER_PAGE * page_i
            line_in_block = max(0, -line_in_page)
            line_in_page = max(0, line_in_page)

            if line_in_block != 0 and block.block_type in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                self.render_more_contd(page_i, False)

            self.draw_with_style(x_pos, line_in_page, page_i, block.line_broken_text,
                                 line_start=line_in_block, max_line=LINES_PER_PAGE-line_in_page,
                                 cursor_start=first_cursor, cursor_end=second_cursor,
                                 alignment=self.get_block_alignment(block.block_type))

            if line_in_page + block.line_height < LINES_PER_PAGE:
                self.last_block += 1
            else:
                if block.block_type in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                    self.render_more_contd(page_i, True)

            if line_in_page + block.line_height >= LINES_PER_PAGE:
                break

            # Finished rendering block

    def ensure_all_are_line_blocks(self):
        line_block_idx = None
        for block_i in range(len(self.blocks)):
            block = self.blocks[block_i]
            if not isinstance(block, LineBlock):
                line_block = LineBlock.from_block(block)
                line_block.split_at_length()
                self.blocks[block_i] = line_block
                if line_block_idx is None:
                    line_block_idx = block_i
            if line_block_idx is None and block.contents_modified:
                line_block_idx = block_i
        if line_block_idx is None:
            return

        for block_i in range(line_block_idx, len(self.blocks)):
            last_block = self.blocks[block_i - 1] if block_i > 0 else None
            block = self.blocks[block_i]
            if block.contents_modified:
                block.split_at_length()
            block.update_line_height(last_block)

    def apply_patch(self, patch: BlockPatch):
        s_block_i, s_block_pos = self.starting_cursor.to_block_pos()
        e_block_i, e_block_pos = self.ending_cursor.to_block_pos()

        patch.apply_on_blocks(self.blocks)

        self.ensure_all_are_line_blocks()

        s_block_i, s_block_pos = patch.map_point(s_block_i, s_block_pos)
        e_block_i, e_block_pos = patch.map_point(e_block_i, e_block_pos)

        self.starting_cursor.from_block_pos(s_block_i, s_block_pos)
        self.ending_cursor.from_block_pos(e_block_i, e_block_pos)
