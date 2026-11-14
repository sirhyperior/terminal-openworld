"""Visible-cell sizing and safe foreground run serialization."""

import io
import os
import re
import unittest
from unittest.mock import patch

from ascii3d.presentation import GRAY_CODES, GRAY_LEVELS, StyledFrame, WHITE_ON_BLACK
from ascii3d.terminal import Terminal


ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class StyledFrameTests(unittest.TestCase):
    def test_gray_palette_has_sixteen_neutral_monotonic_levels(self):
        self.assertEqual(len(GRAY_LEVELS), 16)
        self.assertEqual(tuple(sorted(set(GRAY_LEVELS))), GRAY_LEVELS)
        self.assertEqual(GRAY_LEVELS[-1], 255)
        for level, code in zip(GRAY_LEVELS, GRAY_CODES):
            self.assertEqual(code, f"\x1b[38;2;{level};{level};{level}m")

    def test_runs_preserve_visible_cells_and_reset_each_row(self):
        rows = [".. ##@", "      "]
        frame = StyledFrame(6, 2, rows, [bytearray((2, 2, 9, 8, 8, 15)), bytearray(6)])
        encoded = frame.ansi_rows()
        self.assertEqual([ANSI.sub("", row) for row in encoded], rows)
        self.assertEqual(encoded[0].count(GRAY_CODES[2]), 1)
        self.assertEqual(encoded[0].count(GRAY_CODES[8]), 1)
        self.assertNotIn(GRAY_CODES[9], encoded[0])
        self.assertTrue(all(row.startswith("\x1b[40m") and row.endswith(WHITE_ON_BLACK)
                            for row in encoded))
        self.assertFalse(any(code in encoded[1] for code in GRAY_CODES))

    def test_blank_foreground_changes_do_not_split_a_visible_run(self):
        frame = StyledFrame(5, 1, ["x   y"], [bytearray((7, 0, 4, 15, 7))])
        encoded = frame.ansi_rows()[0]
        self.assertEqual(encoded.count(GRAY_CODES[7]), 1)
        self.assertIn("x   y", encoded)

    def test_rejects_invalid_dimensions_cells_and_style_buffers(self):
        invalid = [
            (0, 1, [""], [bytearray()]),
            (1, 0, [], []),
            (1.5, 1, ["x"], [bytearray(1)]),
            (2, 1, ["x"], [bytearray(2)]),
            (1, 2, ["x"], [bytearray(1)]),
            (1, 1, ["x"], []),
            (1, 1, ["x"], [bytearray(2)]),
            (1, 1, ["x"], [[1]]),
            (1, 1, ["x"], [bytearray((16,))]),
            (1, 1, ["\t"], [bytearray(1)]),
            (1, 1, ["\x1b"], [bytearray(1)]),
            (1, 1, ["界"], [bytearray(1)]),
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                StyledFrame(*values)


class StyledTerminalTests(unittest.TestCase):
    def test_style_byte_length_does_not_change_clear_or_final_cell(self):
        terminal = Terminal()
        first = StyledFrame(3, 2, ["abc", "deZ"], [bytearray((1, 1, 1)), bytearray((1, 1, 1))])
        second = StyledFrame(3, 2, ["ABC", "DEZ"], [bytearray((0, 9, 15)), bytearray((4, 5, 6))])
        with patch("ascii3d.terminal.os.get_terminal_size", return_value=os.terminal_size((3, 2))), \
                patch("ascii3d.terminal.sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(terminal.size(), (3, 2))
            terminal.draw(first)
            self.assertEqual(ANSI.sub("", output.getvalue()), "abc\r\ndeZ")
            self.assertFalse(output.getvalue().endswith("\n"))
            output.seek(0)
            output.truncate()
            terminal.draw(second)
            self.assertNotIn("\x1b[2J", output.getvalue())
            self.assertEqual(ANSI.sub("", output.getvalue()), "ABC\r\nDEZ")
            self.assertTrue(output.getvalue().endswith("Z" + WHITE_ON_BLACK))

    def test_centered_styled_rows_use_native_origin(self):
        terminal = Terminal(1200)
        frame = StyledFrame(60, 20, ["x" * 60] * 20, [bytearray([4] * 60) for _ in range(20)])
        with patch("ascii3d.terminal.os.get_terminal_size", return_value=os.terminal_size((100, 40))), \
                patch("ascii3d.terminal.sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(terminal.size(), (60, 20))
            terminal.draw(frame)
            self.assertTrue(output.getvalue().startswith("\x1b[2J\x1b[11;21H"))
            self.assertEqual(output.getvalue().count("\r\n\x1b[21G"), 19)

    def test_styled_then_plain_output_has_white_foreground(self):
        terminal = Terminal()
        frame = StyledFrame(1, 1, ["x"], [bytearray((0,))])
        with patch("ascii3d.terminal.sys.stdout", new_callable=io.StringIO) as output:
            terminal.draw(frame)
            terminal.draw(["Y"])
            self.assertIn(WHITE_ON_BLACK + "\x1b[1;1HY", output.getvalue())


if __name__ == "__main__":
    unittest.main()
