import io
import struct

from common.Blocks import Block, encode_styled, decode_styled, BlockType
import typing
import copy
from enum import IntEnum


class BlockChangeType(IntEnum):
    NOTHING = 0
    ADD_BLOCK = 1
    REMOVE_BLOCK = 2
    ADD_TEXT = 3
    REMOVE_TEXT = 4
    CHANGED_TYPE = 5


class BlockChanged:
    COUNT = 0
    DELETE_WITH_BLOCK = True

    def __init__(self):
        self.start = 0
        self.length = 0
        self.block_id = 0
        self.change_id = BlockChanged.COUNT
        BlockChanged.COUNT += 1

    @property
    def end(self):
        return self.start + self.length

    def apply_to_blocks(self, blocks: list[Block]):
        pass

    def size_data(self):
        return 0

    def map(self, other: 'BlockChanged') -> tuple['BlockChanged']:
        # This function should not modify changes if they are not in their domain
        return other,

    def map_point(self, block_i, block_pos):
        return block_i, block_pos

    def partial_copy(self, start, end) -> 'BlockChanged':
        pass

    def copy(self):
        raise NotImplemented()

    def to_bytes(self):
        return struct.pack("!B", BlockChangeType.NOTHING)


class BlockAddChange(BlockChanged):
    DELETE_WITH_BLOCK = False

    def __init__(self, block_id, block: Block):
        super().__init__()
        self.block_id = block_id
        self.block = block

    def apply_to_blocks(self, blocks: list[Block]):
        blocks.insert(self.block_id, self.block)

    def map_point(self, block_i, block_pos):
        if block_i >= self.block_id:
            return block_i + 1, block_pos
        return block_i, block_pos

    def map(self, other: 'BlockChanged') -> tuple['BlockChanged']:
        other = other.copy()
        if other.block_id > self.block_id:
            other.block_id += 1
        return other,

    def copy(self):
        return BlockAddChange(self.block_id, self.block)

    def to_bytes(self):
        return struct.pack("!BI", BlockChangeType.ADD_BLOCK, self.block_id) + self.block.to_bytes()

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO):
        block_id = struct.unpack("!I", rdr.read(4))[0]
        block = Block.from_bytes(rdr)
        return BlockAddChange(block_id, block)


class BlockRemoveChange(BlockChanged):
    DELETE_WITH_BLOCK = False

    def __init__(self, block_id):
        super().__init__()
        self.block_id = block_id

    def apply_to_blocks(self, blocks: list[Block]):
        blocks.pop(self.block_id)
        if len(blocks) > self.block_id:
            blocks[self.block_id].contents_modified = True
        elif self.block_id > 0:
            blocks[self.block_id - 1].contents_modified = True

    def map_point(self, block_i, block_pos):
        if block_i >= self.block_id:
            return max(block_i - 1, 0), block_pos
        return block_i, block_pos

    def map(self, other: 'BlockChanged') -> tuple['BlockChanged']:
        other = other.copy()
        if other.block_id == self.block_id:
            if other.DELETE_WITH_BLOCK:
                return tuple()
            return other,
        if other.block_id > self.block_id:
            other.block_id -= 1
        return other,

    def copy(self):
        return BlockRemoveChange(self.block_id)

    def to_bytes(self):
        return struct.pack("!BI", BlockChangeType.REMOVE_BLOCK, self.block_id)

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO):
        block_id = struct.unpack("!I", rdr.read(4))[0]
        return BlockRemoveChange(block_id)


class BlockDataAddChange(BlockChanged):
    DELETE_WITH_BLOCK = True

    def __init__(self, position, data, block_id):
        super().__init__()
        self.block_id = block_id
        self.start = position
        self.data = data
        self.length = 0

    def apply_to_blocks(self, blocks: list[Block]):
        block = blocks[self.block_id]
        blocks[self.block_id].contents_modified = True
        insert_position = self.start
        block_contents_copy = block.block_contents.copy()
        if insert_position == 0:
            block.block_contents = self.data + block_contents_copy
            return
        for i, block_content in enumerate(block_contents_copy):
            if isinstance(block_content, str):
                insert_position -= len(block_content)
                if insert_position == 0:
                    block.block_contents = block_contents_copy[:i+1]
                    block.block_contents.extend(self.data)
                    block.block_contents.extend(block_contents_copy[i+1:])
                    break
                elif insert_position <= 0:
                    block.block_contents = block_contents_copy[:i]
                    block.block_contents.append(block_content[:insert_position])
                    block.block_contents.extend(self.data)
                    block.block_contents.append(block_content[insert_position:])
                    block.block_contents.extend(block_contents_copy[i + 1:])
                    break
            else:
                insert_position -= 1
                if insert_position == 0:
                    block.block_contents = block_contents_copy[:i]
                    block.block_contents.extend(self.data)
                    block.block_contents.extend(block_contents_copy[i:])

    def size_data(self):
        size = 0
        for v in self.data:
            if isinstance(v, str):
                size += len(v)
            else:
                size += 1
        return size

    def map_point(self, block_i, block_pos):
        if self.block_id != block_i:
            return block_i, block_pos
        if block_pos >= self.start:
            return block_i, block_pos + self.size_data()
        return block_i, block_pos

    def map(self, other: 'BlockChanged'):
        other = other.copy()
        if other.block_id != self.block_id:
            return other,
        if other.start <= other.end <= self.start:
            return other,
        if other.start > self.start:
            other.start += self.size_data()
            return other,
        p1 = other.partial_copy(other.start, self.start)
        p2 = other.partial_copy(self.start, other.end)
        p2.start += self.size_data()
        return [p1, p2]

    def partial_copy(self, start, end) -> 'BlockChanged':
        raise ValueError("There should never be a partial copy of an add block!")

    def copy(self):
        return BlockDataAddChange(self.start, self.data, self.block_id)

    def to_bytes(self):
        return struct.pack("!BIH", BlockChangeType.ADD_TEXT, self.block_id, self.start) + encode_styled(self.data)

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO):
        block_id, start = struct.unpack("!IH", rdr.read(6))
        return BlockDataAddChange(start, decode_styled(rdr), block_id)


class BlockDataRemoveChange(BlockChanged):
    DELETE_WITH_BLOCK = True

    def __init__(self, start, length, block_id):
        super().__init__()
        self.block_id = block_id
        self.start = start
        self.length = length

    def map_point(self, block_i, block_pos):
        if self.block_id != block_i:
            return block_i, block_pos
        if block_pos <= self.start:
            return block_i, block_pos
        if self.start <= block_pos <= self.end:
            return block_i, self.start
        return block_i, block_pos - self.length

    def map(self, other: 'BlockChanged'):
        other = other.copy()
        if other.block_id != self.block_id:
            return other,
        if other.start >= self.end:
            other.start -= self.length
        elif self.start <= other.start < self.end:
            other.length -= self.end - other.start
            other.length = max(other.length, 0)
            other.start = self.start

        if self.start <= other.end <= self.end:
            other.length -= other.end - self.start
            other.length = max(other.length, 0)
        return other,

    def apply_to_blocks(self, blocks: list[Block]):
        block = blocks[self.block_id]
        blocks[self.block_id].contents_modified = True
        start = self.start
        length = self.length
        block_contents_copy = block.block_contents.copy()
        block.block_contents = []
        while start > 0 and block_contents_copy:
            v = block_contents_copy.pop(0)
            if isinstance(v, str):
                start -= len(v)
                if start < 0:
                    block.block_contents.append(v[:start])
                    block_contents_copy.insert(0, v[start:])
                    break
            else:
                start -= 1
            block.block_contents.append(v)
        while length > 0 and block_contents_copy:
            v = block_contents_copy.pop(0)
            if isinstance(v, str):
                length -= len(v)
                if length < 0:
                    block.block_contents.append(v[length:])
                    break
                elif length == 0:
                    break
            else:
                length -= 1
                if length == 0:
                    break
        block.block_contents.extend(block_contents_copy)

    def copy(self):
        return BlockDataRemoveChange(self.start, self.length, self.block_id)

    def partial_copy(self, start, end) -> 'BlockChanged':
        return BlockDataRemoveChange(start, end - start, self.block_id)

    def to_bytes(self):
        return struct.pack("!BIHH", BlockChangeType.REMOVE_TEXT, self.block_id, self.start, self.length)

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO):
        block_id, start, length = struct.unpack("!IHH", rdr.read(8))
        return BlockDataRemoveChange(start, length, block_id)


class BlockChangedType(BlockChanged):
    DELETE_WITH_BLOCK = True

    def __init__(self, block_id, block_type):
        super().__init__()
        self.block_id = block_id
        self.block_type = block_type
        self.start = 0
        self.length = 0

    def apply_to_blocks(self, blocks: list[Block]):
        blocks[self.block_id].block_type = self.block_type
        blocks[self.block_id].contents_modified = True

    def copy(self):
        return BlockChangedType(self.block_id, self.block_type)

    def to_bytes(self):
        return struct.pack("!BIB", BlockChangeType.CHANGED_TYPE, self.block_id, self.block_type)

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO):
        block_id, block_type = struct.unpack("!IB", rdr.read(5))
        return BlockChangedType(block_id, BlockType(block_type))


def change_from_bytes(rdr: io.BytesIO):
    change_type = struct.unpack("!B", rdr.read(1))[0]
    if change_type == BlockChangeType.ADD_BLOCK:
        return BlockAddChange.from_bytes(rdr)
    if change_type == BlockChangeType.REMOVE_BLOCK:
        return BlockRemoveChange.from_bytes(rdr)
    if change_type == BlockChangeType.ADD_TEXT:
        return BlockDataAddChange.from_bytes(rdr)
    if change_type == BlockChangeType.REMOVE_TEXT:
        return BlockDataRemoveChange.from_bytes(rdr)
    if change_type == BlockChangeType.CHANGED_TYPE:
        return BlockChangedType.from_bytes(rdr)
    return None


class BlockPatch:
    def __init__(self):
        self.change_queue: list[tuple[int, BlockChanged]] = []

    def set_changes_id(self, change_id):
        change_queue = self.change_queue
        self.change_queue = []
        for id_, change in change_queue:
            self.change_queue.append((change_id, change))

    def drop_changes_with_smaller_change_id(self, change_id):
        for v in self.change_queue.copy():
            id_, _change = v
            if id_ < change_id:
                self.change_queue.remove(v)

    def add_change(self, change: typing.Union[BlockChanged, 'BlockPatch']):
        if isinstance(change, BlockChanged):
            self.change_queue.append((change.change_id, change))
        else:
            self.change_queue.extend(change.change_queue)

    def add_adapting(self, change: BlockChanged):
        change = [change]
        for _id, change_queue in self.change_queue:
            change_copy = change.copy()
            change = []
            for change_ in change_copy:
                change.extend(change_queue.map(change_))
        for change_ in change:
            self.add_change(change_)

    def remove_change(self, change_id: typing.Union['BlockPatch', int]):
        if isinstance(change_id, int):
            removed_list = []
            for id_, change in self.change_queue:
                if id_ != change_id:
                    removed_list.append((id_, change))
            self.change_queue = removed_list
        else:
            removed_list = []
            remove_ids = set()
            for change_hash, change in change_id.change_queue:
                if change_hash not in remove_ids:
                    remove_ids.add(change_hash)

            for id_, change in self.change_queue:
                if id_ not in remove_ids:
                    removed_list.append((id_, change))
            self.change_queue = removed_list

    def map_point(self, block_i, block_pos):
        for _id, change in self.change_queue:
            block_i, block_pos = change.map_point(block_i, block_pos)
        return block_i, block_pos

    def rebase_to_change(self, base_change: BlockChanged):
        old_change_queue = self.change_queue
        self.change_queue = []
        for id_, change in old_change_queue:
            mapped_changes = base_change.map(change)
            for mapped_change in mapped_changes:
                self.change_queue.append((id_, mapped_change))

    def rebase_to(self, base: 'BlockPatch'):
        old_change_queue = self.change_queue
        self.change_queue = []
        for id_, change in old_change_queue:
            mapped_changes = [change]

            # Apply base to change
            for _, base_change in base.change_queue:
                old_mapped_changes = mapped_changes
                mapped_changes = []
                for old_mapped_change in old_mapped_changes:
                    mapped_change = base_change.map(old_mapped_change)
                    mapped_changes.extend(mapped_change)

            # Add result of applying
            for res in mapped_changes:
                self.change_queue.append((id_, res))

            # Apply change to base
            for mapped_change in mapped_changes:
                base.rebase_to_change(mapped_change)

    def apply_on_blocks(self, blocks: list[Block]):
        for block in blocks:
            block.contents_modified = False

        for _id, change in self.change_queue:
            change.apply_to_blocks(blocks)

        # Cleanup
        for block in blocks:
            block_contents_copy = block.block_contents
            block.block_contents = []
            for b in block_contents_copy:
                if block.block_contents:
                    if isinstance(b, str) and isinstance(block.block_contents[-1], str):
                        block.block_contents[-1] += b
                        continue
                if isinstance(b, str):
                    if b == "":  # Skip empty string
                        continue
                block.block_contents.append(b)

    def copy(self):
        r = BlockPatch()
        r.change_queue = [(id_, o.copy()) for id_, o in self.change_queue]
        return r

    def to_bytes(self) -> bytes:
        msg = struct.pack("!H", len(self.change_queue))
        for id_, changed in self.change_queue:
            msg += struct.pack("!I", id_) + changed.to_bytes()
        return msg

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO):
        changes_length = struct.unpack("!H", rdr.read(2))[0]
        change_queue = []
        for i in range(changes_length):
            id_ = struct.unpack("!I", rdr.read(4))[0]
            change = change_from_bytes(rdr)
            if change is None:
                return None
            change_queue.append((id_, change))
        patch = cls()
        patch.change_queue = change_queue
        return patch


if __name__ == '__main__':
    from common.FountianParser import FountainParser
    parser = FountainParser()
    with open("test.fountain", "rb") as f:
        parser.parse(f.read().decode("utf-8"))

    # Server just has one copy
    block_server = copy.deepcopy(parser.blocks)

    # Two local copies per client
    block_client = copy.deepcopy(parser.blocks)
    block_client_advanced = copy.deepcopy(parser.blocks)
    client1_advanced_changed = BlockPatch()

    # Two local copies per client 2
    block_client2 = copy.deepcopy(parser.blocks)
    block_client2_advanced = copy.deepcopy(parser.blocks)
    client2_advanced_changed = BlockPatch()

    # First client1 does its changes
    change1 = BlockDataAddChange(1, "hello", 1)
    change1.apply_to_blocks(block_client_advanced)
    client1_advanced_changed.add_change(change1)

    change1_1 = BlockDataRemoveChange(1, 2, 1)
    change1_1.apply_to_blocks(block_client_advanced)
    client1_advanced_changed.add_change(change1_1)

    # Then client2
    change2 = BlockDataAddChange(2, "trying", 1)
    change2.apply_to_blocks(block_client2_advanced)
    client2_advanced_changed.add_change(change2)

    # Server receives first client1
    change1_server = BlockPatch()
    change1_server.add_change(change1)
    change1_server.apply_on_blocks(block_server)

    # Sends ack to client_1
    client1_advanced_changed.remove_change(hash(change1))
    change1_server.apply_on_blocks(block_client)

    # Broadcasts to client_2
    change1_server.apply_on_blocks(block_client2)

    # Rebase advanced
    client2_advanced_changed.rebase_to(change1_server)
    block_client2_advanced = copy.deepcopy(block_client2)
    client2_advanced_changed.apply_on_blocks(block_client2_advanced)

    # Then server receives client2
    change2_server = BlockPatch()
    change2_server.add_change(change2)
    change2_server.rebase_to(change1_server)  # How many should the server keep track of??
    change2_server.apply_on_blocks(block_server)

    # Broadcasts to client_1
    change2_server.apply_on_blocks(block_client)

    # Rebase advanced
    client1_advanced_changed.rebase_to(change2_server)
    block_client_advanced = copy.deepcopy(block_client)
    client1_advanced_changed.apply_on_blocks(block_client_advanced)

    # Sends ack to client_2
    client2_advanced_changed.remove_change(hash(change2))
    change2_server.apply_on_blocks(block_client2)

    # Server receives client1_1
    change1_1_server = BlockPatch()
    change1_1_server.add_change(change1_1)
    change1_1_server.rebase_to(change2_server)  # Server also has to keep track of this
    change1_1_server.apply_on_blocks(block_server)

    # Ack to client1
    client1_advanced_changed.remove_change(hash(change1_1))
    change1_1_server.apply_on_blocks(block_client)

    # Broadcast to client2
    change1_1_server.apply_on_blocks(block_client2)

    # Rebased advanced
    client2_advanced_changed.rebase_to(change1_1_server)
    block_client2_advanced = copy.deepcopy(block_client2)
    client2_advanced_changed.apply_on_blocks(block_client2_advanced)

    print(block_server[1])
    print(block_client[1])
    print(block_client2[1])

