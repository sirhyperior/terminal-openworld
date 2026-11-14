"""Temporary actual-app native-console smoke. Run only in an idle timing slot."""
import ctypes
from ctypes import wintypes as wt
import hashlib
import json
import math
import msvcrt
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / 'ascii3d').rglob('*'))
            if p.is_file() and p.suffix in ('.py', '.wgsl') and '__pycache__' not in p.parts}


def summary(samples):
    return {'sample_count': len(samples), 'mean_ms': statistics.mean(samples) if samples else None,
            'p95_ms': sorted(samples)[math.ceil(len(samples) * .95) - 1] if samples else None,
            'max_ms': max(samples) if samples else None, 'samples_ms': samples}


class Coord(ctypes.Structure):
    _fields_ = [('X', wt.SHORT), ('Y', wt.SHORT)]


class Rect(ctypes.Structure):
    _fields_ = [('Left', wt.SHORT), ('Top', wt.SHORT), ('Right', wt.SHORT), ('Bottom', wt.SHORT)]


class BufferInfo(ctypes.Structure):
    _fields_ = [('dwSize', Coord), ('dwCursorPosition', Coord), ('wAttributes', wt.WORD),
                ('srWindow', Rect), ('dwMaximumWindowSize', Coord)]


class CursorInfo(ctypes.Structure):
    _fields_ = [('dwSize', wt.DWORD), ('bVisible', wt.BOOL)]


class FontInfo(ctypes.Structure):
    _fields_ = [('cbSize', wt.ULONG), ('nFont', wt.DWORD), ('dwFontSize', Coord),
                ('FontFamily', wt.UINT), ('FontWeight', wt.UINT), ('FaceName', wt.WCHAR * 32)]


class Console:
    def __init__(self):
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.k.GetConsoleWindow.restype = wt.HWND
        self.k.SetStdHandle.argtypes = [wt.DWORD, wt.HANDLE]
        self.k.GetConsoleMode.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
        self.k.GetConsoleScreenBufferInfo.argtypes = [wt.HANDLE, ctypes.POINTER(BufferInfo)]
        self.k.GetConsoleCursorInfo.argtypes = [wt.HANDLE, ctypes.POINTER(CursorInfo)]
        self.k.GetCurrentConsoleFontEx.argtypes = [wt.HANDLE, wt.BOOL, ctypes.POINTER(FontInfo)]
        self.k.SetCurrentConsoleFontEx.argtypes = [wt.HANDLE, wt.BOOL, ctypes.POINTER(FontInfo)]
        self.k.SetConsoleScreenBufferSize.argtypes = [wt.HANDLE, Coord]
        self.k.SetConsoleWindowInfo.argtypes = [wt.HANDLE, wt.BOOL, ctypes.POINTER(Rect)]
        self.k.ReadConsoleOutputCharacterW.argtypes = [wt.HANDLE, wt.LPWSTR, wt.DWORD,
                                                      Coord, ctypes.POINTER(wt.DWORD)]
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
        user.ShowWindow(self.k.GetConsoleWindow(), 0)
        sys.stdin = open('CONIN$', 'r', encoding='utf-8')
        sys.stdout = open('CONOUT$', 'w', encoding='utf-8', buffering=1)
        sys.stderr = sys.stdout
        self.input = msvcrt.get_osfhandle(sys.stdin.fileno())
        self.output = msvcrt.get_osfhandle(sys.stdout.fileno())
        for code, stream in ((-10, sys.stdin), (-11, sys.stdout), (-12, sys.stderr)):
            self.check(self.k.SetStdHandle(code, msvcrt.get_osfhandle(stream.fileno())))

    @staticmethod
    def check(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())

    def configure(self, width, height):
        font = FontInfo(cbSize=ctypes.sizeof(FontInfo), dwFontSize=Coord(0, 16),
                        FontFamily=54, FontWeight=400, FaceName='Consolas')
        accepted = bool(self.k.SetCurrentConsoleFontEx(self.output, False, ctypes.byref(font)))
        font_error = ctypes.get_last_error() if not accepted else 0
        self.check(self.k.SetConsoleWindowInfo(self.output, True, ctypes.byref(Rect(0, 0, 0, 0))))
        self.check(self.k.SetConsoleScreenBufferSize(self.output, Coord(width, height)))
        self.check(self.k.SetConsoleWindowInfo(self.output, True,
                                             ctypes.byref(Rect(0, 0, width - 1, height - 1))))
        return {'face': 'Consolas', 'height': 16, 'api_accepted': accepted,
                'error': font_error}

    def state(self):
        input_mode, output_mode = wt.DWORD(), wt.DWORD()
        info, cursor = BufferInfo(), CursorInfo()
        font = FontInfo(cbSize=ctypes.sizeof(FontInfo))
        for result in (self.k.GetConsoleMode(self.input, ctypes.byref(input_mode)),
                       self.k.GetConsoleMode(self.output, ctypes.byref(output_mode)),
                       self.k.GetConsoleScreenBufferInfo(self.output, ctypes.byref(info)),
                       self.k.GetConsoleCursorInfo(self.output, ctypes.byref(cursor)),
                       self.k.GetCurrentConsoleFontEx(self.output, False, ctypes.byref(font))):
            self.check(result)
        text = ctypes.create_unicode_buffer(info.dwSize.X * info.dwSize.Y + 1)
        count = wt.DWORD()
        self.check(self.k.ReadConsoleOutputCharacterW(self.output, text, len(text) - 1,
                                                     Coord(0, 0), ctypes.byref(count)))
        return {'input_mode': input_mode.value, 'output_mode': output_mode.value,
                'width': info.srWindow.Right - info.srWindow.Left + 1,
                'height': info.srWindow.Bottom - info.srWindow.Top + 1,
                'buffer_width': info.dwSize.X, 'buffer_height': info.dwSize.Y,
                'attributes': info.wAttributes, 'cursor_visible': bool(cursor.bVisible),
                'cursor': [info.dwCursorPosition.X, info.dwCursorPosition.Y],
                'screen_hash': hashlib.sha256(text[:count.value].encode('utf-8')).hexdigest(),
                'font': {'face': font.FaceName, 'width': font.dwFontSize.X, 'height': font.dwFontSize.Y}}


class CountingOutput:
    def __init__(self, stream):
        self.stream = stream
        self.bytes = self.writes = self.flushes = 0
        self.write_seconds = self.flush_seconds = 0.
        self.tail = ''
        self.colored = self.black_background = False

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def write(self, value):
        started = time.perf_counter()
        result = self.stream.write(value)
        self.write_seconds += time.perf_counter() - started
        self.writes += 1
        self.bytes += len(value.encode(self.stream.encoding or 'utf-8'))
        self.tail = (self.tail + value)[-160:]
        self.black_background |= '\x1b[40m' in value
        self.colored |= any(r != g or g != b for r, g, b in re.findall(r'\x1b\[38;2;(\d+);(\d+);(\d+)m', value))
        return result

    def flush(self):
        started = time.perf_counter()
        result = self.stream.flush()
        self.flush_seconds += time.perf_counter() - started
        self.flushes += 1
        return result


def native(width, height, destination):
    started = time.perf_counter()
    report = {'method': 'actual finite native GPU app with live audio; diagnostic, not ABBA acceptance',
              'phase': 'starting', 'complete': False, 'passed': False, 'width': width, 'height': height,
              'frames_requested': 60, 'color_mode': 'color', 'requested_renderer': 'gpu',
              'python': sys.version, 'source': str(ROOT), 'hashes': hashes()}
    with destination.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    try:
        os.chdir(ROOT)
        os.environ.update(TMP=str(ROOT), TEMP=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
        console = Console()
        report['font_request'] = console.configure(width, height)
        report['native_console'] = sys.stdin.isatty() and sys.stdout.isatty()
        if not report['native_console']:
            raise RuntimeError('Real native console unavailable')
        output = CountingOutput(sys.stdout)
        sys.stdout = sys.stderr = output
        from ascii3d import app
        original_draw, original_enter, original_exit = app.Terminal.draw, app.Terminal.__enter__, app.Terminal.__exit__
        original_update, original_audio_exit = app.FrameRateCounter.update, app.Audio.__exit__
        original_renderer = app.Renderer
        starts, draw_ms, work_ms, payload, poses, frame_sizes, renderers = [], [], [], [], [], [], []

        def update(self, now):
            starts.append(now)
            return original_update(self, now)

        def enter(self):
            report['console_before'] = console.state()
            return original_enter(self)

        def exit_terminal(self, *args):
            try:
                return original_exit(self, *args)
            finally:
                report['console_after'] = console.state()
                report['restoration_sequence'] = '\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l' in output.tail

        def draw(self, frame):
            before = (output.bytes, output.writes, output.flushes, output.write_seconds, output.flush_seconds)
            tick = time.perf_counter()
            original_draw(self, frame)
            end = time.perf_counter()
            draw_ms.append((end - tick) * 1000)
            work_ms.append((end - starts[-1]) * 1000)
            payload.append({'bytes': output.bytes - before[0], 'writes': output.writes - before[1],
                            'flushes': output.flushes - before[2],
                            'write_ms': (output.write_seconds - before[3]) * 1000,
                            'flush_ms': (output.flush_seconds - before[4]) * 1000})
            frame_sizes.append([frame.width, frame.height])

        def audio_exit(self, *args):
            report['audio'] = {key: getattr(self, key) for key in
                               ('available', 'enabled', 'error', 'blocks_rendered', 'recoveries',
                                'underruns', 'max_write_gap_ms')}
            return original_audio_exit(self, *args)

        class ObservedRenderer(original_renderer):
            def styled_frame(self, player, *args, **kwargs):
                poses.append({key: getattr(player, key) for key in ('x', 'y', 'z', 'yaw', 'pitch')})
                return super().styled_frame(player, *args, **kwargs)

            def close(self):
                renderers.append({'backend': self.backend_name, 'error': self.backend_error})
                return super().close()

        app.Terminal.draw, app.Terminal.__enter__, app.Terminal.__exit__ = draw, enter, exit_terminal
        app.FrameRateCounter.update, app.Audio.__exit__, app.Renderer = update, audio_exit, ObservedRenderer
        report['phase'] = 'running'
        destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        report['exit_code'] = app.main(['--renderer', 'gpu', '--color-mode', 'color', '--keyboard-look',
                                        '--demo', '--frames', '60'])
        report.update(phase='finished', complete=True, frames=len(draw_ms),
                      draw_write_flush=summary(draw_ms), uncapped_loop_work=summary(work_ms),
                      capped_loop_intervals=summary([(b - a) * 1000 for a, b in zip(starts, starts[1:])]),
                      output_frames=payload, frame_sizes=frame_sizes, poses=poses, renderer_health=renderers,
                      colored_foregrounds=output.colored, black_background=output.black_background)
        before, after = report['console_before'], report['console_after']
        report['modes_restored'] = all(before[key] == after[key] for key in ('input_mode', 'output_mode'))
        report['cursor_restored'] = before['cursor_visible'] == after['cursor_visible']
        report['screen_restored'] = before['screen_hash'] == after['screen_hash']
        report['demo_moved'] = len({tuple(pose.values()) for pose in poses}) > 1
        audio = report['audio']
        report['passed'] = (report['exit_code'] == 0 and len(draw_ms) == 60 and report['demo_moved']
                            and all(size == [width, height] for size in frame_sizes)
                            and all(r['backend'] == 'gpu' and not r['error'] for r in renderers)
                            and audio['available'] and audio['enabled'] and audio['blocks_rendered'] > 0
                            and not audio['error'] and not audio['recoveries'] and not audio['underruns']
                            and all(report[key] for key in ('modes_restored', 'cursor_restored',
                                                           'screen_restored', 'restoration_sequence',
                                                           'colored_foregrounds', 'black_background')))
    except BaseException as error:
        report.update(phase='exception', exception=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
    finally:
        report['final_hashes'] = hashes()
        report['source_unchanged'] = report['hashes'] == report['final_hashes']
        report['passed'] &= report['source_unchanged']
        report['seconds'] = time.perf_counter() - started
        destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    if '--native' in sys.argv:
        raise SystemExit(native(int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])))
    if len(sys.argv) != 4:
        raise SystemExit('Usage: python -B quality_native_smoke_tmp.py WIDTH HEIGHT NEW_REPORT.json')
    width, height, destination = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3]).resolve()
    if destination.exists():
        raise SystemExit('Refusing to overwrite native smoke evidence')
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--native',
                              str(width), str(height), str(destination)], cwd=ROOT,
                             creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
    print('Native smoke PID:', child.pid)
    code = child.wait()
    if destination.exists():
        data = json.loads(destination.read_text(encoding='utf-8'))
        print(json.dumps({key: data.get(key) for key in ('phase', 'complete', 'passed', 'frames',
                                                       'source_unchanged', 'seconds', 'exception')}))
    raise SystemExit(code)
