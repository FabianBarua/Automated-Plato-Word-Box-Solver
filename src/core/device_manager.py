import shutil
import subprocess
from pathlib import Path

import win32gui

from core.paths import TOOLS_DIR


def _find_adb(tools_dir: Path) -> str:
    """Return the best available adb path: bundled first, then system PATH."""
    bundled = tools_dir / "scrcpy" / "adb.exe"
    if bundled.exists():
        return str(bundled)
    system_adb = shutil.which("adb")
    if system_adb:
        return system_adb
    return str(bundled)  # will fail gracefully later


class DeviceManager:
    SCRCPY_WINDOW_TITLE = "WordBoxSolver_Mirror"

    def __init__(self, tools_dir: Path | None = None) -> None:
        tools = tools_dir or TOOLS_DIR
        self.adb_path = _find_adb(tools)
        self.scrcpy_path = tools / "scrcpy" / "scrcpy.exe"
        self.scrcpy_process: subprocess.Popen | None = None

    # ── ADB device enumeration ──────────────────────────────────────

    def get_connected_devices(self) -> list[dict[str, str]]:
        """
        Returns a list of dicts with 'serial' and 'label' keys.
        Starts the adb server if needed, then queries for attached devices.
        """
        try:
            # Ensure adb server is running
            subprocess.run(
                [self.adb_path, "start-server"],
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            result = subprocess.run(
                [self.adb_path, "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []

        devices: list[dict[str, str]] = []
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                model = ""
                for part in parts[2:]:
                    if part.startswith("model:"):
                        model = part.split(":", 1)[1]
                        break
                label = f"{model} ({serial})" if model else serial
                devices.append({"serial": serial, "label": label})
        return devices

    # ── scrcpy lifecycle ────────────────────────────────────────────

    def launch_scrcpy(self, device_serial: str) -> bool:
        """Launch scrcpy for the given device. Returns True on success."""
        self.stop_scrcpy()

        if not self.scrcpy_path.exists():
            return False

        try:
            # DETACHED_PROCESS hides the console but still allows scrcpy's SDL
            # video window to appear (CREATE_NO_WINDOW would suppress it).
            self.scrcpy_process = subprocess.Popen(
                [
                    str(self.scrcpy_path),
                    "-s", device_serial,
                    f"--window-title={self.SCRCPY_WINDOW_TITLE}",
                ],
                creationflags=subprocess.DETACHED_PROCESS,
            )
            return True
        except FileNotFoundError:
            return False

    def stop_scrcpy(self) -> None:
        if self.scrcpy_process and self.scrcpy_process.poll() is None:
            self.scrcpy_process.terminate()
            try:
                self.scrcpy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.scrcpy_process.kill()
        self.scrcpy_process = None

    def is_scrcpy_running(self) -> bool:
        return self.scrcpy_process is not None and self.scrcpy_process.poll() is None

    # ── Window handle ───────────────────────────────────────────────

    def get_window_handle(self) -> int:
        """Return the HWND for the scrcpy mirror window, or 0 if not found."""
        return win32gui.FindWindow(None, self.SCRCPY_WINDOW_TITLE)
