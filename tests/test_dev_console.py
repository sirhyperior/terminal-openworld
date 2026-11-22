import unittest

from ascii3d.dev_console import DevConsole


class DevConsoleTests(unittest.TestCase):
    def setUp(self):
        self.value = "auto"
        self.console = DevConsole(
            {"renderer": self.set_renderer, "frame-timing": lambda value: value},
            {"teleport": lambda args: ",".join(args)},
            lambda: f"renderer {self.value}",
            command_help={"teleport": "teleport <x> <y> [z]  Move to coordinates."},
        )

    def set_renderer(self, value):
        if value not in ("auto", "cpu", "native", "gpu"):
            raise ValueError("Choose auto, cpu, native or gpu.")
        self.value = value
        return f"renderer {value}"

    def test_help_settings_and_commands_share_the_live_configuration(self):
        self.assertIn("teleport <x> <y> [z]", self.console.execute("help"))
        self.assertIn("frame-timing", self.console.execute("help set"))
        self.assertEqual(self.console.execute("settings"), "renderer auto")
        self.assertEqual(self.console.execute("SET --renderer cpu"), "renderer cpu")
        self.assertEqual(self.console.execute("settings"), "renderer cpu")
        self.assertEqual(self.console.execute("Teleport -1 2 3"), "-1,2,3")

    def test_quoted_and_unquoted_windows_paths_preserve_backslashes(self):
        unquoted = r"C:\Monolith\timing.json"
        quoted = r"C:\Monolith Project\timing.json"
        self.assertEqual(self.console.execute(f"set frame-timing {unquoted}"), unquoted)
        self.assertEqual(self.console.execute(f'set frame-timing "{quoted}"'), quoted)

    def test_invalid_input_reports_errors_without_changing_settings(self):
        for line in ('set renderer "cpu', "set renderer", "set renderer bogus",
                     "set unknown on", "help alien", "settings extra", "alien"):
            with self.subTest(line=line):
                self.assertIn("Error", self.console.execute(line))
        self.assertEqual(self.value, "auto")
        self.assertEqual(self.console.execute(" \t "), "")

    def test_editor_inserts_deletes_and_recalls_history_in_event_order(self):
        self.console.handle((*"hsxlp", "home", "right", "delete", "delete", "e",
                             "end", "backspace", "p", "enter"))
        lines = self.console.frame(60, 12)
        self.assertEqual(lines[2].rstrip(), "> help")
        self.assertIn("settings  Show the current live settings.", "\n".join(lines))
        self.assertEqual(lines[-1].rstrip(), "> |")

        self.console.handle((*"set", "left", "up"))
        self.assertEqual(self.console.frame(60, 12)[-1].rstrip(), "> help|")
        self.console.handle(("down", "left"))
        self.assertEqual(self.console.frame(60, 12)[-1].rstrip(), "> se|t")

    def test_output_scroll_and_small_frames_preserve_printable_ascii(self):
        console = DevConsole({}, {"lines": lambda _: "\n".join(
            [f"line {index}" for index in range(9)] + ["line 9 \x1b[31m\u00e9"])}, lambda: "")
        console.handle((*"lines", "enter"))
        lines = console.frame(20, 6)
        self.assertIn("line 9 ?[31m?", lines[4])
        self.assertTrue(all(len(line) == 20 and line.isascii() and line.isprintable() for line in lines))
        console.handle(("page_up",))
        self.assertNotIn("line 9", "\n".join(console.frame(20, 6)))
        console.handle(("page_down",))
        self.assertEqual(console.frame(20, 6), lines)

        console.handle("long input")
        self.assertEqual(console.frame(7, 1), ["> nput|"])
        self.assertEqual(console.frame(1, 1), ["|"])
