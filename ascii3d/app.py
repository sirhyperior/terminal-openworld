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
from .loading import LoadingProgress
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


REGION_NAMES = ("ashgate", "gravewood", "thornwatch", "abbey", "reliquary", "citadel",
                "ridge", "keep", "observatory")


def spawn_region(region: str) -> Player:
    from .terrain import LANDMARKS

    if region == "ashgate":
        return spawn_player()
    if region == "gravewood":
        return Player(x=71.5, y=240.0, z=1.0, yaw=math.pi / 2, pitch=-0.06)
    index = {"thornwatch": 0, "ridge": 0, "abbey": 1, "keep": 1,
             "reliquary": 2, "observatory": 2, "citadel": 3}[region]
    landmark = LANDMARKS[index]
    x0, y0, x1, _ = landmark.bounds
    x, y = landmark.to_world((x0 + x1) / 2 + .5, y0 - 2.5)
    return Player(x=x, y=y, z=float(landmark.base),
                  yaw=math.pi / 2 + landmark.angle, pitch=-0.06)


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
    parser = argparse.ArgumentParser(description="MONOLITH: a real 3D world rendered as ASCII on black.")
    parser.add_argument("--snapshot", action="store_true", help="print one plain ASCII frame and exit")
    parser.add_argument("--width", type=positive_int, default=120, help="snapshot / benchmark columns (default: 120)")
    parser.add_argument("--height", type=positive_int, default=40, help="snapshot / benchmark rows (default: 40)")
    parser.add_argument("--fps", type=positive_int, default=40, help="frame rate limit (default: 40)")
    parser.add_argument("--cell-aspect", type=float, default=0.5, help="font cell width / height (default: 0.5)")
    parser.add_argument("--benchmark", type=positive_int, metavar="FRAMES", help="render a turn without terminal output")
    parser.add_argument("--renderer", choices=('auto', 'cpu', 'native', 'gpu'), default='auto',
                        help='geometry renderer (auto prefers hardware GPU, then compiled native solids)')
    parser.add_argument("--color-mode", choices=('mono', 'gray', 'color'), default='color',
                        help='foreground presentation: color, grayscale or uniform white (default: color)')
    parser.add_argument("--demo", action="store_true", help="automatically walk and turn; controls still work")
    parser.add_argument("--outside", action="store_true", help="start in the meadow facing the castle")
    parser.add_argument("--region", choices=REGION_NAMES,
                        help="start at a highland landmark; R returns to this entrance")
    parser.add_argument("--keyboard-look", action="store_true",
                        help="use arrows to look and Enter to attack instead of mouse capture")
    parser.add_argument("--max-cells", type=positive_int,
                        help="optional live viewport character budget, at least 1200 (default: fill terminal)")
    parser.add_argument("--frames", type=positive_int, help="exit after this many frames")
    parser.add_argument("--frame-timing", type=Path, metavar="PATH",
                        help="save a gameplay timing report on exit")
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
    if args.max_cells is not None and args.max_cells < 1200:
        parser.error("--max-cells must be at least 1200")
    if not math.isfinite(args.volume) or not 0 <= args.volume <= 1:
        parser.error("--volume must be between 0 and 1")
    frame_timing = None
    if args.frame_timing is not None:
        if args.snapshot or args.benchmark or args.sound_preview or args.audio_test:
            parser.error("--frame-timing is available during gameplay")
        if args.frame_timing.exists() or args.frame_timing.is_symlink():
            parser.error("--frame-timing requires an unused path")
        from .frame_timing import FrameTiming, milliseconds

        frame_timing = FrameTiming(args.frame_timing, {
            "fps_cap": args.fps, "renderer_requested": args.renderer, "color_mode": args.color_mode,
            "max_cells": args.max_cells,
            "keyboard_look": keyboard_look, "start_muted": args.mute,
        })
    if args.sound_preview:
        SoundBank().write_preview(args.sound_preview)
        print(f"Wrote original sound effects to {args.sound_preview}")
        return 0
    if args.audio_test:
        from .audio_check import check_audio
        return check_audio(args.volume)

    loading = LoadingProgress(sys.stdout, not args.snapshot and not args.benchmark and sys.stdout.isatty())
    entrance = (lambda: spawn_region(args.region)) if args.region else (lambda: spawn_player(args.outside))
    renderer = None
    try:
        loading.start()
        world, player = build_world(), entrance()
        loading.advance()
        renderer = Renderer(world, args.cell_aspect, backend=args.renderer)
        loading.advance()
        if args.renderer in ('gpu', 'native') and renderer.backend_name != args.renderer:
            label = 'GPU' if args.renderer == 'gpu' else 'Native solid library'
            print(f'MONOLITH: {label} unavailable. Using Python CPU renderer ({renderer.backend_error})', file=sys.stderr)
        soundscape = Soundscape(world)
    except BaseException:
        loading.close()
        if renderer is not None:
            renderer.close()
        raise
    if args.snapshot:
        try:
            print("\n".join(renderer.frame(player, args.width, args.height, keyboard_look=keyboard_look)))
            return 0
        finally:
            renderer.close()
            loading.close()
    if args.benchmark:
        try:
            start = time.perf_counter()
            for frame in range(args.benchmark):
                player.yaw = math.pi / 2 + frame / args.benchmark * math.tau
                renderer.frame(player, args.width, args.height, time_seconds=frame / args.fps)
            elapsed = time.perf_counter() - start
            print(f"{args.benchmark} frames at {args.width}x{args.height}: "
                  f"{args.benchmark / elapsed:.1f} FPS ({elapsed / args.benchmark * 1000:.1f} ms/frame)")
            return 0
        finally:
            renderer.close()
            loading.close()

    status = 0
    try:
        # Static terrain preparation belongs to loading, before capture/audio
        # and the first active physics frame. Headless callers remain lazy-safe.
        renderer.prepare_world(player)
        loading.advance()
        soundscape.at(player.x, player.y, player.yaw, player.z)
        loading.advance()
        with ExitStack() as session:
            with loading.suspend():
                loading.clear_line()
                terminal = session.enter_context(Terminal(args.max_cells))
                # Audio startup can fail before the final phase. Join the
                # loading writer before Terminal restores the main screen.
                session.callback(loading.close)
                loading.use_alternate_screen()
            if frame_timing is not None:
                terminal.measure_output = True
            loading.advance()
            audio = session.enter_context(Audio(not args.mute, args.volume))
            loading.advance()
            # Release before audio drains, on frame limits and exceptions too.
            session.callback(terminal.set_mouse_capture, False)
            show_map, help_open, paused = False, False, False
            previous = time.perf_counter()
            accumulator, frame_count, demo_time = 0.0, 0, 0.0
            frame_rate = FrameRateCounter()
            simulation_time = 0.0
            notice, notice_until = ("Audio output unavailable" if not audio.available else ""), 4.0
            jump_pending = attack_pending = False
            last_mouse_error = ""
            step = 1 / 120
            while True:
                start = time.perf_counter()
                if frame_timing is not None:
                    frame_timing.begin(start)
                    audio_toggle_seconds = 0.0
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
                    if frame_timing is not None:
                        toggle_start = time.perf_counter()
                    audio.toggle()
                    if frame_timing is not None:
                        audio_toggle_seconds = time.perf_counter() - toggle_start
                    notice = "Sound on" if audio.enabled else ("Sound muted" if audio.available else "Audio output unavailable")
                    notice_until = simulation_time + 2
                if "r" in keys.pressed:
                    player = entrance()
                    demo_time = 0.0
                    jump_pending = attack_pending = False
                    ui_events.append(GameEvent("ui_reset"))

                width, height = terminal.size()
                playable = width >= 60 and height >= 20
                active = not paused and not help_open and playable
                terminal.set_mouse_capture(active and not keyboard_look and not args.demo)
                mouse_error = getattr(terminal, "mouse_error", "")
                if mouse_error and mouse_error != last_mouse_error:
                    notice = "Mouse capture unavailable - restart with --keyboard-look"
                    notice_until = simulation_time + 4
                    last_mouse_error = mouse_error
                # Motion belongs to this rendered input frame, never to each
                # catch-up physics step. UI/reset transitions discard old input.
                input_transition = bool(keys.pressed & {"p", "h", "r"})
                if active and not keyboard_look and not input_transition:
                    player.look(keys.mouse_dx, keys.mouse_dy)
                if frame_timing is not None:
                    input_end = time.perf_counter()
                audio.pause(not active)
                audio.listener = (player.x, player.y, player.yaw)
                audio.ambient = soundscape.at(player.x, player.y, player.yaw, player.z)
                for event in ui_events:
                    audio.emit(event)
                if frame_timing is not None:
                    audio_end = time.perf_counter()
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
                            player = entrance()
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

                if frame_timing is not None:
                    simulation_end = time.perf_counter()
                mouse_captured = terminal.mouse_captured if not keyboard_look and not args.demo else None
                frame = renderer.styled_frame(player, width, height, fps, show_map, help_open, paused,
                                              time_seconds=simulation_time,
                                              notice=notice if simulation_time < notice_until else "", sound_on=audio.enabled,
                                              keyboard_look=keyboard_look,
                                              mouse_captured=mouse_captured, color_mode=args.color_mode)
                if frame_timing is not None:
                    render_end = time.perf_counter()
                terminal.draw(frame)
                frame_count += 1
                last_frame = args.frames is not None and frame_count >= args.frames
                if last_frame and frame_timing is None:
                    break
                work_end = time.perf_counter()
                work_seconds = work_end - start
                remaining = 0.0 if last_frame else 1 / args.fps - work_seconds
                timing_sample = None
                if frame_timing is not None:
                    encode, write, output_bytes = getattr(terminal, "output_timing", (None, None, None))
                    gpu = getattr(renderer, "ray_backend", None)
                    timing_sample = frame_timing.record(
                        frame=frame_count, viewport=(width, height), terminal=terminal._terminal_size,
                        scene_samples=(width, height - 5) if playable else None,
                        backend=renderer.backend_name, active=active, sound_on=audio.enabled,
                        mouse_captured=mouse_captured,
                        gpu_stats=dict(gpu.last_stats) if gpu is not None else None,
                        input_ms=milliseconds(input_end - start - audio_toggle_seconds),
                        audio_ms=milliseconds(audio_end - input_end + audio_toggle_seconds),
                        simulation_ms=milliseconds(simulation_end - audio_end),
                        render_ms=milliseconds(render_end - simulation_end),
                        draw_ms=milliseconds(work_end - render_end), work_ms=milliseconds(work_seconds),
                        encode_ms=milliseconds(encode) if encode is not None else None,
                        write_flush_ms=milliseconds(write) if write is not None else None,
                        output_bytes=output_bytes,
                        cap_requested_ms=milliseconds(max(0.0, remaining)), cap_actual_ms=0.0,
                    )
                if remaining > 0:
                    sleep_start = time.perf_counter() if timing_sample is not None else None
                    try:
                        time.sleep(remaining)
                    finally:
                        if sleep_start is not None:
                            timing_sample["cap_actual_ms"] = milliseconds(time.perf_counter() - sleep_start)
                if last_frame:
                    break
    except KeyboardInterrupt:
        pass
    except OSError as error:
        loading.close()
        print(f"MONOLITH: {error}", file=sys.stderr)
        status = 1
    finally:
        renderer.close()
        loading.close()
    if frame_timing is not None:
        try:
            frame_timing.write(status)
        except OSError as error:
            print(f"MONOLITH: Could not save frame timing. {error}", file=sys.stderr)
            return 1
        print(f"Frame timing saved to {args.frame_timing}")
    return status
