"""Full-screen sizing and final-cell output without a physical terminal."""

import io
import os
import unittest
from unittest.mock import Mock, patch

from ascii3d.presentation import GRAY_CODES, WHITE_ON_BLACK, StyledFrame
from ascii3d.terminal import PosixKeyboard, Terminal, fit_viewport


class ViewportSizingTests(unittest.TestCase):
    def test_default_uses_every_cell_including_large_and_small_windows(self):
        for columns, rows in ((1, 1), (40, 12), (60, 20), (120, 40),
                              (240, 80), (360, 140)):
            with self.subTest(columns=columns, rows=rows):
                self.assertEqual(fit_viewport(columns, rows), (columns, rows))

    def test_explicit_budget_stays_within_screen_and_keeps_playable_minimum(self):
        for columns, rows in ((60, 20), (120, 40), (240, 80), (6000, 20),
                              (60, 6000), (40, 1200), (1200, 12)):
            for budget in (1200, 4800, 20000):
                with self.subTest(columns=columns, rows=rows, budget=budget):
                    width, height = fit_viewport(columns, rows, budget)
                    self.assertLessEqual(width * height, budget)
                    self.assertLessEqual(width, columns)
                    self.assertLessEqual(height, rows)
                    self.assertGreaterEqual(width, min(columns, 60))
                    self.assertGreaterEqual(height, min(rows, 20))

    def test_output_device_size_takes_precedence_over_environment(self):
        terminal = Terminal()
        with patch("ascii3d.terminal.sys.stdout") as output, \
                patch("ascii3d.terminal.os.get_terminal_size", return_value=os.terminal_size((240, 80))) as native, \
                patch("ascii3d.terminal.shutil.get_terminal_size") as fallback:
            output.fileno.return_value = 7
            self.assertEqual(terminal.size(), (240, 80))
        native.assert_called_once_with(7)
        fallback.assert_not_called()
        self.assertEqual(terminal.origin, (1, 1))

    def test_missing_or_empty_device_dimensions_use_portable_fallback(self):
        for result in (OSError("not a terminal"), os.terminal_size((0, 0))):
            with self.subTest(result=result), \
                    patch("ascii3d.terminal.os.get_terminal_size", side_effect=(
                        result if isinstance(result, OSError) else lambda fd: result)), \
                    patch("ascii3d.terminal.shutil.get_terminal_size", return_value=os.terminal_size((100, 32))) as fallback:
                self.assertEqual(Terminal().size(), (100, 32))
                fallback.assert_called_once_with((100, 32))


class TerminalOutputTests(unittest.TestCase):
    def test_unchanged_frames_emit_nothing_and_removed_glyphs_are_erased(self):
        terminal = Terminal()
        terminal.origin = (4, 6)
        with patch('ascii3d.terminal.sys.stdout', new_callable=io.StringIO) as output:
            rows = ['.' * 64, '.' * 64, '.' * 64]
            terminal.draw(rows)
            output.seek(0)
            output.truncate()
            terminal.draw(rows)
            self.assertEqual(output.getvalue(), '')
            rows[1] = '.' * 32 + ' ' + '.' * 31
            terminal.draw(rows)
            self.assertEqual(output.getvalue(), '\x1b[5;38H ' + '.' * 15)

    def test_color_only_changes_address_independent_spans(self):
        terminal = Terminal()
        styles = bytearray([2] * 96)
        frame = StyledFrame(96, 1, ['.' * 96], [styles])
        with patch('ascii3d.terminal.sys.stdout', new_callable=io.StringIO) as output:
            terminal.draw(frame)
            output.seek(0)
            output.truncate()
            styles[0] = styles[-1] = 9
            terminal.draw(frame)
            first = '\x1b[1;1H\x1b[40m' + GRAY_CODES[9] + '.' + GRAY_CODES[2] + '.' * 15
            last = '\x1b[1;81H\x1b[40m' + GRAY_CODES[2] + '.' * 15 + GRAY_CODES[9] + '.'
            self.assertEqual(output.getvalue(), first + WHITE_ON_BLACK + last + WHITE_ON_BLACK)

    def test_failed_flush_invalidates_the_delta_baseline(self):
        terminal = Terminal()
        first = ['.' * 32, '.' * 32]
        second = ['.' * 32, 'x' + '.' * 31]
        with patch('ascii3d.terminal.sys.stdout', new_callable=io.StringIO) as output:
            terminal.draw(first)
            with patch.object(output, 'flush', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    terminal.draw(second)
            output.seek(0)
            output.truncate()
            terminal.draw(second)
            self.assertEqual(output.getvalue(), '\x1b[1;1H' + '\r\n'.join(second))

    def test_output_timing_counts_only_the_payload_written(self):
        terminal = Terminal()
        terminal.measure_output = True
        with patch('ascii3d.terminal.sys.stdout', new_callable=io.StringIO) as output, \
                patch('ascii3d.terminal.time.perf_counter', side_effect=(1, 1.001, 1.003, 2, 2.001)):
            terminal.draw(['ab'])
            encode, write, size = terminal.output_timing
            self.assertAlmostEqual(encode, 0.001)
            self.assertAlmostEqual(write, 0.002)
            self.assertEqual(size, len(output.getvalue()))
            terminal.draw(['ab'])
            self.assertEqual(terminal.output_timing[1:], (0.0, 0))

    @unittest.skipUnless(os.name == 'posix', 'requires a POSIX pseudoterminal')
    def test_nonblocking_keyboard_leaves_shared_output_descriptor_blocking(self):
        import pty
        import termios

        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        original = termios.tcgetattr(slave)
        with patch('ascii3d.terminal.sys.stdin') as stdin:
            stdin.fileno.return_value = slave
            keyboard = PosixKeyboard()
            try:
                self.assertTrue(os.get_blocking(slave))
                self.assertFalse(os.get_blocking(keyboard.fd))
                self.assertFalse(keyboard.poll().pressed)
            finally:
                keyboard.close()
        self.assertEqual(termios.tcgetattr(slave), original)

    def test_full_frame_reaches_final_cell_without_a_trailing_linefeed(self):
        terminal = Terminal()
        with patch("ascii3d.terminal.os.get_terminal_size", return_value=os.terminal_size((3, 2))), \
                patch("ascii3d.terminal.sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(terminal.size(), (3, 2))
            terminal.draw(["abc", "deZ"])
            self.assertEqual(output.getvalue(), "\x1b[2J\x1b[1;1Habc\r\ndeZ")
            output.seek(0)
            output.truncate()
            terminal.draw(["ABC", "DEZ"])
            self.assertEqual(output.getvalue(), "\x1b[1;1HABC\r\nDEZ")

    def test_resize_clears_even_when_budget_and_origin_round_to_same_values(self):
        terminal = Terminal(1200)
        with patch("ascii3d.terminal.os.get_terminal_size", side_effect=(
                os.terminal_size((60, 20)), os.terminal_size((61, 21)))), \
                patch("ascii3d.terminal.sys.stdout", new_callable=io.StringIO) as output:
            first_size = terminal.size()
            first_origin = terminal.origin
            terminal.draw(["x" * first_size[0]] * first_size[1])
            output.seek(0)
            output.truncate()
            self.assertEqual(terminal.size(), first_size)
            self.assertEqual(terminal.origin, first_origin)
            terminal.draw(["y" * first_size[0]] * first_size[1])
            self.assertTrue(output.getvalue().startswith("\x1b[2J"))

    def test_budget_viewport_is_centered_and_each_line_uses_its_left_edge(self):
        terminal = Terminal(1200)
        with patch("ascii3d.terminal.os.get_terminal_size", return_value=os.terminal_size((100, 40))), \
                patch("ascii3d.terminal.sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(terminal.size(), (60, 20))
            self.assertEqual(terminal.origin, (11, 21))
            terminal.draw(["x" * 60] * 20)
            self.assertTrue(output.getvalue().startswith("\x1b[2J\x1b[11;21H"))
            self.assertEqual(output.getvalue().count("\r\n\x1b[21G"), 19)

    def test_session_disables_autowrap_and_restores_terminal_on_exception(self):
        keyboard = Mock()
        output = Mock()
        output.isatty.return_value = True
        with patch("ascii3d.terminal.sys.stdin.isatty", return_value=True), \
                patch("ascii3d.terminal.sys.stdout", output), \
                patch("ascii3d.terminal.WindowsKeyboard", return_value=keyboard), \
                patch("ascii3d.terminal.PosixKeyboard", return_value=keyboard):
            with self.assertRaisesRegex(RuntimeError, "frame failed"):
                with Terminal():
                    raise RuntimeError("frame failed")
        written = "".join(call.args[0] for call in output.write.call_args_list)
        self.assertIn("\x1b[?7l", written)
        self.assertTrue(written.endswith("\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l"))
        keyboard.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
