import re
import typing
from enum import IntEnum


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


class Block:
    def __init__(self, block_type: BlockType, block_contents):
        self.block_type: BlockType = block_type
        self.block_contents: str = block_contents

    def fix_contents(self):
        self.block_contents = self.block_contents.replace("\n", " ")

    def __repr__(self):
        return f"{self.block_type.name} block: {repr(self.block_contents)}"


class TitlePage:
    def __init__(self):
        self.keys = {}

    def read_title(self, lines: list[str], line_i: int):
        while True:
            line = lines[line_i].strip()
            if ":" not in line:
                break
            name = line.strip(":")[0]
            line_i += 1
            values = []
            if first_value := ":".join(line.split(":"))[1:] != "":
                values.append(first_value)
            while True:
                line = lines[line_i]
                if not line.startswith(" "):
                    break
                line_i += 1
                line = line.strip()
                values.append(line)
            self.keys[name] = values
        if len(self.keys) > 0 and lines[line_i] == "":
            line_i += 1
        return line_i


class FountainParser:
    SCENE_HEADING_STARTS = [
        "INT", "EXT", "EST", "INT./EXT", "INT/EXT", "I/E"
    ]

    def __init__(self):
        self.title_page = TitlePage()
        self.lines = []
        self.line_i = 0
        self.block_i = 0
        self.blocks: list[Block] = []

    def remove_prev_empty(self):
        if self.line_i > 0:
            if self.lines[self.line_i - 1] != "":
                return False
            if self.blocks[-1].block_type == BlockType.ACTION:
                self.blocks = self.blocks[:-1]  # Remove empty action
        return True

    def remove_next_empty(self):
        if self.line_i < len(self.lines) - 1:
            if self.lines[self.line_i + 1] != "":
                return False
            self.line_i += 1
        return True

    def remove_prev_and_next_empty(self):
        remove_prev = False
        remove_next = False

        if self.line_i > 0:
            if self.lines[self.line_i - 1] != "":
                return False
            remove_prev = True

        if self.line_i < len(self.lines) - 1:
            if self.lines[self.line_i + 1] != "":
                return False
            remove_next = True

        if remove_prev:
            if self.blocks[-1].block_type == BlockType.ACTION:
                self.blocks = self.blocks[:-1]  # Remove empty action
        if remove_next:
            self.line_i += 1
        return True

    def match_dual_dialogue(self):
        line = self.lines[self.line_i]

        if (line.startswith("@") and line.endswith("^")) or re.match("^[A-Z0-9.()]*[A-Z][A-Z0-9.()]*\\s*\\^$", line):
            if not self.remove_prev_empty():
                return False
            self.blocks.append(Block(BlockType.DUAL_DIALOGUE, line[:-1].strip()))
            return True
        return False

    def match_character(self):
        line = self.lines[self.line_i]

        if line.startswith("@"):
            if not self.remove_prev_empty():
                return False
            self.blocks.append(Block(BlockType.CHARACTER, line[1:].strip()))
            return True

        if re.match("^[A-Z0-9.()\\s]*[A-Z][A-Z0-9.()\\s]*$", line):
            if not self.remove_prev_empty():
                return False
            self.blocks.append(Block(BlockType.CHARACTER, line.strip()))
            return True
        return False

    def match_scene(self):
        line = self.lines[self.line_i]
        is_scene = False
        if line.startswith("."):
            is_scene = True
            line = line[1:]
        for scene_start in self.SCENE_HEADING_STARTS:
            if line.startswith(scene_start + ".") or line.startswith(scene_start + " "):
                is_scene = True
                break

        if is_scene:
            if not self.remove_prev_and_next_empty():
                return False
            self.blocks.append(Block(BlockType.SCENE_HEADING, line))
            return True
        return False

    def match_transition(self):
        line = self.lines[self.line_i]
        is_transition = False
        if line.startswith(">"):
            is_transition = True
            line = line[1:].strip()
        elif line.isupper() and line.endswith("TO:"):
            is_transition = True
            line = line.strip()

        if is_transition:
            if not self.remove_prev_and_next_empty():
                return False
            self.blocks.append(Block(BlockType.TRANSITION, line))
            return True
        return False

    def match_action(self):
        line = self.lines[self.line_i]
        if line.startswith("!"):
            line = line[1:]
        self.blocks.append(Block(BlockType.ACTION, line))

    def match_centered(self):
        line = self.lines[self.line_i]
        if line.startswith(">") and line.endswith("<"):
            self.blocks.append(Block(BlockType.CENTERED, line[1:-1].strip()))
            return True
        return False

    def match_page_break(self):
        line = self.lines[self.line_i]
        if line.strip() == "===":
            if not self.remove_prev_and_next_empty():
                return False
            self.blocks.append(Block(BlockType.PAGE_BREAK, ""))
            return True
        else:
            return False

    def match_note(self):  # non-standard but whatever
        line = self.lines[self.line_i]
        if line.startswith("// "):
            if not self.remove_prev_and_next_empty():
                return False
            self.blocks.append(Block(BlockType.NOTE, line[3:]))
            return True
        else:
            return False

    def parse(self, text: str):
        self.lines = text.splitlines()
        self.line_i = 0
        title_end = self.title_page.read_title(self.lines, self.line_i)
        self.lines = self.lines[title_end:]

        while self.line_i < len(self.lines):
            if self.lines[self.line_i].startswith("!"):
                self.match_action()
                self.line_i += 1
                continue
            if self.match_page_break():
                continue
            if self.match_dual_dialogue():
                self.line_i += 1
                self.parse_dialogue_and_parenthetical()
                continue
            if self.match_character():
                self.line_i += 1
                self.parse_dialogue_and_parenthetical()
                continue
            if self.match_scene():
                self.line_i += 1
                continue
            if self.match_centered():
                self.line_i += 1
                continue
            if self.match_transition():
                self.line_i += 1
                continue
            if self.match_note():
                self.line_i += 1
                continue
            self.match_action()
            self.line_i += 1

    def parse_dialogue_and_parenthetical(self):
        while self.line_i < len(self.lines):
            line = self.lines[self.line_i]
            self.line_i += 1
            if line == "":
                break
            if line.startswith("(") and line.endswith(")"):
                self.blocks.append(Block(BlockType.PARENTHETICAL, line[1:-1]))
                continue
            if line == "  ":
                self.blocks.append(Block(BlockType.DIALOGUE, ""))
                continue
            self.blocks.append(Block(BlockType.DIALOGUE, line))

    def serialize_dialogue_and_parenthetical(self):
        while self.block_i < len(self.blocks):
            block = self.blocks[self.block_i]
            if block.block_type == BlockType.DIALOGUE:
                if block.block_contents == "":
                    self.lines.append("  ")
                else:
                    self.lines.append(block.block_contents)
                self.block_i += 1
            elif block.block_type == BlockType.PARENTHETICAL:
                self.lines.append("(" + block.block_contents + ")")
                self.block_i += 1
            else:
                break
        self.lines.append("")

    def serialize(self):
        self.lines = []
        self.block_i = 0
        while self.block_i < len(self.blocks):
            block = self.blocks[self.block_i]
            self.block_i += 1

            block.fix_contents()
            if block.block_type == BlockType.ACTION:
                self.lines.append("!" + block.block_contents)
            elif block.block_type == BlockType.SCENE_HEADING:
                if len(self.lines) > 0:
                    if self.lines[-1] != "":
                        self.lines.append("")
                self.lines.append("." + block.block_contents)
                self.lines.append("")
            elif block.block_type == BlockType.CHARACTER:
                if len(self.lines) > 0:
                    if self.lines[-1] != "":
                        self.lines.append("")
                self.lines.append("@" + block.block_contents)
                self.serialize_dialogue_and_parenthetical()
            elif block.block_type == BlockType.DUAL_DIALOGUE:
                if len(self.lines) > 0:
                    if self.lines[-1] != "":
                        self.lines.append("")
                self.lines.append("@" + block.block_contents + " ^")
                self.serialize_dialogue_and_parenthetical()
            elif block.block_type == BlockType.TRANSITION:
                if len(self.lines) > 0:
                    if self.lines[-1] != "":
                        self.lines.append("")
                self.lines.append(">" + block.block_contents)
                self.lines.append("")
            elif block.block_type == BlockType.CENTERED:
                self.lines.append(">" + block.block_contents + "<")
            elif block.block_type == BlockType.PAGE_BREAK:
                if len(self.lines) > 0:
                    if self.lines[-1] != "":
                        self.lines.append("")
                self.lines.append("")
                self.lines.append("===")
            elif block.block_type == BlockType.NOTE:
                if len(self.lines) > 0:
                    if self.lines[-1] != "":
                        self.lines.append("")
                self.lines.append("// " + block.block_contents)
                self.lines.append("")
        return "\n".join(self.lines)


if __name__ == '__main__':
    parser = FountainParser()
    with open("test.fountain", "r") as f:
        parser.parse(f.read())
    parser2 = FountainParser()
    parser2.parse(parser.serialize())
    print(parser.serialize())
    for i in range(len(parser.blocks)):
        print(parser.blocks[i], parser2.blocks[i])
    print(len(parser.blocks), len(parser2.blocks))
