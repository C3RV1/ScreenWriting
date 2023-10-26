import unittest
from common.BlockPatches import *
from common.Blocks import Style


class BlockPatchTest(unittest.TestCase):
    def get_blocks(self):
        return [
            Block(BlockType.ACTION, ["Text ", Style.ITALICS, "styled", Style.ITALICS, " hehe."]),
            Block(BlockType.CHARACTER, ["First character"]),
            Block(BlockType.DIALOGUE, []),  # empty dialogue
            Block(BlockType.DIALOGUE, ["Next dialogue."])
        ]

    def test_add_block(self):
        blocks = self.get_blocks()
        patch = BlockPatch()
        patch.add_change(
            BlockAddChange(
                1,
                Block(
                    BlockType.TRANSITION,
                    [Style.ITALICS, "Added transition", Style.ITALICS]
                )
            )
        )
        patch.apply_on_blocks(blocks)
        self.assertEqual(blocks[1].block_type, BlockType.TRANSITION)
        self.assertEqual(blocks[1].block_contents, [Style.ITALICS, "Added transition", Style.ITALICS])
        self.assertEqual(blocks[2].block_contents, ["First character"])

    def test_add_data_start(self):
        blocks = self.get_blocks()
        patch = BlockPatch()
        patch.add_change(
            BlockDataAddChange(
                0,
                [Style.ITALICS, "Added", Style.ITALICS],
                2
            )
        )
        patch.apply_on_blocks(blocks)
        self.assertEqual(blocks[2].block_contents, [Style.ITALICS, "Added", Style.ITALICS])

    def test_remove_block(self):
        blocks = self.get_blocks()
        patch = BlockPatch()
        patch.add_change(
            BlockRemoveChange(1)
        )
        patch.apply_on_blocks(blocks)
        self.assertEqual(blocks[1].block_type, BlockType.DIALOGUE)
        self.assertEqual(blocks[1].block_contents, [])


if __name__ == '__main__':
    unittest.main()
