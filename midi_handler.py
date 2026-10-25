"""RtMidi callbacks enqueue messages; the owner thread manages ports and state."""

import logging
import queue
import sys
from dataclasses import dataclass, field

import mido

log = logging.getLogger("modecalc")
VIRTUAL_PORT_KEYWORDS = ("Through", "Microsoft GS", "MIDI Mapper")


@dataclass
class _Channel:
    active: set[int] = field(default_factory=set)
    sustained: set[int] = field(default_factory=set)
    sustain: bool = False


class MidiHandler:
    def __init__(self):
        self._queue = queue.Queue()
        self._ports: list[mido.ports.BaseInput] = []
        self._inputs = {}
        self._tokens = {}
        self._next_token = 0
        self._channels = {}
        self._active_notes: set[int] = set()
        self._selected = None
        self._available = []
        self._failed = {}
        self._error = ""
        self._enumeration_error = False

    def open(self, port_name: str | None = None):
        self.close()
        self._selected = port_name or None
        self.refresh()
        if not self._ports:
            raise RuntimeError(self._error or "没有可用的 MIDI 输入设备")

    def refresh(self):
        """Reconcile changed inputs, preserving notes on surviving devices."""
        try:
            self._available = self.list_ports()
            self._enumeration_error = False
        except Exception as exc:
            self._enumeration_error = True
            self._error = str(exc)
            return
        if self._selected:
            desired = [self._selected] if self._selected in self._available else []
        else:
            desired = self._eligible(self._available)
        for name in list(self._inputs):
            if name not in desired:
                self._remove(name)
        self._failed = {}
        for name in desired:
            if name in self._inputs:
                continue
            self._next_token += 1
            token = self._next_token
            self._tokens[name] = token

            def callback(msg, source=name, generation=token):
                self._queue.put((source, generation, msg))

            try:
                self._inputs[name] = mido.open_input(name, callback=callback)
            except Exception as exc:
                self._tokens.pop(name, None)
                self._failed[name] = str(exc)
        self._ports = list(self._inputs.values())
        self._error = "; ".join(f"{name}: {error}" for name, error in self._failed.items())
        if not self._ports and not self._error:
            self._error = "等待 MIDI 设备" if self._selected else "没有可用的 MIDI 输入设备"
        self._update_active()

    def _remove(self, name):
        # Invalidate callbacks before closing: late notes must not revive state.
        self._tokens.pop(name, None)
        port = self._inputs.pop(name)
        try:
            port.close()
        except Exception:
            log.exception("关闭 MIDI 端口失败: %s", name)
        self._channels = {key: value for key, value in self._channels.items() if key[0] != name}

    def _callback(self, msg):
        """Synthetic/default source for deterministic MIDI tests."""
        self._queue.put((None, 0, msg))

    def poll(self) -> set[int]:
        while True:
            try:
                source, token, msg = self._queue.get_nowait()
            except queue.Empty:
                break
            if source is not None and self._tokens.get(source) != token:
                continue
            channel = getattr(msg, "channel", 0)
            state = self._channels.setdefault((source, token, channel), _Channel())
            if msg.type == "note_on" and msg.velocity > 0:
                state.active.add(msg.note)
                state.sustained.discard(msg.note)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                if state.sustain:
                    state.sustained.add(msg.note)
                else:
                    state.active.discard(msg.note)
            elif msg.type == "control_change" and msg.control == 64:
                new_value = msg.value >= 64
                if state.sustain and not new_value:
                    state.active -= state.sustained
                    state.sustained.clear()
                state.sustain = new_value
            elif msg.type == "control_change" and msg.control in (120, 123):
                state.active.clear()
                state.sustained.clear()
        self._update_active()
        return set(self._active_notes)

    def _update_active(self):
        self._active_notes = set().union(*(state.active for state in self._channels.values()))

    @property
    def sustain(self) -> bool:
        return any(state.sustain for state in self._channels.values())

    def active_notes(self) -> set[int]:
        return set(self._active_notes)

    def close(self):
        for name in list(self._inputs):
            self._remove(name)
        self._ports.clear()
        self._channels.clear()
        self._active_notes.clear()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def select_port(self, port_name: str | None = None):
        self.open(port_name)

    def status(self):
        state = "CONNECTED" if self._ports else ("DISCONNECTED" if self._selected else "NO_DEVICE")
        if self._failed or self._enumeration_error:
            state = "PARTIAL" if self._ports else "ERROR"
        return {
            "state": state, "selected": self._selected,
            "available": list(self._available), "opened": list(self._inputs),
            "failed": dict(self._failed), "error": self._error,
        }

    @staticmethod
    def list_ports() -> list[str]:
        return mido.get_input_names()

    @staticmethod
    def _eligible(names):
        if sys.platform != "win32":
            return list(names)
        return [name for name in names if not any(k in name for k in VIRTUAL_PORT_KEYWORDS)]

    @staticmethod
    def list_real_ports() -> list[str]:
        return MidiHandler._eligible(MidiHandler.list_ports())
