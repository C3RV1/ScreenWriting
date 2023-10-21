from PySide6 import QtWidgets, QtGui
from common.Blocks import RenderBlock, BlockType, LINES_PER_PAGE
from common.FountianParser import FountainParser


class ScriptRenderer(QtWidgets.QWidget):
    PAGE_MARGIN = 50
    SPACING_BETWEEN_PAGES = 50
    LINE_SPACING = 3

    def __init__(self):
        super().__init__()
        self.scroll_position = 0  # in lines hundreds
        self.blocks: list[RenderBlock] = []
        self.cursor_line = 0
        self.cursor_character = 0

        self.last_block = -1
        self.last_character_block = -1

    def render_until_page_end(self):
        pass

    def scroll_units_to_lines(self, su):
        return su * LINES_PER_PAGE / 100

    def lines_to_pixels(self, painter: QtGui.QPainter, lines):
        return lines * painter.fontMetrics().height()

    def scroll_units_to_pixels(self, painter: QtGui.QPainter, su):
        return int(su * LINES_PER_PAGE * painter.fontMetrics().height()) // 100

    def find_first_block_of_page(self, page_i):
        for i, block in enumerate(self.blocks):
            if block.block_type == BlockType.CHARACTER:
                self.last_character_block = i
            if block.ending_line > page_i * LINES_PER_PAGE:
                return i
        return len(self.blocks)

    def render_more_contd(self, painter: QtGui.QPainter, pixel_start, page_i, is_more):
        if self.last_character_block == -1:
            return
        x_pos = 30 + (43-9) * painter.fontMetrics().maxWidth()

        character_block = self.blocks[self.last_character_block]

        page_complete_height = self.lines_to_pixels(painter, LINES_PER_PAGE)
        page_complete_height += self.PAGE_MARGIN * 2
        page_complete_height += self.SPACING_BETWEEN_PAGES

        page_start = page_i * page_complete_height - pixel_start
        page_start += self.SPACING_BETWEEN_PAGES / 2
        y_pos = page_start + self.PAGE_MARGIN
        y_pos += self.lines_to_pixels(painter, LINES_PER_PAGE if is_more else -1)
        painter.drawText(x_pos, y_pos, ("(MORE)" if is_more else character_block.block_contents + " (CONT'D)"))

    def draw_page(self, painter: QtGui.QPainter, page_i, pixel_start):
        if self.last_block == -1:
            self.last_block = self.find_first_block_of_page(page_i)

        if self.last_block >= len(self.blocks):
            return False
        page_complete_height = self.lines_to_pixels(painter, LINES_PER_PAGE)
        page_complete_height += self.PAGE_MARGIN * 2
        page_complete_height += self.SPACING_BETWEEN_PAGES

        page_start = page_i * page_complete_height - pixel_start
        page_start += self.SPACING_BETWEEN_PAGES / 2

        page_height = self.lines_to_pixels(painter, LINES_PER_PAGE) + self.PAGE_MARGIN * 2
        page_width = (55 + 10 + 5) * painter.fontMetrics().maxWidth()

        painter.fillRect(30, page_start, page_width, page_height,
                         QtGui.QColor(50, 50, 50))

        painter.setPen(QtGui.QColor('white'))

        while self.last_block < len(self.blocks):
            block = self.blocks[self.last_block]
            if block.block_type == BlockType.PAGE_BREAK:
                return page_start + page_height < self.height()
            elif block.block_type == BlockType.CHARACTER:
                self.last_character_block = self.last_block
            characters_padding = {
                BlockType.ACTION: 19-9,
                BlockType.SCENE_HEADING: 19-9,
                BlockType.CHARACTER: 43-9,
                BlockType.DIALOGUE: 29-9,
                BlockType.PARENTHETICAL: 33-9,
                BlockType.TRANSITION: 19-9,
                BlockType.CENTERED: 43-9,
                BlockType.NOTE: 19-9,
                BlockType.DUAL_DIALOGUE: 43-9
            }[block.block_type]
            x_pos = 30 + characters_padding * painter.fontMetrics().maxWidth()

            # Starting to render block

            line_in_page = block.starting_line - LINES_PER_PAGE * page_i
            line_in_block = max(0, -line_in_page)
            line_in_page = max(0, line_in_page)

            if line_in_block != 0 and block.block_type in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                self.render_more_contd(painter, pixel_start, page_i, False)

            while line_in_block < block.line_height and line_in_page < LINES_PER_PAGE:
                y_pos = page_start + self.PAGE_MARGIN
                y_pos += self.lines_to_pixels(painter, line_in_page)
                painter.drawText(x_pos, y_pos, block.get_line(line_in_block))
                line_in_block += 1
                line_in_page += 1

            if line_in_block == block.line_height:
                self.last_block += 1
            else:
                if block.block_type in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                    self.render_more_contd(painter, pixel_start, page_i, True)

            if line_in_page >= LINES_PER_PAGE:
                if line_in_block < block.line_height or block.block_type in (BlockType.DIALOGUE, BlockType.PARENTHETICAL):
                    break
                break

            # Finished rendering block

        return page_start + page_height < self.height()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter()
        painter.begin(self)
        painter.setFont(QtGui.QFont("Courier", 12))

        page_complete_height = self.lines_to_pixels(painter, LINES_PER_PAGE)
        page_complete_height += self.PAGE_MARGIN * 2
        page_complete_height += self.SPACING_BETWEEN_PAGES
        pixel_start = self.scroll_position
        page_i = self.scroll_position // page_complete_height
        self.last_block = -1
        self.last_character_block = -1
        while self.draw_page(painter, page_i, pixel_start):
            page_i += 1

        painter.end()


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
            render_block = RenderBlock.from_block(block)

            last_block = render_blocks[-1] if render_blocks else None
            render_block.update_line_height(last_block)

            render_blocks.append(render_block)

        self.script_renderer = ScriptRenderer()
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
