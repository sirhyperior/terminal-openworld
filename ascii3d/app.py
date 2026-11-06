"""Interactive loop and a deterministic still-frame / performance mode."""

import argparse
from collections import deque
from contextlib import ExitStack
import math
import os
from pathlib import Path
import sys
import time

from .player import Player
from .doors import Door
from .events import GameEvent
from .renderer import Renderer
from .sound import Audio, SoundBank
from .soundscape import Soundscape
from .terminal import Terminal
from .world import build_world
from .map_expansion import INDOOR_SPAWN, OUTDOOR_SPAWN


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def spawn_player(outside: bool = False) -> Player:
    x, y, z = OUTDOOR_SPAWN if outside else INDOOR_SPAWN
    return Player(x=x, y=y, z=z, pitch=-0.06 if outside else 0.0)


class FrameRateCounter:
    """Completed loop frames per elapsed second, using recent frame starts."""

    def __init__(self):
        self._starts: deque[float] = deque()

    def update(self, now: float) -> float:
        self._starts.append(now)
        # Keep the frame spanning the window boundary. Always retain the last
        # complete interval, including a stall longer than the whole window.
        while len(self._starts) > 2 and self._starts[1] <= now - 1.0:
            self._starts.popleft()
        elapsed = now - self._starts[0]
        return (len(self._starts) - 1) / elapsed if elapsed > 0 else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MONOLITH: a real 3D world rendered as white terminal text.")
    parser.add_argument("--snapshot", action="store_true", help="print one plain ASCII frame and exit")
    parser.add_argument("--width", type=positive_int, default=120, help="snapshot / benchmark columns (default: 120)")
    parser.add_argument("--height", type=positive_int, default=40, help="snapshot / benchmark rows (default: 40)")
    parser.add_argument("--fps", type=positive_int, default=40, help="frame rate limit (default: 40)")
    parser.add_argument("--cell-aspect", type=float, default=0.5, help="font cell width / height (default: 0.5)")
    parser.add_argument("--benchmark", type=positive_int, metavar="FRAMES", help="render a turn without terminal output")
    parser.add_argument("--demo", action="store_true", help="automatically walk and turn; controls still work")
    parser.add_argument("--outside", action="store_true", help="start in the meadow facing the castle")
    parser.add_argument("--keyboard-look", action="store_true",
                        help="use arrows to look and Enter to attack instead of mouse capture")
    parser.add_argument("--max-cells", type=positive_int, default=4800,
                        help="live viewport character budget; larger costs more CPU (default: 4800)")
    parser.add_argument("--frames", type=positive_int, help="exit after this many frames")
    parser.add_argument("--mute", action="store_true", help="start with sound muted (F toggles sound)")
    parser.add_argument("--volume", type=float, default=0.55, help="master sound volume, 0 to 1 (default: 0.55)")
    parser.add_argument("--sound-preview", type=Path, metavar="WAV", help="export the original effects as a stereo WAV and exit")
    parser.add_argument("--audio-test", action="store_true", help="play river/effect audio and report playback health")
    args = parser.parse_args(argv)
    keyboard_look = args.keyboard_look or os.name != "nt"
    if not 0.2 <= args.cell_aspect <= 1.5:
        parser.error("--cell-aspect must be between 0.2 and 1.5")
    if args.width > 300 or args.height > 120:
        parser.error("--width / --height must not exceed 300 / 120")
    if args.fps > 240:
        parser.error("--fps must not exceed 240")
    if not 1200 <= args.max_cells <= 11520:
        parser.error("--max-cells must be between 1200 and 11520")
    if not math.isfinite(args.volume) or not 0 <= args.volume <= 1:
        parser.error("--volume must be between 0 and 1")
    if args.sound_preview:
        SoundBank().write_preview(args.sound_preview)
        print(f"Wrote original sound effects to {args.sound_preview}")
        return 0
    if args.audio_test:
        from .audio_check import check_audio
        return check_audio(args.volume)

    world, player = build_world(), spawn_player(args.outside)
    renderer = Renderer(world, args.cell_aspect)
    soundscape = Soundscape(world)
    if args.snapshot:
        print("\n".join(renderer.frame(player, args.width, args.height, keyboard_look=keyboard_look)))
        return 0
    if args.benchmark:
        start = time.perf_counter()
        for frame in range(args.benchmark):
            player.yaw = math.pi / 2 + frame / args.benchmark * math.tau
            renderer.frame(player, args.width, args.height, time_seconds=frame / args.fps)
        elapsed = time.perf_counter() - start
        print(f"{args.benchmark} frames at {args.width}x{args.height}: "
              f"{args.benchmark / elapsed:.1f} FPS ({elapsed / args.benchmark * 1000:.1f} ms/frame)")
        return 0

    try:
        with ExitStack() as session:
            terminal = session.enter_context(Terminal(args.max_cells))
            audio = session.enter_context(Audio(not args.mute, args.volume))
            # Release before audio drains, on frame limits and exceptions too.
            session.callback(terminal.set_mouse_capture, False)
            show_map, help_open, paused = False, False, False
            previous = time.perf_counter()
            accumulator, frame_count, demo_time = 0.0, 0, 0.0
            frame_rate = FrameRateCounter()
            simulation_time = 0.0
            notice, notice_until = ("Audio output unavailable" if not audio.available else ""), 4.0
            jump_pending = attack_pending = False
            step = 1 / 120
            while True:
                start = time.perf_counter()
                fps = frame_rate.update(start)
                elapsed, previous = min(start - previous, 0.1), start
                keys = terminal.keyboard.poll()
                if "escape" in keys.pressed:
                    terminal.set_mouse_capture(False)
                    audio.pause(True)
                    audio.emit(GameEvent("ui_exit"))
                    if audio.enabled:
                        time.sleep(0.25)
                    break
                ui_events = []
                if "m" in keys.pressed or "tab" in keys.pressed:
                    show_map = not show_map
                    ui_events.append(GameEvent("ui_map"))
                if "h" in keys.pressed:
                    help_open = not help_open
                    ui_events.append(GameEvent("ui_help"))
                if "p" in keys.pressed:
                    paused = False if help_open else not paused
                    help_open = False
                    ui_events.append(GameEvent("ui_pause"))
                if "blur" in keys.pressed:
                    paused = True
                    help_open = False
                    ui_events.append(GameEvent("ui_pause"))
                if "f" in keys.pressed:
                    audio.toggle()
                    notice = "Sound on" if audio.enabled else ("Sound muted" if audio.available else "Audio output unavailable")
                    notice_until = simulation_time + 2
                if "r" in keys.pressed:
                    player = spawn_player(args.outside)
                    demo_time = 0.0
                    jump_pending = attack_pending = False
                    ui_events.append(GameEvent("ui_reset"))

                width, height = terminal.size()
                active = not paused and not help_open and width >= 60 and height >= 20
                terminal.set_mouse_capture(active and not keyboard_look and not args.demo)
                # Motion belongs to this rendered input frame, never to each
                # catch-up physics step. UI/reset transitions discard old input.
                input_transition = bool(keys.pressed & {"p", "h", "r"})
                if active and not keyboard_look and not input_transition:
                    player.look(keys.mouse_dx, keys.mouse_dy)
                audio.pause(not active)
                audio.listener = (player.x, player.y, player.yaw)
                audio.ambient = soundscape.at(player.x, player.y, player.yaw)
                for event in ui_events:
                    audio.emit(event)
                if active:
                    if "e" in keys.pressed:
                        for event in world.interact(player):
                            audio.emit(event)
                            if event.name in ("sword_pickup", "staff_pickup"):
                                name = world.combat.held_item.name.capitalize()
                                attack_label = "Enter" if keyboard_look else "left click"
                                notice, notice_until = f"{name} equipped - {attack_label} to attack", simulation_time + 2
                    jump_pending |= "space" in keys.pressed
                    attack_pending |= "attack" in keys.pressed and not input_transition
                    accumulator += elapsed
                    movement = set(keys.down)
                    if not keyboard_look:
                        movement.difference_update(("left", "right", "up", "down"))
                    if args.demo:
                        demo_time += elapsed
                        # Walk through the entrance, then circle in the court.
                        if demo_time < 2.8:
                            movement.add("w")
                        else:
                            movement.update(("w", "right"))
                        if 4 < demo_time % 8 < 4.1:
                            jump_pending = True
                        target = world.interaction_target(player)
                        if target and (not isinstance(target, Door) or not target.target_open):
                            for event in world.interact(player):
                                audio.emit(event)
                    while accumulator >= step:
                        player.update(world, movement, step, jump=jump_pending)
                        for event in player.events:
                            audio.emit(event)
                        for event in world.combat.update(step, world, player):
                            audio.emit(event)
                        if player.hp <= 0:
                            player = spawn_player(args.outside)
                            audio.listener = (player.x, player.y, player.yaw)
                            audio.emit(GameEvent("player_respawn", player.x, player.y))
                            notice = "You fell to the Warden - restored at the entrance"
                            notice_until = simulation_time + 3.0
                            jump_pending = attack_pending = False
                            accumulator = 0.0
                            simulation_time += step
                            break
                        if attack_pending:
                            for event in world.combat.attack(world, player):
                                audio.emit(event)
                                if event.name == "attack_empty":
                                    notice, notice_until = "Collect a weapon with E, then attack", simulation_time + 2
                        for event in world.update_doors(player, step):
                            audio.emit(event)
                            if event.name == "door_blocked":
                                notice, notice_until = "Doorway obstructed", simulation_time + 1.5
                        simulation_time += step
                        jump_pending = attack_pending = False
                        accumulator -= step
                else:
                    accumulator = 0.0
                    jump_pending = attack_pending = False

                mouse_captured = terminal.mouse_captured if not keyboard_look and not args.demo else None
                terminal.draw(renderer.frame(player, width, height, fps, show_map, help_open, paused,
                                              time_seconds=simulation_time,
                                              notice=notice if simulation_time < notice_until else "", sound_on=audio.enabled,
                                              keyboard_look=keyboard_look,
                                              mouse_captured=mouse_captured))
                frame_count += 1
                if args.frames and frame_count >= args.frames:
                    break
                remaining = 1 / args.fps - (time.perf_counter() - start)
                if remaining > 0:
                    time.sleep(remaining)
    except KeyboardInterrupt:
        pass
    except OSError as error:
        print(f"MONOLITH: {error}", file=sys.stderr)
        return 1
    return 0
