"""Device-driven Windows PCM output and a safety cap for immediate-return sinks."""

import os
import time


SAMPLE_RATE = 22050
BUFFER_FRAMES = 1024
BUFFER_COUNT = 3


class StreamPacer:
    """Let driver backpressure set the rate; cap only sinks with no backpressure."""

    def __init__(self, frames, capacity, now):
        self.period = frames / SAMPLE_RATE
        self.capacity = capacity
        self.anchor = now
        self.written = 0

    def blocked(self, now):
        self.anchor, self.written = now, 0

    def delay(self, now):
        return max(0.0, (self.written - self.capacity + 1) * self.period - (now - self.anchor))

    def submitted(self):
        self.written += 1


class WaveOutput:
    """Prime ~139 ms of audio, then refill on native completion events."""

    def __init__(self, frames=BUFFER_FRAMES, buffer_count=BUFFER_COUNT):
        if os.name != "nt":
            raise OSError("Live audio currently requires Windows; WAV export works on all platforms.")
        import ctypes as ct
        from ctypes import wintypes as wt

        class Format(ct.Structure):
            _pack_ = 1
            _fields_ = [("tag", wt.WORD), ("channels", wt.WORD), ("rate", wt.DWORD),
                        ("bytes_per_second", wt.DWORD), ("align", wt.WORD),
                        ("bits", wt.WORD), ("extra", wt.WORD)]

        class Header(ct.Structure):
            _fields_ = [("data", ct.c_void_p), ("length", wt.DWORD), ("recorded", wt.DWORD),
                        ("user", ct.c_size_t), ("flags", wt.DWORD), ("loops", wt.DWORD),
                        ("next", ct.c_void_p), ("reserved", ct.c_size_t)]

        self.ct, self.api = ct, ct.WinDLL("winmm")
        self.kernel = ct.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateEventW.argtypes = [ct.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
        self.kernel.CreateEventW.restype = wt.HANDLE
        for name in ("SetEvent", "ResetEvent", "CloseHandle"):
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = [wt.HANDLE], wt.BOOL
        self.kernel.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
        self.kernel.WaitForSingleObject.restype = wt.DWORD
        self.handle, self.frames, self.buffers = wt.HANDLE(), frames, []
        self.buffer_count = buffer_count
        self._started, self._submitted = False, 0
        self.underruns, self.max_write_gap_ms = 0, 0.0
        self._last_write = None
        self.event = self.kernel.CreateEventW(None, True, False, None)
        if not self.event:
            raise ct.WinError(ct.get_last_error())
        self.api.waveOutOpen.argtypes = [ct.POINTER(wt.HANDLE), wt.UINT, ct.POINTER(Format),
                                         ct.c_size_t, ct.c_size_t, wt.DWORD]
        self.api.waveOutOpen.restype = wt.UINT
        for name in ("waveOutPrepareHeader", "waveOutUnprepareHeader", "waveOutWrite"):
            function = getattr(self.api, name)
            function.argtypes, function.restype = [wt.HANDLE, ct.POINTER(Header), wt.UINT], wt.UINT
        for name in ("waveOutReset", "waveOutClose", "waveOutPause", "waveOutRestart"):
            function = getattr(self.api, name)
            function.argtypes, function.restype = [wt.HANDLE], wt.UINT
        fmt = Format(1, 2, SAMPLE_RATE, SAMPLE_RATE * 4, 4, 16, 0)
        # CALLBACK_EVENT: the driver signals the event when buffers complete.
        result = self.api.waveOutOpen(ct.byref(self.handle), 0xFFFFFFFF,
                                      ct.byref(fmt), self.event, 0, 0x50000)
        if result:
            self.kernel.CloseHandle(self.event)
            self.event = None
            raise OSError(f"Windows audio output unavailable (waveOut error {result}).")
        try:
            if self.api.waveOutPause(self.handle):
                raise OSError("Cannot prime Windows audio output.")
            for _ in range(buffer_count):
                buffer = ct.create_string_buffer(frames * 4)
                header = Header(ct.addressof(buffer), frames * 4, 0, 0, 0, 0, None, 0)
                if self.api.waveOutPrepareHeader(self.handle, ct.byref(header), ct.sizeof(header)):
                    raise OSError("Cannot prepare Windows audio buffers.")
                self.buffers.append((buffer, header))
            self.kernel.ResetEvent(self.event)
        except BaseException:
            self.close()
            raise

    @property
    def queued(self):
        return sum(bool(header.flags & 0x10) for _, header in self.buffers)

    def ready(self):
        # Reset BEFORE inspecting flags, so a completion racing with the check
        # cannot be lost between the flag check and WaitForSingleObject.
        self.kernel.ResetEvent(self.event)
        return next((item for item in self.buffers if not item[1].flags & 0x10), None)

    def wait(self, timeout):
        result = self.kernel.WaitForSingleObject(self.event, max(1, round(timeout * 1000)))
        if result == 0xFFFFFFFF:
            raise self.ct.WinError(self.ct.get_last_error())

    def wake(self):
        if self.event:
            self.kernel.SetEvent(self.event)

    def write(self, item, samples):
        buffer, header = item
        if len(samples) != header.length:
            raise ValueError("Audio buffer size mismatch")
        now = time.perf_counter()
        if self._started and self._submitted > self.buffer_count and self.queued == 0:
            self.underruns += 1
        if self._last_write is not None:
            self.max_write_gap_ms = max(self.max_write_gap_ms, (now - self._last_write) * 1000)
        self._last_write = now
        # The fixed buffer's raw setter copies in place without releasing the
        # GIL for an extra tiny ctypes call on every audio block.
        buffer.raw = samples
        if self.api.waveOutWrite(self.handle, self.ct.byref(header), self.ct.sizeof(header)):
            raise OSError("Windows audio playback failed.")
        self._submitted += 1
        if not self._started and self._submitted == self.buffer_count:
            if self.api.waveOutRestart(self.handle):
                raise OSError("Cannot start Windows audio output.")
            self._started = True

    def close(self):
        if self.handle:
            self.api.waveOutReset(self.handle)
            for _, header in self.buffers:
                self.api.waveOutUnprepareHeader(self.handle, self.ct.byref(header), self.ct.sizeof(header))
            self.api.waveOutClose(self.handle)
            self.handle = None
        if self.event:
            self.kernel.CloseHandle(self.event)
            self.event = None
