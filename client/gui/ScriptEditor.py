import math

from PySide6 import QtWidgets, QtGui

from common.BlockPatches import *
from common.Blocks import Style, BlockType, LINES_PER_PAGE
from client.gui.DisplayLayout import LineBlock
from common.FountianParser import FountainParser

CHARACTER_PADDING = {
    BlockType.CHARACTER: 43-9,
    BlockType.DIALOGUE: 29-9,
    BlockType.PARENTHETICAL: 33-9,
    BlockType.CENTERED: 43-9,
    BlockType.DUAL_DIALOGUE: 43-9
}

DEFAULT_CHARACTER_PADDING = 19-9


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
            patch.add_adapting(BlockTextRemoveChange(
                view_range.block_start,
                view_range.block_end - view_range.block_start,
                view_range.block_i)
            )
        return patch

    def add_at_end(self, new_text: str) -> BlockPatch:
        patch = BlockPatch()
        view_range = self.cursor_view_range[-1]
        patch.add_change(BlockTextAddChange(view_range.block_end, [new_text], view_range.block_i))
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


class InnerScriptEditor(QtWidgets.QWidget):
    PAGE_MARGIN = 50
    SPACING_BETWEEN_PAGES = 50
    LINE_SPACING = 3
    X_PADDING = 30

    def __init__(self, update_scrollbar):
        super().__init__()
        self.scroll_position = 0  # pixels
        self.update_scrollbar = update_scrollbar
        self.blocks: list[LineBlock] = []
        self.starting_cursor = Cursor(self.blocks)
        self.ending_cursor = Cursor(self.blocks)
        self.mouse_down = False

        self.last_block = -1
        self.last_character_block = -1

        self.page_complete_height = 0

        self.setFocusPolicy(QtGui.Qt.FocusPolicy.ClickFocus)
        self.line_height = 0
        self.space_width = 0

        self.show_cursors = False

    def set_blocks(self, blocks: list[Block]):
        self.blocks = blocks
        self.starting_cursor.blocks = blocks
        self.ending_cursor.blocks = blocks

    def lines_to_pixels(self, lines):
        return lines * self.line_height

    def find_first_block_of_page(self, page_i):
        for i, block in enumerate(self.blocks):
            if block.block_type == BlockType.CHARACTER:
                self.last_character_block = i
            elif block.block_type not in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                self.last_character_block = -1
            if block.ending_line > page_i * LINES_PER_PAGE:
                return i
        return len(self.blocks)

    def render_more_contd(self, painter: QtGui.QPainter, pixel_start, page_i, is_more):
        if self.last_character_block == -1:
            return
        x_pos = self.X_PADDING + CHARACTER_PADDING[BlockType.CHARACTER] * self.space_width

        character_block = self.blocks[self.last_character_block]

        page_start = page_i * self.page_complete_height - pixel_start
        page_start += self.SPACING_BETWEEN_PAGES / 2
        y_pos = page_start + self.PAGE_MARGIN
        y_pos += self.lines_to_pixels(-1 if not is_more else LINES_PER_PAGE)
        if not is_more:
            x_pos, _ = self.draw_with_style(painter, x_pos, y_pos, character_block.line_broken_text,
                                            max_line=1)
            self.draw_with_style(painter, x_pos, y_pos, [" (CONT'D)"])
        else:
            self.draw_with_style(painter, x_pos, y_pos, ["(MORE)"])

    def draw_with_style(self, painter: QtGui.QPainter, x_pos, y_pos, style_text: list,
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
        x_start = x_pos
        style_text = style_text.copy()
        c_start_line, c_start_char = normalize_cursor_to_block(cursor_start)
        c_end_line, c_end_char = normalize_cursor_to_block(cursor_end)
        c_start_line -= line_start
        c_end_line -= line_start
        block = self.blocks[self.last_block]
        while style_text and max_line != 0:
            v = style_text.pop(0)
            if isinstance(v, str):
                if line_start > 0:
                    continue

                def draw_text(text, is_highlighted):
                    nonlocal x_pos, painter
                    font = painter.font()
                    pen = painter.pen()
                    if is_highlighted and self.show_cursors:
                        painter.setBackground(QtGui.QColor('white'))
                        painter.setBackgroundMode(QtGui.Qt.BGMode.OpaqueMode)
                        pen.setColor(QtGui.QColor('black'))
                    else:
                        painter.setBackgroundMode(QtGui.Qt.BGMode.TransparentMode)
                        pen.setColor(QtGui.QColor('white'))
                    painter.setPen(pen)
                    font.setItalic(Style.ITALICS in current_style)
                    font.setBold(Style.BOLD in current_style)
                    font.setUnderline(Style.UNDERLINE in current_style)
                    painter.setFont(font)
                    painter.drawText(x_pos, y_pos, text)
                    x_pos += len(text) * self.space_width

                if block.block_type == BlockType.PARENTHETICAL and line_start == 0:
                    x_pos -= self.space_width
                    draw_text("(", False)

                def draw_cursor(cursor_start_line, cursor_start_char):
                    if cursor_start_line == 0 and self.show_cursors:
                        if len(v) >= cursor_start_char >= 0:
                            cursor_start_pos = x_pos + len(v[:cursor_start_char]) * self.space_width
                            height = painter.fontMetrics().height()
                            painter.drawLine(cursor_start_pos - 1, y_pos-height+5, cursor_start_pos - 1, y_pos+2)
                draw_cursor(c_start_line, c_start_char)
                draw_cursor(c_end_line, c_end_char)

                # Draw text highlighted
                if c_start_line == 0 == c_end_line:
                    # End and start on same line
                    print(c_start_char, c_end_char)
                    if c_start_char < 0:
                        c_start_char = 0
                    if c_end_char < 0:
                        c_end_char = 0
                    draw_text(v[:c_start_char], False)
                    draw_text(v[c_start_char:c_end_char], True)
                    draw_text(v[c_end_char:], False)
                    c_start_char -= len(v)
                    c_end_char -= len(v)
                elif c_start_line == 0:
                    # Starting line to end
                    if c_start_char < 0:
                        c_start_char = 0
                    draw_text(v[:c_start_char], False)
                    draw_text(v[c_start_char:], True)
                    c_start_char -= len(v)
                elif c_end_line == 0:
                    if c_end_char < 0:
                        c_end_char = 0
                    # From starting line to end
                    draw_text(v[:c_end_char], True)
                    draw_text(v[c_end_char:], False)
                    c_end_char -= len(v)
                    pass
                elif c_start_line < 0 < c_end_line:
                    # Whole line selected
                    draw_text(v, True)
                else:
                    draw_text(v, False)

                if block.block_type == BlockType.PARENTHETICAL and len(style_text) == 0:
                    draw_text(")", False)
            if v == Style.LINE_BREAK:
                if line_start <= 0:
                    y_pos += self.lines_to_pixels(1)
                    x_pos = x_start
                line_start -= 1
                max_line -= 1
                c_start_line -= 1
                c_end_line -= 1
                continue
            if v in current_style:
                current_style.remove(v)
            else:
                current_style.add(v)
        return x_pos, y_pos

    def draw_page(self, painter: QtGui.QPainter, page_i, pixel_start):
        if self.last_block == -1:
            self.last_block = self.find_first_block_of_page(page_i)

        if self.last_block >= len(self.blocks):
            return False

        page_start = page_i * self.page_complete_height - pixel_start
        page_start += self.SPACING_BETWEEN_PAGES / 2

        page_height = self.lines_to_pixels(LINES_PER_PAGE) + self.PAGE_MARGIN * 2
        page_width = (55 + 19) * self.space_width

        painter.fillRect(self.X_PADDING, page_start, page_width, page_height,
                         QtGui.QColor(50, 50, 50))

        painter.setPen(QtGui.QColor('white'))

        first_cursor = min(self.starting_cursor, self.ending_cursor)
        second_cursor = max(self.starting_cursor, self.ending_cursor)

        while self.last_block < len(self.blocks):
            block = self.blocks[self.last_block]
            if block.block_type == BlockType.PAGE_BREAK:
                line_in_page = block.line_start - LINES_PER_PAGE * page_i
                line_in_page = max(0, line_in_page)
                if line_in_page + block.line_height >= LINES_PER_PAGE:
                    break
            elif block.block_type == BlockType.CHARACTER:
                self.last_character_block = self.last_block
            characters_padding = CHARACTER_PADDING.get(block.block_type, DEFAULT_CHARACTER_PADDING)
            x_pos = self.X_PADDING + characters_padding * self.space_width

            # Starting to render block

            line_in_page = block.line_start - LINES_PER_PAGE * page_i
            line_in_block = max(0, -line_in_page)
            line_in_page = max(0, line_in_page)

            if line_in_block != 0 and block.block_type in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                self.render_more_contd(painter, pixel_start, page_i, False)

            y_pos = page_start + self.PAGE_MARGIN
            y_pos += self.lines_to_pixels(line_in_page)

            self.draw_with_style(painter, x_pos, y_pos, block.line_broken_text,
                                 line_start=line_in_block, max_line=LINES_PER_PAGE-line_in_page,
                                 cursor_start=first_cursor, cursor_end=second_cursor)

            if line_in_page + block.line_height < LINES_PER_PAGE:
                self.last_block += 1
            else:
                if block.block_type in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                    self.render_more_contd(painter, pixel_start, page_i, True)

            if line_in_page + block.line_height >= LINES_PER_PAGE:
                break

            # Finished rendering block

        return page_start + page_height < self.height()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter()
        painter.begin(self)
        painter.setFont(QtGui.QFont("Courier", 12))
        self.line_height = painter.fontMetrics().height()
        self.space_width = painter.fontMetrics().horizontalAdvance(" ")

        self.page_complete_height = self.lines_to_pixels(LINES_PER_PAGE)
        self.page_complete_height += self.PAGE_MARGIN * 2
        self.page_complete_height += self.SPACING_BETWEEN_PAGES
        pixel_start = self.scroll_position
        page_i = self.scroll_position // self.page_complete_height
        self.last_block = -1
        self.last_character_block = -1
        while self.draw_page(painter, page_i, pixel_start):
            page_i += 1

        painter.end()

    def ensure_cursor_visible(self):
        cursor_page = self.blocks[self.ending_cursor.block_i].line_start // LINES_PER_PAGE
        cursor_offset = cursor_page * self.page_complete_height
        page_line = self.blocks[self.ending_cursor.block_i].line_start % LINES_PER_PAGE
        page_line += self.ending_cursor.line_in_block
        cursor_offset += self.lines_to_pixels(page_line + 1)
        cursor_offset += self.SPACING_BETWEEN_PAGES / 2
        cursor_offset += self.PAGE_MARGIN
        if self.scroll_position > cursor_offset - self.line_height - self.PAGE_MARGIN:
            self.scroll_position = cursor_offset - self.line_height - self.PAGE_MARGIN
            self.update_wheel()
        if self.scroll_position + self.height() < cursor_offset:
            self.scroll_position = cursor_offset + self.line_height + 5 - self.height()
            self.update_wheel()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        updated_cursor = True
        if event.key() == QtGui.Qt.Key.Key_Left:
            self.ending_cursor.move_char(-1)
        elif event.key() == QtGui.Qt.Key.Key_Right:
            self.ending_cursor.move_char(1)
        elif event.key() == QtGui.Qt.Key.Key_Up:
            self.ending_cursor.move_line(-1)
        elif event.key() == QtGui.Qt.Key.Key_Down:
            self.ending_cursor.move_line(1)
        else:
            updated_cursor = False
        if updated_cursor:
            self.starting_cursor = self.ending_cursor.copy()
            self.ensure_cursor_visible()
            self.repaint()
            return

        if event.key() == QtGui.Qt.Key.Key_Backspace:
            if self.starting_cursor != self.ending_cursor:
                print("Different: Deleting region")
                cursor_view = self.starting_cursor - self.ending_cursor
                patch = cursor_view.delete()
                self.apply_patch(patch)
            else:
                if self.starting_cursor.char_in_line == 0 and self.starting_cursor.line_in_block == 0:
                    # Remove block and join with prev
                    return
                self.starting_cursor.move_char(-1)
                cursor_view = self.starting_cursor - self.ending_cursor
                patch = cursor_view.delete()
                self.apply_patch(patch)
                print("Deleting single character")
        else:
            if event.text() == "":
                return
            cursor_view = self.starting_cursor - self.ending_cursor
            patch = cursor_view.add_at_end(event.text())
            self.apply_patch(patch)

        # TODO: Create cursor views into the blocks.

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        delta = event.angleDelta().y() // 8
        self.scroll_position -= delta
        self.update_wheel()
        self.repaint()

    def update_wheel(self):
        page_count = int(math.ceil(self.blocks[-1].ending_line / LINES_PER_PAGE))
        self.scroll_position = min(self.scroll_position, self.page_complete_height * page_count - self.height())
        self.scroll_position = max(self.scroll_position, 0)
        self.update_scrollbar(0, self.page_complete_height * page_count - self.height(), self.scroll_position,
                              self.page_complete_height)

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        self.show_cursors = True
        self.repaint()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.show_cursors = False
        self.repaint()

    def pixel_position_to_cursor_position(self, pos_x, pos_y, cursor: Cursor):
        pixel_position = pos_y + self.scroll_position + self.line_height
        pixel_page = pixel_position // self.page_complete_height
        pixel_in_page = pixel_position % self.page_complete_height
        line = pixel_page * LINES_PER_PAGE
        padding_before_line = self.SPACING_BETWEEN_PAGES / 2
        padding_before_line += self.PAGE_MARGIN

        # Whether to accept that the next block line is over the current line
        # Instead of current block ending after the line.
        # This is done so that when you click between pages the cursor
        # Snaps to the previous page.
        accept_next_block_over = False
        if pixel_in_page >= self.page_complete_height - padding_before_line:
            line += LINES_PER_PAGE - 1
            accept_next_block_over = True
        elif padding_before_line <= pixel_in_page:
            line += (pixel_in_page - padding_before_line) // self.lines_to_pixels(1)
        line = min(line, LINES_PER_PAGE * (pixel_page + 1) - 1)
        spaces_from_left = (pos_x - self.X_PADDING) // self.space_width

        for i, block in enumerate(self.blocks):
            next_block = self.blocks[i+1] if i < len(self.blocks) - 1 else None
            next_block_over = False
            if next_block:
                next_block_over = next_block.line_start > line
            if block.ending_line > line or (next_block_over and accept_next_block_over):
                cursor.block_i = i
                cursor.line_in_block = min(line - block.line_start, block.line_height - 1)
                cursor.line_in_block = max(cursor.line_in_block, 0)
                padding = CHARACTER_PADDING.get(block.block_type, DEFAULT_CHARACTER_PADDING)
                cursor.char_in_line = int(spaces_from_left - padding)
                cursor.char_in_line = min(
                    cursor.char_in_line,
                    block.get_line_length(cursor.line_in_block)
                )
                cursor.char_in_line = max(cursor.char_in_line, 0)
                break
        else:
            block = self.blocks[-1]
            cursor.block_i = len(self.blocks) - 1
            cursor.line_in_block = block.line_height - 1
            cursor.char_in_line = block.get_line_length(cursor.line_in_block)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        self.mouse_down = True
        self.pixel_position_to_cursor_position(event.position().x(), event.position().y(), self.starting_cursor)
        self.pixel_position_to_cursor_position(event.position().x(), event.position().y(), self.ending_cursor)
        self.repaint()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self.mouse_down = False
        self.pixel_position_to_cursor_position(event.position().x(), event.position().y(), self.ending_cursor)
        self.repaint()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self.mouse_down:
            return
        self.pixel_position_to_cursor_position(event.position().x(), event.position().y(), self.ending_cursor)
        self.ensure_cursor_visible()
        self.repaint()

    def apply_patch(self, patch: BlockPatch):
        s_block_i, s_block_pos = self.starting_cursor.to_block_pos()
        e_block_i, e_block_pos = self.ending_cursor.to_block_pos()

        patch.apply_on_blocks(self.blocks)

        for block_i in range(len(self.blocks)):
            last_block = self.blocks[block_i - 1] if block_i > 0 else None
            self.blocks[block_i].update_line_height(last_block)

        s_block_i, s_block_pos = patch.map_point(s_block_i, s_block_pos)
        e_block_i, e_block_pos = patch.map_point(e_block_i, e_block_pos)
        print(s_block_i, s_block_pos, e_block_i, e_block_pos)

        self.starting_cursor.from_block_pos(s_block_i, s_block_pos)
        self.ending_cursor.from_block_pos(e_block_i, e_block_pos)

        self.repaint()


class ScriptEditor(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.zoom = 1

        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        fountain_parser = FountainParser()
        with open("Big Fish.fountain", "rb") as f:
            fountain_parser.parse(f.read().decode("utf-8"))

        render_blocks = []
        for i, block in enumerate(fountain_parser.blocks):
            render_block = LineBlock.from_block(block)

            last_block = render_blocks[-1] if render_blocks else None
            render_block.update_line_height(last_block)

            render_blocks.append(render_block)

        self.script_renderer = InnerScriptEditor(self.update_scrollbar)
        self.script_renderer.set_blocks(render_blocks)
        self.grid_layout.addWidget(self.script_renderer, 0, 0)

        self.vertical_scrollbar = QtWidgets.QScrollBar()
        self.vertical_scrollbar.setMinimum(0)
        self.vertical_scrollbar.setMaximum(5000)
        self.vertical_scrollbar.setOrientation(QtGui.Qt.Orientation.Vertical)
        self.vertical_scrollbar.valueChanged.connect(self.scroll_changed)
        self.grid_layout.addWidget(self.vertical_scrollbar, 0, 1)

        self.horizontal_scrollbar = QtWidgets.QScrollBar()
        self.horizontal_scrollbar.setOrientation(QtGui.Qt.Orientation.Horizontal)
        self.grid_layout.addWidget(self.horizontal_scrollbar, 1, 0)

    def scroll_changed(self, value):
        self.script_renderer.scroll_position = value
        self.script_renderer.repaint()

    def update_scrollbar(self, min_scroll, max_scroll, value, page_step):
        self.vertical_scrollbar.setMaximum(max_scroll)
        self.vertical_scrollbar.setMinimum(min_scroll)
        self.vertical_scrollbar.setValue(value)
        self.vertical_scrollbar.setPageStep(page_step)
