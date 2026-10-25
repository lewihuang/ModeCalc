"""ModeCalc 桌面版 — pywebview 主入口"""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import threading
import time
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app_version import VERSION
from desktop_runtime import DesktopRuntime
from runtime_paths import resource_root, log_path

import webview
import mido

from chord_engine import analyze, note_info
from midi_handler import MidiHandler
from scale_library import ScaleLibrary

UI_INTERVAL = 0.03  # 30ms 固定推送间隔

# ── 日志 ────────────────────────────────────────────

log = logging.getLogger("modecalc")


def configure_logging():
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    except OSError:
        path = Path(tempfile.gettempdir()) / "ModeCalc_debug.log"
        handler = RotatingFileHandler(path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    logging.basicConfig(handlers=[handler], level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s", force=True)
    return path


class MidiState:
    """MIDI 采集 + 状态管理"""

    def __init__(self):
        self._lock = threading.RLock()
        self.handler = MidiHandler()
        self._analysis_mode = "chord"
        self.library = ScaleLibrary.load()
        self._pinned_pcs: frozenset[int] = frozenset()
        self._pinned_tonic: int | None = None
        self._key_sig = "C"

    def set_analysis_mode(self, mode: str, parents: list[str] | None = None):
        if mode not in ("chord", "mode"):
            raise ValueError(f"无效 analysis_mode: {mode}")
        with self._lock:
            self._analysis_mode = mode

    def set_key_signature(self, key_sig: str):
        with self._lock:
            self._key_sig = key_sig

    def set_pinned_scale(self, pcs=None, tonic_pc=None):
        """记录/清除当前固定的调式音阶（前端点击 Matches 时同步）。"""
        with self._lock:
            if not pcs:
                self._pinned_pcs = frozenset()
                self._pinned_tonic = None
                return
            self._pinned_pcs = frozenset(int(p) % 12 for p in pcs)
            self._pinned_tonic = None if tonic_pc is None else int(tonic_pc) % 12

    def get_state(self) -> dict:
        """消费队列 → 返回当前完整和弦数据。每次调用都处理所有新消息。"""
        active = self.handler.poll()  # 永远返回 set[int]
        with self._lock:
            result = analyze(
                active,
                analysis_mode=self._analysis_mode,
                key_sig=self._key_sig,
                pinned_pcs=self._pinned_pcs,
                pinned_tonic=self._pinned_tonic,
                scales=self.library.detection_rows(),
            )
            result["active_notes"] = [note_info(n, self._key_sig) for n in sorted(active)]
        result["sustain"] = self.handler.sustain
        return result


class Api:
    def __init__(self, state, runtime):
        self._state = state
        self._runtime = runtime
        self._window: webview.Window | None = None

    def _set_window(self, w: webview.Window):
        self._window = w

    def set_analysis_mode(self, mode: str, parents: list[str] | None = None):
        """JS → Python: 切换 Chord / Mode 视角（parents 参数保留兼容，已忽略）"""
        self._state.set_analysis_mode(mode, parents)
        log.info(f"analysis_mode={mode}")

    def set_key_signature(self, key_sig: str):
        """JS → Python: 调号变更"""
        self._state.set_key_signature(key_sig)
        log.info(f"key_sig={key_sig}")

    def get_scale_library(self):
        """JS → Python: 读取当前音阶库（含内置默认与用户改动）"""
        return self._state.library.payload()

    def set_scale_enabled(self, scale_id: str, enabled: bool):
        """JS → Python: 切换某个音阶的「使用」状态"""
        result = self._state.library.set_enabled(scale_id, enabled)
        log.info(f"scale enabled: {scale_id} = {enabled} ({result.get('ok')})")
        return result

    def set_group_enabled(self, section: str, group: str, enabled: bool):
        """JS → Python: 分组三态全选"""
        result = self._state.library.set_group_enabled(section, group, enabled)
        log.info(f"scale group: {section}/{group} = {enabled} ({result.get('ok')})")
        return result

    def update_scale(self, scale_id: str, name=None, pcs=None):
        """JS → Python: 修改音阶名称或音集"""
        result = self._state.library.update(scale_id, name=name, pcs=pcs)
        log.info(f"scale update: {scale_id} ({result.get('ok')})")
        return result

    def add_scale(self, name=None, pcs=None):
        """JS → Python: 新建自定义音阶"""
        result = self._state.library.add(name=name, pcs=pcs)
        log.info(f"scale add: {result.get('new_id')} ({result.get('ok')})")
        return result

    def delete_scale(self, scale_id: str):
        """JS → Python: 删除音阶（内置可恢复，自定义永久删除）"""
        result = self._state.library.delete(scale_id)
        log.info(f"scale delete: {scale_id} ({result.get('ok')})")
        return result

    def reset_scale_library(self):
        """JS → Python: 恢复内置默认，保留自定义音阶"""
        result = self._state.library.reset()
        log.info(f"scale library reset ({result.get('ok')})")
        return result

    def set_pinned_scale(self, pcs=None, tonic_pc=None):
        """JS → Python: 固定/取消固定某个调式音阶"""
        self._state.set_pinned_scale(pcs, tonic_pc)

    def frontend_ready(self, capabilities=None):
        # A bridge invocation proves Cocoa/WKWebView's event loop is running.
        # pywebview.start(func=...) itself invokes func before creating a window.
        self._runtime.start()
        return {
            "version": VERSION, "platform": sys.platform,
            "library": self._state.library.payload(),
            "state": self._runtime.frontend_ready(),
        }

    def list_midi_ports(self):
        return self._runtime.snapshot().get("midi", {}).get("available", [])

    def refresh_midi_ports(self):
        return self._runtime.command("refresh")

    def select_midi_port(self, port_name: str | None = None):
        if port_name is not None and not isinstance(port_name, str):
            raise ValueError("无效 MIDI 端口名称")
        return self._runtime.command("select", port_name)

    def quit_app(self):
        if self._window:
            self._window.destroy()


def _smoke_test(window, runtime):
    """Exercise the real WebView and bridge in source and standalone builds."""
    deadline = time.monotonic() + 20
    result = {"ok": False}
    try:
        while time.monotonic() < deadline:
            if window.evaluate_js("Boolean(window.__modecalcReady)"):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("桌面桥接启动超时")
        midi_port = os.environ.get("MODECALC_SMOKE_MIDI_PORT")
        if midi_port:
            selected = runtime.command("select", midi_port)
            assert selected["ok"], selected
            while time.monotonic() < deadline:
                notes = runtime.snapshot().get("active_notes", [])
                if {note["midi"] for note in notes} == {60, 64, 67}:
                    if window.evaluate_js("document.getElementById('chord-name').textContent") == "C":
                        break
                time.sleep(0.03)
            else:
                raise RuntimeError("CoreMIDI 测试输入未到达界面")
        else:
            sample = analyze({60, 64, 67})
            sample["active_notes"] = [note_info(n) for n in (60, 64, 67)]
            window.evaluate_js('window.updateUI(' + json.dumps(sample) + ')')
        checks = window.evaluate_js("""({
            chord: document.getElementById('chord-name').textContent,
            bravura: document.fonts.check('16px Bravura', '\uE050'),
            academico: document.fonts.check('16px Academico', 'ModeCalc'),
            fonts: Array.from(document.fonts).map(f => ({family: f.family, status: f.status})),
            fontStatus: document.getElementById('db-font').textContent,
            keys: document.querySelectorAll('#keyboard rect.key-white').length,
            staff: document.querySelectorAll('#staff svg, #staff canvas').length,
            fretboard: document.querySelectorAll('#fretboard svg').length,
            transport: location.hash,
            bridge: typeof window.pywebview.api.frontend_ready
        })""")
        assert checks["chord"] == "C", checks
        assert checks["bravura"] and checks["academico"], checks
        assert checks["keys"] == 52 and checks["staff"] > 0 and checks["fretboard"] > 0, checks
        assert checks["bridge"] == "function", checks
        result = {"ok": True, "checks": checks, "midi": runtime.snapshot().get("midi")}
        result["real_midi_input"] = bool(midi_port)
        result["runtime_architecture"] = platform.machine()
    except Exception as exc:
        result["error"] = str(exc)
        log.exception("桌面冒烟失败")
    finally:
        log.info("SMOKE_RESULT %s", json.dumps(result, ensure_ascii=False))
        if os.environ.get("MODECALC_SMOKE_RESULT"):
            Path(os.environ["MODECALC_SMOKE_RESULT"]).write_text(json.dumps(result), encoding="utf-8")
        window.destroy()


def main():
    path = configure_logging()
    fault_log = None
    if "--smoke-test" in sys.argv:
        import faulthandler
        fault_log = path.open("a", encoding="utf-8")
        faulthandler.dump_traceback_later(25, file=fault_log)
    log.info("ModeCalc %s 启动 | %s | Log: %s", VERSION, sys.platform, path)
    backend = "mido.backends.rtmidi/MACOSX_CORE" if sys.platform == "darwin" else "mido.backends.rtmidi"
    mido.set_backend(backend, load=True)
    state = MidiState()
    html_path = resource_root() / "static" / "index.html"
    if not html_path.is_file():
        raise FileNotFoundError(f"缺少界面资源: {html_path}")
    # Mac uses pywebview's loopback static server; the fragment prevents an
    # accidental WebSocket connection before the native bridge is injected.
    url = str(html_path) if sys.platform == "darwin" else html_path.as_uri()
    window = None
    runtime = DesktopRuntime(state, lambda data: window.run_js(
        'window.updateUI(' + json.dumps(data) + ')'))
    api = Api(state, runtime)
    window = webview.create_window(
        "ModeCalc", url=url + "#desktop", js_api=api, width=1200, height=720,
        resizable=True, min_size=(1024, 640), background_color="#FFFFFF",
    )
    api._set_window(window)
    window.events.closing += runtime.request_stop
    window.events.closed += runtime.request_stop
    try:
        def started():
            log.info("等待前端握手后初始化 MIDI")
            if "--smoke-test" in sys.argv:
                _smoke_test(window, runtime)

        webview.start(func=started, debug=False, http_server=sys.platform == "darwin")
    finally:
        runtime.close()
        if fault_log:
            faulthandler.cancel_dump_traceback_later()
            fault_log.close()
        log.info("ModeCalc 已退出")
        logging.shutdown()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("ModeCalc 启动失败")
        raise
