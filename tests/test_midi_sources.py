"""Source/channel isolation, hotplug and stale callback regression tests."""

from unittest.mock import MagicMock

import mido
import pytest

from midi_handler import MidiHandler


@pytest.fixture
def devices(monkeypatch):
    names = ["Keyboard A", "Keyboard B"]
    callbacks = {}
    ports = {}

    def open_input(name, callback):
        callbacks[name] = callback
        ports[name] = MagicMock()
        return ports[name]

    monkeypatch.setattr("midi_handler.mido.get_input_names", lambda: list(names))
    monkeypatch.setattr("midi_handler.mido.open_input", open_input)
    handler = MidiHandler()
    handler.open()
    yield handler, names, callbacks, ports
    handler.close()


def test_same_note_from_two_devices(devices):
    handler, _, callbacks, _ = devices
    callbacks["Keyboard A"](mido.Message("note_on", note=60))
    callbacks["Keyboard B"](mido.Message("note_on", note=60))
    assert handler.poll() == {60}
    callbacks["Keyboard A"](mido.Message("note_off", note=60))
    assert handler.poll() == {60}
    callbacks["Keyboard B"](mido.Message("note_off", note=60))
    assert handler.poll() == set()


def test_channels_and_pedals_are_independent(devices):
    handler, _, callbacks, _ = devices
    a = callbacks["Keyboard A"]
    a(mido.Message("control_change", channel=0, control=64, value=127))
    a(mido.Message("note_on", channel=0, note=60))
    a(mido.Message("note_on", channel=1, note=64))
    a(mido.Message("note_off", channel=0, note=60))
    a(mido.Message("note_off", channel=1, note=64))
    callbacks["Keyboard B"](mido.Message("note_on", note=67))
    callbacks["Keyboard B"](mido.Message("note_off", note=67))
    assert handler.poll() == {60}
    assert handler.sustain
    a(mido.Message("control_change", control=64, value=0))
    assert handler.poll() == set()
    assert not handler.sustain


def test_hotplug_preserves_other_device_and_rejects_late_callbacks(devices):
    handler, names, callbacks, ports = devices
    old_a = callbacks["Keyboard A"]
    old_a(mido.Message("note_on", note=60))
    callbacks["Keyboard B"](mido.Message("note_on", note=67))
    assert handler.poll() == {60, 67}
    names.remove("Keyboard A")
    handler.refresh()
    old_a(mido.Message("note_on", note=61))
    assert handler.poll() == {67}
    assert not ports["Keyboard B"].close.called
    names.append("Keyboard A")
    handler.refresh()
    old_a(mido.Message("note_on", note=62))
    callbacks["Keyboard A"](mido.Message("note_on", note=64))
    assert handler.poll() == {64, 67}


def test_partial_failure_keeps_working_port(monkeypatch):
    monkeypatch.setattr("midi_handler.mido.get_input_names", lambda: ["bad", "good"])
    good = MagicMock()

    def open_input(name, callback):
        if name == "bad":
            raise OSError("device busy")
        return good

    monkeypatch.setattr("midi_handler.mido.open_input", open_input)
    handler = MidiHandler()
    handler.open()
    assert handler.status()["state"] == "PARTIAL"
    assert handler.status()["opened"] == ["good"]
    handler.close()
    handler.close()
    good.close.assert_called_once()


def test_mac_does_not_apply_windows_name_filter(monkeypatch):
    monkeypatch.setattr("midi_handler.sys.platform", "darwin")
    assert MidiHandler._eligible(["IAC Through", "Microsoft GS"]) == ["IAC Through", "Microsoft GS"]


def test_enumeration_failure_is_not_reported_as_no_device(monkeypatch):
    def unavailable():
        raise OSError("CoreMIDI unavailable")

    monkeypatch.setattr("midi_handler.mido.get_input_names", unavailable)
    handler = MidiHandler()
    handler.refresh()
    assert handler.status()["state"] == "ERROR"
    assert handler.status()["error"] == "CoreMIDI unavailable"
