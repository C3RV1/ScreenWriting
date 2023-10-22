import math

from PySide6 import QtWidgets, QtGui
from common.Blocks import Style, BlockType, LINES_PER_PAGE
from client.gui.DisplayLayout import LineBlock
from common.FountianParser import FountainParser

CHARACTER_PADDING = {
    BlockType.CHARACTER: 43,
    BlockType.DIALOGUE: 29,
    BlockType.PARENTHETICAL: 33,
    BlockType.CENTERED: 43,
    BlockType.DUAL_DIALOGUE: 43
}

DEFAULT_CHARACTER_PADDING = 19


class Cursor:

    def __init__(self):
        self.block_i = 0
        self.line_in_block = 0
        self.char_in_line = 0

    def move_block(self, blocks: list[LineBlock], block_move):
        old_block = blocks[self.block_i]
        self.block_i += block_move
        block_moved = False
        if self.block_i < 0:
            self.block_i = 0
            self.line_in_block = 0
            self.char_in_line = 0
            block_moved = True
        elif self.block_i >= len(blocks):
            self.block_i = len(blocks) - 1
            self.line_in_block = blocks[self.block_i].line_height - 1
            self.char_in_line = blocks[self.block_i].get_line_length(self.line_in_block)
            block_moved = True
        new_block = blocks[self.block_i]

        characters_padding_new = CHARACTER_PADDING.get(new_block.block.block_type, DEFAULT_CHARACTER_PADDING)
        characters_padding_old = CHARACTER_PADDING.get(old_block.block.block_type, DEFAULT_CHARACTER_PADDING)
        self.char_in_line += characters_padding_old - characters_padding_new
        return block_moved

    def move_line(self, blocks: list[LineBlock], line_move):
        self.line_in_block += line_move
        moved_line = False
        if self.line_in_block < 0:
            if self.move_block(blocks, -1):
                return False
            self.line_in_block = blocks[self.block_i].line_height - 1
            moved_line = True
        elif self.line_in_block >= blocks[self.block_i].line_height:
            if self.move_block(blocks, 1):
                return False
            self.line_in_block = 0
            moved_line = True
        self.char_in_line = min(blocks[self.block_i].get_line_length(self.line_in_block), self.char_in_line)
        self.char_in_line = max(0, self.char_in_line)
        return moved_line

    def move_char(self, blocks: list[LineBlock], char_move):
        self.char_in_line += char_move
        if self.char_in_line < 0:
            if self.move_line(blocks, -1):
                self.char_in_line = blocks[self.block_i].get_line_length(self.line_in_block)
                return True
            self.char_in_line = blocks[self.block_i].get_line_length(self.line_in_block)
        elif self.char_in_line > blocks[self.block_i].get_line_length(self.line_in_block):
            if self.move_line(blocks, 1):
                self.char_in_line = 0
                return True
            self.char_in_line = 0
        self.char_in_line = min(blocks[self.block_i].get_line_length(self.line_in_block), self.char_in_line)


class ScriptRenderer(QtWidgets.QWidget):
    PAGE_MARGIN = 50
    SPACING_BETWEEN_PAGES = 50
    LINE_SPACING = 3

    def __init__(self, update_scrollbar):
        super().__init__()
        self.scroll_position = 0  # pixels
        self.update_scrollbar = update_scrollbar
        self.blocks: list[LineBlock] = []
        self.cursor = Cursor()

        self.last_block = -1
        self.last_character_block = -1

        self.page_complete_height = 0

        self.setFocusPolicy(QtGui.Qt.FocusPolicy.ClickFocus)
        self.line_height = 0

    def render_until_page_end(self):
        pass

    def lines_to_pixels(self, lines):
        return lines * self.line_height

    def find_first_block_of_page(self, page_i):
        for i, block in enumerate(self.blocks):
            if block.block.block_type == BlockType.CHARACTER:
                self.last_character_block = i
            if block.ending_line > page_i * LINES_PER_PAGE:
                return i
        return len(self.blocks)

    def render_more_contd(self, painter: QtGui.QPainter, pixel_start, page_i, is_more):
        if self.last_character_block == -1:
            return
        x_pos = 30 + (43-9) * painter.fontMetrics().horizontalAdvance(" ")

        character_block = self.blocks[self.last_character_block]

        page_start = page_i * self.page_complete_height - pixel_start
        page_start += self.SPACING_BETWEEN_PAGES / 2
        y_pos = page_start + self.PAGE_MARGIN
        y_pos += self.lines_to_pixels(LINES_PER_PAGE if not is_more else -1)
        if not is_more:
            x_pos, _ = self.draw_with_style(painter, x_pos, y_pos, character_block.line_broken_text,
                                            max_line=1)
            self.draw_with_style(painter, x_pos, y_pos, [" (CONT'D)"])
        else:
            self.draw_with_style(painter, x_pos, y_pos, ["(MORE)"])

    def draw_with_style(self, painter: QtGui.QPainter, x_pos, y_pos, style_text: list,
                        line_start=0, max_line=-1, cursor=None):
        current_style = set()
        x_start = x_pos
        style_text = style_text.copy()
        lines_until_cursor = -1 if cursor is None else cursor.line_in_block - line_start
        chars_until_cursor = -1 if cursor is None else cursor.char_in_line
        while style_text and max_line != 0:
            v = style_text.pop(0)
            if isinstance(v, str):
                if line_start > 0:
                    continue
                if lines_until_cursor == 0 and cursor:
                    if len(v) >= chars_until_cursor >= 0:
                        cursor_start = x_pos + painter.fontMetrics().horizontalAdvance(v[:chars_until_cursor])
                        height = painter.fontMetrics().height()
                        painter.drawLine(cursor_start-1, y_pos-height+5, cursor_start-1, y_pos+2)
                    chars_until_cursor -= len(v)
                font = painter.font()
                font.setItalic(Style.ITALICS in current_style)
                font.setBold(Style.BOLD in current_style)
                font.setUnderline(Style.UNDERLINE in current_style)
                painter.setFont(font)
                painter.drawText(x_pos, y_pos, v)
                x_pos += painter.fontMetrics().horizontalAdvance(v)
                continue
            if v == Style.LINE_BREAK:
                if line_start <= 0:
                    y_pos += self.lines_to_pixels(1)
                    x_pos = x_start
                line_start -= 1
                max_line -= 1
                lines_until_cursor -= 1
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
        page_width = (55 + 19 + 9) * painter.fontMetrics().horizontalAdvance(" ")

        painter.fillRect(30, page_start, page_width, page_height,
                         QtGui.QColor(50, 50, 50))

        painter.setPen(QtGui.QColor('white'))

        while self.last_block < len(self.blocks):
            block = self.blocks[self.last_block]
            if block.block.block_type == BlockType.PAGE_BREAK:
                return page_start + page_height < self.height()
            elif block.block.block_type == BlockType.CHARACTER:
                self.last_character_block = self.last_block
            characters_padding = CHARACTER_PADDING.get(block.block.block_type, DEFAULT_CHARACTER_PADDING)
            x_pos = 30 + characters_padding * painter.fontMetrics().horizontalAdvance(" ")

            # Starting to render block

            line_in_page = block.line_start - LINES_PER_PAGE * page_i
            line_in_block = max(0, -line_in_page)
            line_in_page = max(0, line_in_page)

            if line_in_block != 0 and block.block.block_type in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                self.render_more_contd(painter, pixel_start, page_i, True)

            y_pos = page_start + self.PAGE_MARGIN
            y_pos += self.lines_to_pixels(line_in_page)
            cursor = None
            if self.cursor.block_i == self.last_block:
                cursor = self.cursor
            self.draw_with_style(painter, x_pos, y_pos, block.line_broken_text,
                                 line_start=line_in_block, max_line=LINES_PER_PAGE-line_in_page,
                                 cursor=cursor)

            if line_in_page + block.line_height < LINES_PER_PAGE:
                self.last_block += 1
            else:
                if block.block.block_type in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                    self.render_more_contd(painter, pixel_start, page_i, False)

            if line_in_page + block.line_height >= LINES_PER_PAGE:
                break

            # Finished rendering block

        return page_start + page_height < self.height()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter()
        painter.begin(self)
        painter.setFont(QtGui.QFont("Courier", 12))
        self.line_height = painter.fontMetrics().height()

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
        cursor_page = self.blocks[self.cursor.block_i].line_start // LINES_PER_PAGE
        cursor_offset = cursor_page * self.page_complete_height
        page_line = self.blocks[self.cursor.block_i].line_start % LINES_PER_PAGE
        page_line += self.cursor.line_in_block
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
            self.cursor.move_char(self.blocks, -1)
        elif event.key() == QtGui.Qt.Key.Key_Right:
            self.cursor.move_char(self.blocks, 1)
        elif event.key() == QtGui.Qt.Key.Key_Up:
            self.cursor.move_line(self.blocks, -1)
        elif event.key() == QtGui.Qt.Key.Key_Down:
            self.cursor.move_line(self.blocks, 1)
        else:
            updated_cursor = False
        if updated_cursor:
            self.ensure_cursor_visible()
            self.repaint()

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


class EditingText(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.zoom = 1

        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        fountain_parser = FountainParser()
        with open("test.fountain", "rb") as f:
            fountain_parser.parse(f.read().decode("utf-8"))

        render_blocks = []
        for i, block in enumerate(fountain_parser.blocks):
            render_block = LineBlock(block)

            last_block = render_blocks[-1] if render_blocks else None
            render_block.update_line_height(last_block)

            render_blocks.append(render_block)

        self.script_renderer = ScriptRenderer(self.update_scrollbar)
        self.script_renderer.blocks = render_blocks
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
        print(f"Changed to {value}")
        self.script_renderer.scroll_position = value
        self.script_renderer.repaint()

    def update_scrollbar(self, min_scroll, max_scroll, value, page_step):
        self.vertical_scrollbar.setMaximum(max_scroll)
        self.vertical_scrollbar.setMinimum(min_scroll)
        self.vertical_scrollbar.setValue(value)
        self.vertical_scrollbar.setPageStep(page_step)
