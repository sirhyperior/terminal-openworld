"""Conversation camera motion and an immutable view for terminal presentation."""

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

from .events import GameEvent

if TYPE_CHECKING:
    from .npcs import NPC
    from .player import Player


TURN_SECONDS = 0.34


@dataclass(frozen=True, slots=True)
class DialogueView:
    speaker: str
    text: str | None
    last: bool


class Conversation:
    """Take control of facing until the player dismisses the last line."""

    def __init__(self, npc: "NPC", player: "Player"):
        self.npc = npc
        self.elapsed = 0.0
        self.line = 0
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
        text = self.npc.dialogue[self.line] if self.elapsed >= TURN_SECONDS else None
        return DialogueView(self.npc.name, text, self.line == len(self.npc.dialogue) - 1)

    def update(self, player: "Player", dt: float, *, advance: bool = False) -> GameEvent | None:
        if self.elapsed < TURN_SECONDS:
            self.elapsed = min(TURN_SECONDS, self.elapsed + dt)
            t = self.elapsed / TURN_SECONDS
            ease = t * t * (3 - 2 * t)
            player.yaw = (self.player_start + self.player_turn * ease) % math.tau
            player.pitch = self.pitch_start + self.pitch_turn * ease
            self.npc.yaw = (self.npc_start + self.npc_turn * ease) % math.tau
            if self.elapsed == TURN_SECONDS:
                return GameEvent("dialogue_line", self.npc.x, self.npc.y)
        elif advance:
            self.line += 1
            return GameEvent("dialogue_end" if self.finished else "dialogue_line",
                             self.npc.x, self.npc.y)
        return None
