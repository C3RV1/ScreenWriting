import math
from typing import Optional

from PySide6 import QtWidgets, QtGui

from common.BlockPatches import *
from common.Blocks import Style, BlockType, LINES_PER_PAGE

from client.RealTimeDocumentClient import RealTimeDocumentClient

from client.visual_document.Cursor import Cursor, CHARACTER_PADDING, DEFAULT_CHARACTER_PADDING
from client.visual_document.ScriptRenderer import ScriptRenderer


class InnerScriptEditor(ScriptRenderer, QtWidgets.QWidget):
    PAGE_MARGIN = 50
    SPACING_BETWEEN_PAGES = 50
    X_PADDING = 30
    PAGE_SPACE_WIDTH = 55 + 19 + 9

    def __init__(self, update_scrollbar,
                 real_time_document: typing.Optional[RealTimeDocumentClient] = None):
        super().__init__()
        self.scroll_position = 0  # pixels
        self.update_scrollbar = update_scrollbar
        self.mouse_down = False

        self.page_complete_height = 0

        self.setFocusPolicy(QtGui.Qt.FocusPolicy.ClickFocus)
        self.line_height = 0
        self.space_width = 0

        self.rtd_c: RealTimeDocumentClient = real_time_document
        if self.rtd_c:
            self.set_blocks(self.rtd_c.blocks_advanced)
            self.rtd_c.on_rebase = self.on_rebase
            self.rtd_c.on_change = self.on_change

        self.painter: Optional[QtGui.QPainter] = None

        self.base_weight = 0
        self.bold_weight = 0

    def on_rebase(self, blocks: list[Block]):
        self.set_blocks(blocks)
        self.repaint()

    def lines_to_pixels(self, lines):
        return lines * self.line_height

    def cursor_drawer(self, x_pos: int, y_pos: int, page_i: int):
        if self.painter is None:
            return
        x_pos = self.X_PADDING + x_pos * self.space_width
        y_pos = page_i * self.page_complete_height + self.lines_to_pixels(y_pos)
        y_pos += self.SPACING_BETWEEN_PAGES / 2
        y_pos += self.PAGE_MARGIN
        y_pos -= self.scroll_position
        self.painter.drawLine(int(x_pos) - 1, int(y_pos) - self.line_height + 5,
                              int(x_pos) - 1, int(y_pos) + 2)

    def set_current_weight(self, block_type: BlockType):
        self.base_weight = QtGui.QFont.Weight.Normal
        self.bold_weight = QtGui.QFont.Weight.Bold
        if block_type == BlockType.SCENE_HEADING:
            self.base_weight = QtGui.QFont.Weight.ExtraBold
            self.bold_weight = QtGui.QFont.Weight.Black

    def text_drawer(self, x_pos: int, y_pos: int, page_i: int, text: str, is_highlighted: bool,
                    current_style: set[Style]):
        x_pos = self.X_PADDING + x_pos * self.space_width
        y_pos = page_i * self.page_complete_height + self.lines_to_pixels(y_pos)
        y_pos += self.SPACING_BETWEEN_PAGES / 2
        y_pos += self.PAGE_MARGIN
        y_pos -= self.scroll_position

        font = self.painter.font()
        pen = self.painter.pen()
        if is_highlighted and self.show_cursors:
            self.painter.setBackground(QtGui.QColor('white'))
            self.painter.setBackgroundMode(QtGui.Qt.BGMode.OpaqueMode)
            pen.setColor(QtGui.QColor('black'))
        else:
            self.painter.setBackgroundMode(QtGui.Qt.BGMode.TransparentMode)
            pen.setColor(QtGui.QColor('white'))
        self.painter.setPen(pen)
        font.setItalic(Style.ITALICS in current_style)
        if Style.BOLD in current_style:
            font.setWeight(self.bold_weight)
        else:
            font.setWeight(self.base_weight)
        font.setUnderline(Style.UNDERLINE in current_style)
        self.painter.setFont(font)
        self.painter.drawText(int(x_pos), int(y_pos), text)

    def base_page_drawer(self, page_i):
        page_start = page_i * self.page_complete_height - self.scroll_position
        page_start += self.SPACING_BETWEEN_PAGES / 2

        page_height = self.lines_to_pixels(LINES_PER_PAGE) + self.PAGE_MARGIN * 2
        page_width = self.PAGE_SPACE_WIDTH * self.space_width

        self.painter.fillRect(self.X_PADDING, page_start, page_width, page_height,
                              QtGui.QColor(50, 50, 50))

        self.painter.setPen(QtGui.QColor('white'))

    def separator_drawer(self, y_pos, page_i):
        x_pos = self.X_PADDING + DEFAULT_CHARACTER_PADDING * self.space_width
        y_pos = page_i * self.page_complete_height + self.lines_to_pixels(y_pos)
        y_pos += self.SPACING_BETWEEN_PAGES / 2
        y_pos += self.PAGE_MARGIN
        y_pos -= self.scroll_position

        self.painter.fillRect(int(x_pos + 10), int(y_pos), self.space_width * 55 - 10, 2, QtGui.QColor('white'))

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter()
        painter.begin(self)
        self.painter = painter

        painter.setFont(QtGui.QFont("Courier", 12))
        self.line_height = painter.fontMetrics().height()
        self.space_width = painter.fontMetrics().horizontalAdvance(" ")

        self.page_complete_height = self.lines_to_pixels(LINES_PER_PAGE)
        self.page_complete_height += self.PAGE_MARGIN * 2
        self.page_complete_height += self.SPACING_BETWEEN_PAGES

        page_i = self.scroll_position // self.page_complete_height
        while True:
            self.draw_page(page_i)
            if self.page_complete_height * page_i - self.scroll_position > self.height():
                break
            page_i += 1

        self.painter = None
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
                    # TODO: Join block contents with previous
                    #       Maybe functionality into BlockDataRemove?
                    if self.starting_cursor.block_i == 0:
                        return
                    patch = BlockPatch()
                    patch.add_change(BlockRemoveChange(block_id=self.starting_cursor.block_i))
                    self.apply_patch(patch)
                    self.starting_cursor.from_block_pos(
                        self.starting_cursor.block_i,
                        self.blocks[self.starting_cursor.block_i].get_block_len()
                    )
                    self.ending_cursor = self.starting_cursor.copy()
                    self.repaint()
                    return
                self.starting_cursor.move_char(-1)
                cursor_view = self.starting_cursor - self.ending_cursor
                patch = cursor_view.delete()
                self.apply_patch(patch)
                self.repaint()
        elif event.key() == QtGui.Qt.Key.Key_Return:
            cursor_view = self.starting_cursor - self.ending_cursor
            patch = cursor_view.add_block_after_last_block(BlockType.ACTION)
            self.apply_patch(patch)
            self.starting_cursor.block_i = patch.change_queue[0][1].block_id
            self.starting_cursor.line_in_block = 0
            self.starting_cursor.char_in_line = 0
            self.ending_cursor.block_i = patch.change_queue[0][1].block_id
            self.ending_cursor.line_in_block = 0
            self.ending_cursor.char_in_line = 0
            self.repaint()
        else:
            if event.text() == "":
                return
            cursor_view = self.starting_cursor - self.ending_cursor
            print(cursor_view)
            patch = cursor_view.add_text_at_end(event.text())
            self.apply_patch(patch)
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

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        self.show_cursors = True
        self.repaint()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.show_cursors = False
        self.repaint()

    def pixel_position_to_cursor_position(self, pos_x, pos_y, cursor: Cursor):
        # TODO: Might move some logic to Script Renderer.
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
            next_block = self.blocks[i + 1] if i < len(self.blocks) - 1 else None
            next_block_over = False
            if next_block:
                next_block_over = next_block.line_start > line
            if block.ending_line > line or (next_block_over and accept_next_block_over):
                cursor.block_i = i
                cursor.line_in_block = min(line - block.line_start, block.line_height - 1)
                cursor.line_in_block = max(cursor.line_in_block, 0)
                padding = CHARACTER_PADDING.get(block.block_type, DEFAULT_CHARACTER_PADDING)
                padding -= block.get_line_length(cursor.line_in_block) * self.get_block_alignment(block.block_type)
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
        self.pixel_position_to_cursor_position(event.position().x(), event.position().y(),
                                               self.starting_cursor)
        self.pixel_position_to_cursor_position(event.position().x(), event.position().y(),
                                               self.ending_cursor)
        self.repaint()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self.mouse_down = False
        self.pixel_position_to_cursor_position(event.position().x(), event.position().y(),
                                               self.ending_cursor)
        self.repaint()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self.mouse_down:
            return
        self.pixel_position_to_cursor_position(event.position().x(), event.position().y(),
                                               self.ending_cursor)
        self.ensure_cursor_visible()
        self.repaint()

    def apply_patch(self, patch: BlockPatch):
        super().apply_patch(patch)
        if self.rtd_c:
            self.rtd_c.send_change(patch)

    def on_change(self):
        self.ensure_all_are_line_blocks()


class ScriptEditor(QtWidgets.QWidget):
    def __init__(self, rtd_c: RealTimeDocumentClient):
        super().__init__()
        self.zoom = 1

        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        self.script_renderer = InnerScriptEditor(self.update_scrollbar, rtd_c)
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
