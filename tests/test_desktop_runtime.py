"""The real MIDI owner and UI publisher, with an isolated backend."""

import threading
import time
from unittest.mock import MagicMock

from app import Api, MidiState
from desktop_runtime import DesktopRuntime


def test_handshake_commands_and_shutdown(tmp_path, monkeypatch):
    monkeypatch.setenv("MODECALC_SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr("midi_handler.mido.get_input_names", lambda: ["Test"])
    port = MagicMock()
    owner_threads = []

    def open_input(name, callback):
        owner_threads.append(threading.get_ident())
        return port

    monkeypatch.setattr("midi_handler.mido.open_input", open_input)
    state = MidiState()
    published = []
    received = threading.Event()

    def publish(data):
        published.append(data)
        received.set()

    runtime = DesktopRuntime(state, publish)
    api = Api(state, runtime)
    runtime.start()
    try:
        deadline = time.monotonic() + 2
        while not runtime.snapshot() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert runtime.snapshot()
        assert not received.wait(0.08)  # Not ready: do not call JS.
        initial = api.frontend_ready()
        assert initial["library"]["total"] == 71
        assert received.wait(1)
        selected = api.select_midi_port("Test")
        assert selected["ok"]
        assert selected["sequence"] >= initial["state"]["sequence"]
        assert len(set(owner_threads)) == 1
        assert owner_threads[0] != threading.get_ident()
        state.set_analysis_mode("mode")
        runtime.start()  # Repeated bootstrap cannot start a second owner.
        assert len(runtime._threads) == 2
    finally:
        runtime.close()
    count = len(published)
    assert all(not thread.is_alive() for thread in runtime._threads)
    assert not api.refresh_midi_ports()["ok"]
    assert len(published) == count
    assert port.close.called


def test_no_device_is_recoverable(tmp_path, monkeypatch):
    monkeypatch.setenv("MODECALC_SETTINGS_DIR", str(tmp_path))
    names = []
    monkeypatch.setattr("midi_handler.mido.get_input_names", lambda: names[:])
    monkeypatch.setattr("midi_handler.mido.open_input", lambda *args, **kwargs: MagicMock())
    runtime = DesktopRuntime(MidiState(), lambda data: None)
    runtime.start()
    try:
        assert runtime.command("refresh")["state"] == "NO_DEVICE"
        names.append("New keyboard")
        assert runtime.command("refresh")["opened"] == ["New keyboard"]
        names.clear()
        assert runtime.command("refresh")["opened"] == []
    finally:
        runtime.close()


def test_api_defers_native_midi_until_bridge_is_ready(tmp_path, monkeypatch):
    monkeypatch.setenv("MODECALC_SETTINGS_DIR", str(tmp_path))
    names = MagicMock(return_value=[])
    monkeypatch.setattr("midi_handler.mido.get_input_names", names)
    runtime = DesktopRuntime(MidiState(), lambda data: None)
    api = Api(runtime._state, runtime)
    try:
        names.assert_not_called()
        assert not runtime._threads
        api.frontend_ready()
        assert runtime.command("refresh")["state"] == "NO_DEVICE"
        assert names.called
    finally:
        runtime.close()
