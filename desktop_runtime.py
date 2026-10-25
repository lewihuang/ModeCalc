"""Own MIDI on one worker; publish latest snapshots without blocking MIDI I/O."""

import copy
import logging
import queue
import threading
import time
from concurrent.futures import Future, TimeoutError

log = logging.getLogger("modecalc")


class DesktopRuntime:
    def __init__(self, state, publish, refresh_interval=1.0):
        self._state = state
        self._publish = publish
        self._refresh_interval = refresh_interval
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._commands = queue.Queue()
        self._lock = threading.Lock()
        self._snapshot = {}
        self._sequence = 0
        self._threads = []

    def start(self):
        with self._lock:
            if self._threads or self._stop.is_set():
                return
            self._threads = [
                threading.Thread(target=self._work, name="ModeCalc-MIDI"),
                threading.Thread(target=self._push, name="ModeCalc-UI", daemon=True),
            ]
            for thread in self._threads:
                thread.start()

    def frontend_ready(self):
        if self._stop.is_set():
            raise RuntimeError("应用正在退出")
        self._ready.set()
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._snapshot)

    def command(self, operation, *args):
        future = Future()
        with self._lock:
            if self._stop.is_set():
                return {"ok": False, "error": "应用正在退出"}
            self._commands.put((operation, args, future))
        try:
            return future.result(timeout=5)
        except TimeoutError:
            return {"ok": False, "error": "MIDI 操作超时，请刷新设备状态"}

    def request_stop(self, *args):
        self._ready.clear()
        with self._lock:
            self._stop.set()

    def close(self):
        self.request_stop()
        for thread in self._threads:
            thread.join(timeout=2)
            if thread.is_alive():
                log.error("退出时线程未收敛: %s", thread.name)

    def _record(self):
        data = self._state.get_state()
        data["midi"] = self._state.handler.status()
        with self._lock:
            previous = {k: v for k, v in self._snapshot.items() if k != "sequence"}
            if data != previous:
                self._sequence += 1
                self._snapshot = {**data, "sequence": self._sequence}

    def _work(self):
        try:
            try:
                self._state.handler.open()
            except Exception as exc:
                log.info("启动 MIDI: %s", exc)
            last_refresh = time.monotonic()
            last_error = 0.0
            while not self._stop.is_set():
                try:
                    while not self._stop.is_set():
                        try:
                            operation, args, future = self._commands.get_nowait()
                        except queue.Empty:
                            break
                        try:
                            if operation == "select":
                                self._state.handler.select_port(*args)
                            elif operation == "refresh":
                                self._state.handler.refresh()
                            else:
                                raise ValueError("未知 MIDI 操作")
                            self._record()
                            future.set_result({"ok": True, **self._state.handler.status(),
                                               "sequence": self.snapshot().get("sequence", 0)})
                        except Exception as exc:
                            future.set_result({"ok": False, **self._state.handler.status(), "error": str(exc),
                                               "sequence": self.snapshot().get("sequence", 0)})
                    if time.monotonic() - last_refresh >= self._refresh_interval:
                        self._state.handler.refresh()
                        last_refresh = time.monotonic()
                    self._record()
                except Exception:
                    if time.monotonic() - last_error > 5:
                        log.exception("MIDI 工作线程错误")
                        last_error = time.monotonic()
                self._stop.wait(0.005)
        finally:
            self._state.handler.close()
            while True:
                try:
                    _, _, future = self._commands.get_nowait()
                except queue.Empty:
                    break
                future.set_result({"ok": False, "error": "应用已退出"})

    def _push(self):
        last_sequence = None
        while not self._stop.wait(0.03):
            if not self._ready.is_set():
                continue
            data = self.snapshot()
            if not data or data.get("sequence") == last_sequence:
                continue
            try:
                self._publish(data)
                last_sequence = data.get("sequence")
            except Exception:
                if not self._stop.is_set():
                    log.exception("界面推送失败，等待前端重新就绪")
                    self._ready.clear()
