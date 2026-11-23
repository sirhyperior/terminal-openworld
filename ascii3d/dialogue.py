"""Conversation camera motion and an immutable view for terminal presentation."""

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

from .events import GameEvent

if TYPE_CHECKING:
    from .npcs import NPC
    from .player import Player


TURN_SECONDS = 0.34
CHARACTERS_PER_SECOND = 36


@dataclass(frozen=True, slots=True)
class DialogueView:
    speaker: str
    text: str | None
    last: bool
    visible_characters: int | None = None


class Conversation:
    """Take control of facing until the player dismisses the last line."""

    def __init__(self, npc: "NPC", player: "Player"):
        self.npc = npc
        self.elapsed = 0.0
        self.line = 0
        self._reveal_progress = 1.0
        dx, dy = npc.x - player.x, npc.y - player.y
        self.player_start = player.yaw
        self.npc_start = npc.yaw
        self.pitch_start = player.pitch
        yaw = math.atan2(dy, dx) if dx or dy else player.yaw
        self.player_turn = math.remainder(yaw - player.yaw, math.tau)
        self.npc_turn = math.remainder(yaw + math.pi - npc.yaw, math.tau)
        pitch = math.atan2(npc.eye_z - player.eye_z, math.hypot(dx, dy))
        self.pitch_turn = max(-0.65, min(0.65, pitch)) - player.pitch

    @property
    def finished(self) -> bool:
        return self.line == len(self.npc.dialogue)

    @property
    def view(self) -> DialogueView:
        text = self.npc.dialogue[self.line] if self.elapsed >= TURN_SECONDS and not self.finished else None
        visible = int(self._reveal_progress) if text is not None and self._reveal_progress < len(text) else None
        return DialogueView(self.npc.name, text, self.line == len(self.npc.dialogue) - 1, visible)

    def _reveal(self, dt: float, *, line_start: bool = False) -> tuple[GameEvent, ...]:
        text = self.npc.dialogue[self.line]
        previous = 0 if line_start else int(self._reveal_progress)
        self._reveal_progress = min(len(text), self._reveal_progress + dt * CHARACTERS_PER_SECOND)
        visible = int(self._reveal_progress)
        position = self.npc.x, self.npc.y
        start = (GameEvent("dialogue_line", *position),) if line_start else ()
        # Keep letters apart even when a slow frame reveals several together.
        return start + tuple(GameEvent("dialogue_letter", *position, delay=offset / CHARACTERS_PER_SECOND)
                             for offset, character in enumerate(text[previous:visible])
                             if character.isalpha())

    def update(self, player: "Player", dt: float, *, advance: bool = False) -> tuple[GameEvent, ...]:
        if self.finished:
            return ()
        if self.elapsed < TURN_SECONDS:
            turn_remaining = TURN_SECONDS - self.elapsed
            self.elapsed = min(TURN_SECONDS, self.elapsed + dt)
            t = self.elapsed / TURN_SECONDS
            ease = t * t * (3 - 2 * t)
            player.yaw = (self.player_start + self.player_turn * ease) % math.tau
            player.pitch = self.pitch_start + self.pitch_turn * ease
            self.npc.yaw = (self.npc_start + self.npc_turn * ease) % math.tau
            if self.elapsed == TURN_SECONDS:
                return self._reveal(max(0.0, dt - turn_remaining), line_start=True)
            return ()

        if not advance:
            return self._reveal(dt)
        length = len(self.npc.dialogue[self.line])
        if self._reveal_progress < length:
            self._reveal_progress = length
            return (GameEvent("dialogue_reveal", self.npc.x, self.npc.y),)

        self.line += 1
        self._reveal_progress = 1.0
        if self.finished:
            return (GameEvent("dialogue_end", self.npc.x, self.npc.y),)
        return self._reveal(0.0, line_start=True)
