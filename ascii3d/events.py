"""Semantic feedback events shared by gameplay and the sound system."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GameEvent:
    name: str
    x: float | None = None
    y: float | None = None
    strength: float = 1.0
    surface: str | None = None
