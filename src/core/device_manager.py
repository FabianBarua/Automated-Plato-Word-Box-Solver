import logging
import shutil
import subprocess
import time
from pathlib import Path

import win32gui

from core.paths import TOOLS_DIR

log = logging.getLogger("device_manager")


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
        self.device_serial: str | None = None
        self.adb_input: ADBInput | None = None
        log.debug("DeviceManager init — adb=%s, scrcpy=%s", self.adb_path, self.scrcpy_path)

    # ── ADB device enumeration ──────────────────────────────────────

    def get_connected_devices(self) -> list[dict[str, str]]:
        """
        Returns a list of dicts with 'serial' and 'label' keys.
        Starts the adb server if needed, then queries for attached devices.
        """
        log.debug("get_connected_devices() — starting adb server")
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
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            log.warning("get_connected_devices() failed: %s", e)
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
        log.info("get_connected_devices() found %d device(s): %s",
                 len(devices), [d["serial"] for d in devices])
        return devices

    # ── scrcpy lifecycle ────────────────────────────────────────────

    def launch_scrcpy(self, device_serial: str) -> bool:
        """Launch scrcpy for the given device. Returns True on success."""
        # Skip restart if already connected to the same device and healthy
        if (self.device_serial == device_serial
                and self.scrcpy_process is not None
                and self.scrcpy_process.poll() is None
                and self.get_window_handle()):
            log.info("launch_scrcpy() — already connected to %s, skipping restart", device_serial)
            return True

        log.info("launch_scrcpy() — starting for device %s", device_serial)
        self.stop_scrcpy()
        self.device_serial = device_serial

        if not self.scrcpy_path.exists():
            log.error("launch_scrcpy() — scrcpy binary not found: %s", self.scrcpy_path)
            return False

        try:
            self.scrcpy_process = subprocess.Popen(
                [
                    str(self.scrcpy_path),
                    "-s", device_serial,
                    f"--window-title={self.SCRCPY_WINDOW_TITLE}",
                ],
                creationflags=subprocess.DETACHED_PROCESS,
                stderr=subprocess.PIPE,
            )
            log.debug("launch_scrcpy() — process spawned, pid=%d", self.scrcpy_process.pid)
        except FileNotFoundError as e:
            log.error("launch_scrcpy() — FileNotFoundError: %s", e)
            return False

        # Wait for the scrcpy window to actually appear (up to 8s)
        if not self._wait_for_scrcpy_window(timeout=8.0, interval=0.4):
            log.error("launch_scrcpy() — scrcpy window never appeared, killing process")
            self._read_scrcpy_stderr()
            self.stop_scrcpy()
            return False

        log.info("launch_scrcpy() — scrcpy window appeared, hwnd=%d", self.get_window_handle())
        return True

    def _wait_for_scrcpy_window(self, timeout: float = 8.0, interval: float = 0.4) -> bool:
        """Poll for the scrcpy window handle until it appears or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.scrcpy_process and self.scrcpy_process.poll() is not None:
                log.warning("_wait_for_scrcpy_window() — process exited early (code=%s)",
                            self.scrcpy_process.returncode)
                return False
            if self.get_window_handle():
                return True
            time.sleep(interval)
        return False

    def _read_scrcpy_stderr(self) -> None:
        """Read and log any stderr output from scrcpy (non-blocking)."""
        if not self.scrcpy_process or not self.scrcpy_process.stderr:
            return
        try:
            stderr_data = self.scrcpy_process.stderr.read(4096)
            if stderr_data:
                log.error("scrcpy stderr: %s", stderr_data.decode(errors="replace").strip())
        except Exception:
            pass

    def stop_scrcpy(self) -> None:
        log.info("stop_scrcpy() — cleaning up")
        if self.adb_input:
            self.adb_input.close()
            self.adb_input = None
        self.device_serial = None
        if self.scrcpy_process and self.scrcpy_process.poll() is None:
            log.debug("stop_scrcpy() — terminating pid=%d", self.scrcpy_process.pid)
            self.scrcpy_process.terminate()
            try:
                self.scrcpy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log.warning("stop_scrcpy() — force killing pid=%d", self.scrcpy_process.pid)
                self.scrcpy_process.kill()
        self.scrcpy_process = None

    def is_scrcpy_running(self) -> bool:
        process_alive = self.scrcpy_process is not None and self.scrcpy_process.poll() is None
        window_exists = self.get_window_handle() != 0
        running = process_alive and window_exists
        if process_alive and not window_exists:
            log.warning("is_scrcpy_running() — process alive but window gone")
        return running

    # ── Window handle ───────────────────────────────────────────────

    def get_window_handle(self) -> int:
        """Return the HWND for the scrcpy mirror window, or 0 if not found."""
        hwnd = win32gui.FindWindow(None, self.SCRCPY_WINDOW_TITLE)
        return hwnd

    def setup_adb_input(self) -> tuple[bool, str]:
        """Initialize ADB direct input. Returns (success, status_message)."""
        if not self.device_serial:
            log.warning("setup_adb_input() — no device serial")
            return False, "No device connected"
        try:
            log.debug("setup_adb_input() — creating ADBInput for %s", self.device_serial)
            self.adb_input = ADBInput(self.adb_path, self.device_serial)
            ready, msg = self.adb_input.status()
            if not ready:
                self.adb_input = None
            log.info("setup_adb_input() — ready=%s, msg=%s", ready, msg)
            return ready, msg
        except Exception as e:
            log.error("setup_adb_input() — exception: %s", e, exc_info=True)
            self.adb_input = None
            return False, f"Error: {e}"


class ADBInput:
    """Sends touch events directly to Android via ADB."""

    # sendevent numeric codes
    _EV_SYN = 0
    _EV_KEY = 1
    _EV_ABS = 3
    _SYN_REPORT = 0
    _SYN_MT_REPORT = 2
    _BTN_TOUCH = 330
    _ABS_MT_SLOT = 0x2F          # 47
    _ABS_MT_TOUCH_MAJOR = 0x30   # 48
    _ABS_MT_POSITION_X = 0x35    # 53
    _ABS_MT_POSITION_Y = 0x36    # 54
    _ABS_MT_TRACKING_ID = 0x39   # 57
    _ABS_MT_PRESSURE = 0x3A      # 58

    def __init__(self, adb_path: str, device_serial: str) -> None:
        self.adb_path = adb_path
        self.serial = device_serial
        self.event_device: str | None = None
        self.touch_max_x: int = 0
        self.touch_max_y: int = 0
        self.has_pressure: bool = False
        self.has_touch_major: bool = False
        self.has_slot: bool = False
        self.screen_w: int = 0
        self.screen_h: int = 0
        self._shell: subprocess.Popen | None = None
        self._use_input_fallback: bool = False

        self._detect_input_device()
        self._detect_screen_size()

        # If sendevent detection failed, mark fallback mode
        if not self.event_device and self.screen_w and self.screen_h:
            self._use_input_fallback = True

    def status(self) -> tuple[bool, str]:
        if self.event_device and self.screen_w and self.screen_h:
            return True, (
                f"ADB Ready — {self.event_device} "
                f"({self.touch_max_x}×{self.touch_max_y}) "
                f"Screen {self.screen_w}×{self.screen_h}"
            )
        if self._use_input_fallback:
            return True, f"ADB Ready (fallback) — Screen {self.screen_w}×{self.screen_h}"
        parts = []
        if not self.event_device:
            parts.append("touch device not found")
        if not self.screen_w:
            parts.append("screen size unknown")
        return False, "ADB Failed: " + ", ".join(parts)

    def _run_adb(self, *args) -> str:
        try:
            result = subprocess.run(
                [self.adb_path, '-s', self.serial] + list(args),
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return ""

    def _detect_input_device(self) -> None:
        output = self._run_adb('shell', 'getevent', '-pl')
        if not output.strip():
            output = self._run_adb('shell', 'getevent', '-p')

        current_device = None
        found_x_device = None

        for line in output.splitlines():
            stripped = line.strip()

            # Detect device path — handle both "add device N: /dev/..." and indented names
            if 'add device' in stripped:
                # e.g. "add device 1: /dev/input/event3"
                colon_idx = stripped.find('/dev/')
                if colon_idx >= 0:
                    current_device = stripped[colon_idx:].split()[0].strip()
                else:
                    parts = stripped.split(':')
                    if len(parts) >= 2:
                        candidate = parts[-1].strip()
                        if candidate.startswith('/dev/'):
                            current_device = candidate

            if not current_device:
                continue

            # Look for ABS_MT_POSITION_X (labeled or hex 0035)
            if 'ABS_MT_POSITION_X' in stripped or '0035' in stripped:
                if 'ABS_MT_POSITION_X' in stripped or ('0035' in stripped and 'max' in stripped):
                    found_x_device = current_device
                    self.event_device = current_device
                    self._parse_max_value(stripped, 'x')

            # ABS_MT_POSITION_Y
            if current_device == found_x_device:
                if 'ABS_MT_POSITION_Y' in stripped or ('0036' in stripped and 'max' in stripped):
                    self._parse_max_value(stripped, 'y')
                if 'ABS_MT_PRESSURE' in stripped or '003a' in stripped:
                    self.has_pressure = True
                if 'ABS_MT_TOUCH_MAJOR' in stripped or '0030' in stripped:
                    self.has_touch_major = True
                if 'ABS_MT_SLOT' in stripped or '002f' in stripped:
                    self.has_slot = True

    def _parse_max_value(self, line: str, axis: str) -> None:
        for part in line.split(','):
            p = part.strip()
            if p.startswith('max'):
                try:
                    val = int(p.split()[-1])
                    if axis == 'x':
                        self.touch_max_x = val
                    else:
                        self.touch_max_y = val
                except ValueError:
                    pass

    def _detect_screen_size(self) -> None:
        output = self._run_adb('shell', 'wm', 'size')
        for line in output.splitlines():
            if 'Override size' in line or 'Physical size' in line:
                try:
                    size_str = line.split(':')[1].strip()
                    w, h = size_str.split('x')
                    self.screen_w, self.screen_h = int(w), int(h)
                except (ValueError, IndexError):
                    pass
                if 'Override size' in line:
                    break

    def _to_screen_coords(self, win_x: int, win_y: int, window_w: int, window_h: int):
        """Map scrcpy window pixel coordinates to device screen pixel coordinates."""
        if not window_w or not window_h:
            return 0, 0
        return (
            int(win_x * self.screen_w / window_w),
            int(win_y * self.screen_h / window_h),
        )

    def _to_touch_coords(self, win_x: int, win_y: int, window_w: int, window_h: int):
        """Map scrcpy window pixel coordinates to raw touch panel coordinates."""
        sx, sy = self._to_screen_coords(win_x, win_y, window_w, window_h)
        if self.touch_max_x and self.screen_w:
            tx = int(sx * self.touch_max_x / self.screen_w)
        else:
            tx = sx
        if self.touch_max_y and self.screen_h:
            ty = int(sy * self.touch_max_y / self.screen_h)
        else:
            ty = sy
        return tx, ty

    def _ensure_shell(self) -> None:
        if self._shell is None or self._shell.poll() is not None:
            self._shell = subprocess.Popen(
                [self.adb_path, '-s', self.serial, 'shell'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

    def _send_shell(self, cmd: str) -> None:
        self._ensure_shell()
        try:
            self._shell.stdin.write(cmd.encode())
            self._shell.stdin.flush()
        except (BrokenPipeError, OSError):
            self._shell = None
            self._ensure_shell()
            try:
                self._shell.stdin.write(cmd.encode())
                self._shell.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def swipe_path(self, points: list[tuple[int, int]], window_w: int, window_h: int) -> None:
        """Execute a multi-point swipe gesture via ADB."""
        if not points:
            return
        log.debug("swipe_path() — %d points, window=%dx%d, fallback=%s",
                  len(points), window_w, window_h, self._use_input_fallback)

        if self._use_input_fallback:
            self._swipe_path_input(points, window_w, window_h)
        else:
            self._swipe_path_sendevent(points, window_w, window_h)

    def _swipe_path_sendevent(self, points: list[tuple[int, int]], window_w: int, window_h: int) -> None:
        dev = self.event_device
        if not dev:
            return

        def se(evtype, code, value):
            return f"sendevent {dev} {evtype} {code} {value}"

        # Touch DOWN at first point
        tx, ty = self._to_touch_coords(points[0][0], points[0][1], window_w, window_h)
        down = []
        if self.has_slot:
            down.append(se(self._EV_ABS, self._ABS_MT_SLOT, 0))
        down.append(se(self._EV_ABS, self._ABS_MT_TRACKING_ID, 0))
        down.append(se(self._EV_ABS, self._ABS_MT_POSITION_X, tx))
        down.append(se(self._EV_ABS, self._ABS_MT_POSITION_Y, ty))
        if self.has_touch_major:
            down.append(se(self._EV_ABS, self._ABS_MT_TOUCH_MAJOR, 6))
        if self.has_pressure:
            down.append(se(self._EV_ABS, self._ABS_MT_PRESSURE, 50))
        down.append(se(self._EV_KEY, self._BTN_TOUCH, 1))
        down.append(se(self._EV_SYN, self._SYN_MT_REPORT, 0))
        down.append(se(self._EV_SYN, self._SYN_REPORT, 0))
        self._send_shell(";".join(down) + "\n")

        # MOVE through remaining points with delay between each
        for px, py in points[1:]:
            time.sleep(0.015)
            tx, ty = self._to_touch_coords(px, py, window_w, window_h)
            move = [
                se(self._EV_ABS, self._ABS_MT_POSITION_X, tx),
                se(self._EV_ABS, self._ABS_MT_POSITION_Y, ty),
            ]
            if self.has_pressure:
                move.append(se(self._EV_ABS, self._ABS_MT_PRESSURE, 50))
            move.append(se(self._EV_SYN, self._SYN_MT_REPORT, 0))
            move.append(se(self._EV_SYN, self._SYN_REPORT, 0))
            self._send_shell(";".join(move) + "\n")

        # Touch UP
        time.sleep(0.01)
        up = [
            se(self._EV_ABS, self._ABS_MT_TRACKING_ID, 4294967295),
            se(self._EV_KEY, self._BTN_TOUCH, 0),
            se(self._EV_SYN, self._SYN_MT_REPORT, 0),
            se(self._EV_SYN, self._SYN_REPORT, 0),
        ]
        self._send_shell(";".join(up) + "\n")

    def _swipe_path_input(self, points: list[tuple[int, int]], window_w: int, window_h: int) -> None:
        """Fallback: chain 'input swipe' for each segment. Not perfectly continuous."""
        if len(points) < 2:
            sx, sy = self._to_screen_coords(points[0][0], points[0][1], window_w, window_h)
            self._send_shell(f"input tap {sx} {sy}\n")
            return

        cmds = []
        for i in range(len(points) - 1):
            x1, y1 = self._to_screen_coords(points[i][0], points[i][1], window_w, window_h)
            x2, y2 = self._to_screen_coords(points[i + 1][0], points[i + 1][1], window_w, window_h)
            cmds.append(f"input swipe {x1} {y1} {x2} {y2} 40")

        self._send_shell(" && ".join(cmds) + "\n")

    def close(self) -> None:
        if self._shell and self._shell.poll() is None:
            self._shell.terminate()
            try:
                self._shell.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._shell.kill()
        self._shell = None
