"""MidiHandler 测试 — mock mido 端口代替物理设备"""

from unittest.mock import MagicMock, patch, call
import pytest
import mido
from midi_handler import MidiHandler


@pytest.fixture(autouse=True)
def isolated_backend(monkeypatch):
    # Unit tests never touch CoreMIDI/WinMM, even when open() enumerates ports.
    monkeypatch.setattr("midi_handler.mido.get_input_names", lambda: ["TestPort"])
    monkeypatch.setattr("midi_handler.sys.platform", "win32")


def _note_on(note=60, velocity=100):
    return mido.Message("note_on", note=note, velocity=velocity)


def _note_off(note=60):
    return mido.Message("note_off", note=note)


def test_open_with_port_name():
    h = MidiHandler()
    with patch("midi_handler.mido.open_input") as mock_open:
        mock_port = MagicMock()
        mock_open.return_value = mock_port
        h.open("TestPort")
        assert mock_open.call_args.args == ("TestPort",)
        callback = mock_open.call_args.kwargs["callback"]
        callback(_note_on())
        assert h.poll() == {60}


def test_open_all_ports():
    h = MidiHandler()
    with (
        patch("midi_handler.mido.get_input_names") as mock_names,
        patch("midi_handler.mido.open_input") as mock_open,
    ):
        mock_names.return_value = ["Port A", "Port B", "Microsoft GS Wavetable Synth"]
        h.open()
        # 虚拟端口被过滤，只打开 Port A 和 Port B
        assert mock_open.call_count == 2
        assert [c.args[0] for c in mock_open.call_args_list] == ["Port A", "Port B"]


def test_open_all_virtual_raises():
    """只有虚拟端口时抛出异常（不监听软件合成器）"""
    h = MidiHandler()
    with patch("midi_handler.mido.get_input_names",
               return_value=["Microsoft GS Wavetable Synth"]):
        with pytest.raises(RuntimeError, match="没有可用"):
            h.open()


def test_open_no_ports_raises():
    h = MidiHandler()
    with patch("midi_handler.mido.get_input_names", return_value=[]):
        with pytest.raises(RuntimeError, match="没有可用"):
            h.open()


def test_note_on_adds_to_active():
    h = MidiHandler()
    h._callback(_note_on(60))
    result = h.poll()
    assert result == {60}


def test_note_off_removes():
    h = MidiHandler()
    h._callback(_note_on(60))
    h.poll()  # 消费 note_on
    h._callback(_note_off(60))
    result = h.poll()
    assert result == set()


def test_multiple_notes():
    h = MidiHandler()
    h._callback(_note_on(60))
    h._callback(_note_on(64))
    h._callback(_note_on(67))
    result = h.poll()
    assert result == {60, 64, 67}


def test_note_on_velocity_zero_is_note_off():
    h = MidiHandler()
    h._callback(_note_on(60))
    h.poll()
    h._callback(_note_on(60, velocity=0))
    result = h.poll()
    assert result == set()


def test_poll_no_change_returns_empty():
    h = MidiHandler()
    assert h.poll() == set()


def test_poll_after_consumed_returns_active():
    h = MidiHandler()
    h._callback(_note_on(60))
    h.poll()
    # poll() 永远返回当前 active_notes 快照，note 仍在
    assert h.poll() == {60}


def test_active_notes_snapshot():
    h = MidiHandler()
    h._callback(_note_on(60))
    h._callback(_note_on(64))
    h.poll()
    snap = h.active_notes()
    assert snap == {60, 64}
    # 快照不引用内部 set
    snap.add(99)
    assert h.active_notes() == {60, 64}


def test_close():
    h = MidiHandler()
    with patch("midi_handler.mido.open_input") as mock_open:
        mock_port = MagicMock()
        mock_open.return_value = mock_port
        h.open("TestPort")
        h.close()
        mock_port.close.assert_called_once()
        assert h._ports == []


def test_list_ports():
    with patch("midi_handler.mido.get_input_names",
               return_value=["Port A", "Port B"]):
        assert MidiHandler.list_ports() == ["Port A", "Port B"]


def test_list_real_ports_filters_virtual():
    with patch("midi_handler.mido.get_input_names",
               return_value=["Port A", "Microsoft GS Wavetable Synth"]):
        assert MidiHandler.list_real_ports() == ["Port A"]


def test_rapid_arpeggio_no_miss():
    """快速琶音不丢消息"""
    h = MidiHandler()
    for note in [60, 64, 67, 72]:
        h._callback(_note_on(note))
    result = h.poll()
    assert result == {60, 64, 67, 72}


def test_note_on_twice_idempotent():
    h = MidiHandler()
    h._callback(_note_on(60))
    h._callback(_note_on(60))
    result = h.poll()
    assert result == {60}
