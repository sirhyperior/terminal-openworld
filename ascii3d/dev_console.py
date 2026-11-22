"""Command dispatch and a bounded ASCII editor for the developer console."""

from collections import deque
from collections.abc import Callable, Iterable, Mapping
import shlex
from textwrap import TextWrapper


class DevConsole:
    def __init__(self, settings: Mapping[str, Callable[[str], str]],
                 commands: Mapping[str, Callable[[list[str]], str]],
                 describe: Callable[[], str], *, command_help: Mapping[str, str] | None = None):
        self._settings = settings
        self._commands = commands
        self._describe = describe
        self._help = {
            "help": "help [command]  List commands or show one command's usage.",
            "settings": "settings  Show the current live settings.",
            "set": "set <option> <value>  Change a live setting.",
        }
        command_help = command_help or {}
        self._help.update({name: command_help.get(name, name) for name in commands})
        self._history: deque[str] = deque(maxlen=64)
        self._output: deque[str] = deque(maxlen=160)
        self._line = ""
        self._cursor = 0
        self._draft = ""
        self._history_index: int | None = None
        self._scroll = 0
        self._page_rows = 1

    def execute(self, line: str) -> str:
        """Run a console command. Handlers report invalid inputs via ValueError."""
        lexer = shlex.shlex(line, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        lexer.escape = ""  # Keep literal backslashes in Windows paths.
        try:
            tokens = list(lexer)
            if not tokens:
                return ""
            name, *args = tokens
            name = name.lower()
            if name == "help":
                return self._show_help(args)
            if name == "settings":
                if args:
                    raise ValueError("Use 'settings' without arguments.")
                return self._describe()
            if name == "set":
                return self._set(args)
            if name in self._commands:
                return self._commands[name](args)
            raise ValueError(f"Unknown command '{name}'. Try help.")
        except ValueError as exc:
            return f"[Error] {exc}"

    def _show_help(self, args: list[str]) -> str:
        if len(args) > 1:
            raise ValueError("Use 'help' or 'help <command>'.")
        if not args:
            return "\n".join(self._help.values())
        name = args[0].lower()
        if name not in self._help:
            raise ValueError(f"Unknown command '{name}'. Try help.")
        if name == "set":
            return self._help[name] + "\nAvailable options are " + ", ".join(self._settings) + "."
        return self._help[name]

    def _set(self, args: list[str]) -> str:
        if len(args) != 2:
            raise ValueError("Use 'set <option> <value>'. Try 'help set'.")
        name, value = args
        name = name.lower().removeprefix("--")
        if name not in self._settings:
            raise ValueError(f"Unknown option '{name}'. Try help set.")
        return self._settings[name](value)

    def handle(self, keys: Iterable[str]) -> None:
        """Apply ordered terminal text events without reading gameplay keys."""
        for key in keys:
            if key == "enter":
                self._submit()
            elif key == "up":
                self._recall(-1)
            elif key == "down":
                self._recall(1)
            elif key == "page_up":
                self._scroll += max(1, self._page_rows - 1)
            elif key == "page_down":
                self._scroll -= max(1, self._page_rows - 1)
            elif key == "home":
                self._cursor = 0
            elif key == "end":
                self._cursor = len(self._line)
            elif key == "left":
                self._cursor = max(0, self._cursor - 1)
            elif key == "right":
                self._cursor = min(len(self._line), self._cursor + 1)
            elif key == "backspace" and self._cursor:
                self._replace(self._cursor - 1, self._cursor)
            elif key == "delete":
                self._replace(self._cursor, self._cursor + 1)
            elif len(key) == 1 and " " <= key <= "~" and len(self._line) < 512:
                self._replace(self._cursor, self._cursor, key)

    def _replace(self, start: int, stop: int, text: str = "") -> None:
        self._line = self._line[:start] + text + self._line[stop:]
        self._cursor = start + len(text)

    def _submit(self) -> None:
        line = self._line.strip()
        self._line = self._draft = ""
        self._cursor = self._scroll = 0
        self._history_index = None
        if line:
            self._history.append(line)
            self._output.append("> " + line)
            for row in self.execute(line).splitlines():
                self._output.append("".join(char if " " <= char <= "~" else "?" for char in row))

    def _recall(self, direction: int) -> None:
        if not self._history:
            return
        if self._history_index is None:
            if direction > 0:
                return
            self._draft = self._line
            self._history_index = len(self._history)
        index = max(0, self._history_index + direction)
        if index == len(self._history):
            self._history_index = None
            self._line = self._draft
        else:
            self._history_index = index
            self._line = self._history[index]
        self._cursor = len(self._line)

    def frame(self, width: int, height: int) -> list[str]:
        """Compose a full viewport with a fixed prompt and scrolling output."""
        header = ["MONOLITH / DEVELOPER CONSOLE",
                  "help lists commands | Esc closes | PgUp/PgDn scroll"][:height - 1]
        self._page_rows = height - len(header) - 1
        wrapper = TextWrapper(width=width)
        output = [fragment for line in self._output for fragment in wrapper.wrap(line) or [""]]
        self._scroll = min(max(0, self._scroll), max(0, len(output) - self._page_rows))
        stop = len(output) - self._scroll
        history = output[max(0, stop - self._page_rows):stop]

        prompt = "> " if width >= 3 else ""
        visible = width - len(prompt)
        marked = self._line[:self._cursor] + "|" + self._line[self._cursor:]
        start = max(0, self._cursor + 1 - visible)
        lines = header + history + [""] * (self._page_rows - len(history))
        lines.append(prompt + marked[start:start + visible])
        return [line[:width].ljust(width) for line in lines]
