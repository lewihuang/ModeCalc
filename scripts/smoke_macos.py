"""Verify a standalone app with a private CoreMIDI virtual output and real UI."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import mido
import rtmidi


def main():
    app = Path(sys.argv[1]).resolve()
    executable = app / "Contents" / "MacOS" / "ModeCalc"
    output = rtmidi.MidiOut()
    name = f"ModeCalc Smoke {os.getpid()}"
    output.open_virtual_port(name)
    try:
        ports = mido.get_input_names()
        port = next(port for port in ports if name in port)
        with tempfile.TemporaryDirectory(prefix="modecalc-smoke-") as directory:
            work = Path(directory)
            result_file = work / "result.json"
            env = {**os.environ, "MODECALC_SETTINGS_DIR": str(work),
                   "MODECALC_LOG": str(work / "ModeCalc.log"),
                   "MODECALC_SMOKE_RESULT": str(result_file),
                   "MODECALC_SMOKE_MIDI_PORT": port}
            # Deliberately launch from an unrelated directory and remove Python
            # and dynamic-loader overrides to expose accidental host dependencies.
            for key in ("PYTHONPATH", "PYTHONHOME", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH"):
                env.pop(key, None)
            command = [str(executable), "--smoke-test"]
            requested_arch = os.environ.get("MODECALC_SMOKE_ARCH")
            if requested_arch:
                if requested_arch not in ("arm64", "x86_64"):
                    raise ValueError("MODECALC_SMOKE_ARCH must be arm64 or x86_64")
                command = ["/usr/bin/arch", "-" + requested_arch, *command]
            process = subprocess.Popen(command, cwd=work, env=env)
            try:
                deadline = time.monotonic() + 40
                while process.poll() is None and time.monotonic() < deadline:
                    for note in (60, 64, 67):
                        output.send_message([0x90, note, 100])
                    time.sleep(0.05)
                if process.poll() is None:
                    raise RuntimeError("App did not exit after smoke test")
                if not result_file.exists():
                    raise RuntimeError(f"App exited without diagnostics (code {process.returncode})")
                result = json.loads(result_file.read_text())
                if not result.get("ok") or not result.get("real_midi_input"):
                    raise RuntimeError(json.dumps(result, ensure_ascii=False))
                if requested_arch and result.get("runtime_architecture") != requested_arch:
                    raise RuntimeError(f"Unexpected runtime architecture: {result}")
                print(json.dumps(result, ensure_ascii=False, indent=2))
            except Exception:
                if (work / "ModeCalc.log").exists():
                    print((work / "ModeCalc.log").read_text(), file=sys.stderr)
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                if os.environ.get("MODECALC_SMOKE_DIAGNOSTICS"):
                    diagnostics = Path(os.environ["MODECALC_SMOKE_DIAGNOSTICS"])
                    diagnostics.mkdir(parents=True, exist_ok=True)
                    for file in (result_file, work / "ModeCalc.log"):
                        if file.exists():
                            shutil.copy2(file, diagnostics / file.name)
    finally:
        output.close_port()


if __name__ == "__main__":
    main()
