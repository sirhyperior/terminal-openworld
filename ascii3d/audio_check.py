"""Audible river/effect check with output-queue diagnostics; no microphone access."""

import time

from .events import GameEvent
from .sound import Audio


def check_audio(volume=0.55, seconds=18.0):
    audio = Audio(volume=volume)
    if not audio.available:
        print(f"Audio output unavailable: {audio.error}")
        audio.close()
        return 1
    print("Playing meadow wind, river, surface Foley, doors, weapons and creature/player effects...")
    start = time.perf_counter()
    next_effect, effect = 2.0, 0
    effects = ("step_stone", "step_grass", "step_wood", "step_water", "step_gravel", "step_metal",
               "land_gravel", "land_metal", "door_open", "door_close", "door_blocked", "sword_pickup",
               "sword_swing", "sword_hit", "sword_miss", "attack_empty", "dummy_down", "dummy_reset",
               "staff_pickup", "item_drop", "fireball_cast", "fireball_hit", "fireball_impact", "fireball_fizzle",
               "enemy_alert", "enemy_step", "enemy_attack", "enemy_miss", "enemy_hurt", "enemy_down",
               "enemy_respawn", "player_hurt", "player_down", "player_respawn")
    try:
        while time.perf_counter() - start < seconds:
            elapsed = time.perf_counter() - start
            audio.ambient = ((0.18, 0.0, 0.0) if elapsed < 2.0
                             else (0.025, 0.5, 0.0)) if elapsed < seconds - 0.4 else (0.0, 0.0, 0.0)
            if elapsed >= next_effect and effect < len(effects):
                audio.emit(GameEvent(effects[effect]))
                effect += 1
                next_effect += 0.45
            time.sleep(0.01)
    finally:
        audio.close()
    print(f"Playback: {audio.blocks_rendered} buffers, {audio.underruns} empty-queue events, "
          f"{audio.max_write_gap_ms:.1f} ms maximum refill interval, {audio.recoveries} recoveries.")
    if audio.error:
        print(f"Audio error: {audio.error}")
    return 1 if audio.error or audio.underruns else 0
