"""Isolate native playback from the renderer's Python execution lock."""

import ctypes
import multiprocessing
import queue
import time


def _worker(controls, status, error, events, stop, ready, volume, bank, output_factory):
    # Import in the spawned child, after module initialization has completed.
    from .sound import ThreadAudio, WaveOutput

    engine = None
    last_status, last_error = None, None

    def publish(message=None):
        nonlocal last_status, last_error
        if engine is not None:
            output = engine.output
            native_active = bool(getattr(output, "handle", None))
            underruns = engine.underruns + (getattr(output, "underruns", 0) if native_active else 0)
            gap = max(engine.max_write_gap_ms, getattr(output, "max_write_gap_ms", 0))
            snapshot = [float(engine.available), engine.blocks_rendered, engine.recoveries, underruns, gap]
            if snapshot != last_status:
                status[:] = snapshot
                last_status = snapshot
        if message is not None and str(message) != last_error:
            with error.get_lock():
                error.get_obj().value = str(message)[:511]
            last_error = str(message)

    try:
        state = controls[:]
        engine = ThreadAudio(bool(state[6]), volume, output_factory or WaveOutput, bank)
        generation = int(state[8])
        # Signal readiness after prefill and the first device completion, not
        # merely after opening a handle. The renderer starts after priming.
        deadline = time.monotonic() + 0.35
        wanted = getattr(engine.output, "buffer_count", 3) + 1
        while engine.available and engine.blocks_rendered < wanted and time.monotonic() < deadline:
            time.sleep(0.002)
        publish(engine.error)
        ready.set()
        while not stop.is_set():
            state = controls[:]
            if int(state[8]) != generation:
                generation = int(state[8])
                engine._clear()
                if state[6] and not engine.available:
                    engine._retry.set()
            engine._enabled, engine._paused = bool(state[6]), bool(state[7])
            engine.listener, engine.ambient = tuple(state[:3]), tuple(state[3:6])
            for _ in range(32):
                try:
                    epoch, event = events.get_nowait()
                except queue.Empty:
                    break
                if epoch == generation:
                    engine.emit(event)
            publish(engine.error)
            stop.wait(0.02)
    except Exception as exception:
        status[0] = 0
        publish(exception)
        ready.set()
    finally:
        if engine is not None:
            engine.close()
            publish(engine.error or None)
        status[0] = 0
        ready.set()


class ProcessAudio:
    def __init__(self, enabled=True, volume=0.55, bank=None, output_factory=None):
        context = multiprocessing.get_context("spawn")
        # Listener, three ambience values, enable/pause flags, control generation.
        self._controls = context.Array("d", [0, 0, 1.57079632679, 0, 0, 0, float(enabled), 0, 0])
        self._status = context.Array("d", [0, 0, 0, 0, 0])
        self._error = context.Array(ctypes.c_wchar, 512)
        self._events = context.Queue(maxsize=32)
        self._stop, ready = context.Event(), context.Event()
        self._wanted, self._paused, self._epoch = enabled, False, 0
        self._listener, self._ambient = (0.0, 0.0, 1.57079632679), (0.0, 0.0, 0.0)
        self._closed = False
        self._process = context.Process(target=_worker,
                                        args=(self._controls, self._status, self._error, self._events,
                                              self._stop, ready, volume, bank, output_factory),
                                        name="monolith-audio", daemon=True)
        self._process.start()
        if not ready.wait(5):
            with self._error.get_lock():
                self._error.get_obj().value = "Audio worker did not initialize in time."

    @property
    def available(self):
        return not self._closed and self._process.is_alive() and bool(self._status[0])

    @property
    def enabled(self):
        return self._wanted and self.available

    @property
    def error(self):
        with self._error.get_lock():
            message = self._error.get_obj().value
        if not message and not self._closed and not self._process.is_alive():
            return "Audio worker stopped."
        return message

    @property
    def blocks_rendered(self):
        return int(self._status[1])

    @property
    def recoveries(self):
        return int(self._status[2])

    @property
    def underruns(self):
        return int(self._status[3])

    @property
    def max_write_gap_ms(self):
        return self._status[4]

    @property
    def listener(self):
        return self._listener

    @listener.setter
    def listener(self, value):
        value = tuple(value)
        if value == self._listener:
            return
        self._listener = value
        self._controls[:3] = self._listener

    @property
    def ambient(self):
        return self._ambient

    @ambient.setter
    def ambient(self, value):
        value = tuple(value) if len(value) == 3 else tuple(value) + (0.0,)
        if value == self._ambient:
            return
        self._ambient = value
        self._controls[3:6] = self._ambient

    def _changed(self):
        self._epoch += 1
        self._controls[6:9] = [float(self._wanted), float(self._paused), float(self._epoch)]

    def emit(self, event):
        from .sound import EFFECTS
        if event.name not in EFFECTS:
            raise ValueError(f"No sound registered for event: {event.name}")
        if self.enabled:
            try:
                self._events.put_nowait((self._epoch, event))
            except queue.Full:
                pass

    def pause(self, paused):
        if paused != self._paused:
            self._paused = paused
            self._changed()

    def toggle(self):
        from .events import GameEvent
        self._wanted = True if not self.available else not self._wanted
        self._changed()
        if self.enabled:
            self.emit(GameEvent("ui_toggle"))
        return self.enabled

    def close(self):
        if self._closed:
            return
        self._stop.set()
        self._process.join(timeout=3)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=1)
        self._events.close()
        self._events.cancel_join_thread()
        self._closed = True
