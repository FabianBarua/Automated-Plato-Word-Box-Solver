from __future__ import annotations

import math
import threading
import time
from random import uniform
from typing import TYPE_CHECKING

import pyautogui
from pynput import keyboard

from core.device_manager import DeviceManager
from core.img_processing import ImgProcessing
from core.solver import WordBoxSolver

if TYPE_CHECKING:
    from ui.app import App


class AppController:
    def __init__(self, app: App) -> None:
        self.app = app
        self.device_manager = DeviceManager()
        self.img_process = ImgProcessing(self)
        self.solver = WordBoxSolver()

    # ── Language ────────────────────────────────────────────────────

    def set_language(self, language: str) -> None:
        self.solver.set_language(language)

    def set_min_word_length(self, length: int) -> None:
        self.solver.set_min_word_length(length)

    # ── Scan game ───────────────────────────────────────────────────

    def set_game(self) -> None:
        grid = self.app.grid_widget
        settings = self.app.settings
        hwnd = self.app.get_mirror_hwnd()

        if not hwnd or self.app.is_solving:
            return

        def destroy_grid() -> None:
            if not grid or not grid.frame:
                return
            grid.frame.destroy()
            grid.set_inner_frame_text("Scanning…")
            settings.disable_scan_window_btn()
            grid.create_grid_frame()

        def task() -> None:
            self.app.after(0, destroy_grid)
            self.img_process.pipeline()
            self.solver.set_cell_positions(self.img_process.contour_info_grid)
            self.app.after(0, update_ui)

        def update_ui() -> None:
            settings.enable_scan_window_btn()
            if not grid or not grid.frame or not grid.inner_frame:
                return

            rows = len(self.img_process.contour_info_grid)
            cols = 0 if rows == 0 else len(self.img_process.contour_info_grid[0])
            grid.set_grid_row_col_size(rows, cols)

            if grid.grid_row_size > 1 and grid.grid_col_size > 1:
                grid.inner_frame_label.configure(text="")
                grid.fill_grid()
            else:
                grid.inner_frame_label.configure(text="No Grid Found")

        threading.Thread(target=task, daemon=True).start()

    # ── Automation ──────────────────────────────────────────────────

    def _automate(self) -> None:
        settings = self.app.settings

        def on_press(key: keyboard.Key) -> bool | None:
            try:
                if key == keyboard.Key.esc:
                    self.app.is_solving = False
                    return False
                if key == keyboard.Key.space:
                    self.app.is_paused = not self.app.is_paused
                    style = (
                        self.app.state_label_paused_style
                        if self.app.is_paused
                        else self.app.state_label_solving_style
                    )
                    self.app.after(0, lambda: self.app.state_label.configure(**style))
            except AttributeError:
                pass
            return None

        listener = keyboard.Listener(on_press=on_press)
        listener.start()

        self.app.is_solving = True

        def path_distance(path: list[list[int]]) -> float:
            total = 0.0
            for i in range(len(path) - 1):
                x1, y1 = path[i]
                x2, y2 = path[i + 1]
                total += math.hypot(x1 - x2, y1 - y2)
            return total

        sorted_words = sorted(
            self.solver.found_words.items(),
            key=lambda x: path_distance(x[1]),
            reverse=True,
        )

        use_adb = (settings.get_input_mode() == "ADB"
                    and self.device_manager.adb_input
                    and self.device_manager.adb_input.status()[0])

        for (_, _), path in sorted_words:
            if not self.app.is_solving:
                self.app.is_paused = False
                break

            if use_adb:
                points = []
                for py, px in path:
                    pos_x, pos_y = self.solver.cell_window_positions[py][px]
                    points.append((pos_x, pos_y))
                self.device_manager.adb_input.swipe_path(
                    points,
                    self.img_process.window_width,
                    self.img_process.window_height,
                )
            else:
                y, x = path[0]
                pos_x, pos_y = self.solver.cell_window_positions[y][x]

                pyautogui.moveTo(
                    self.img_process.window_left + pos_x,
                    self.img_process.window_top + pos_y,
                )
                pyautogui.mouseDown(button="left")

                for i in range(1, len(path)):
                    y, x = path[i]
                    pos_x, pos_y = self.solver.cell_window_positions[y][x]
                    mov_x = self.img_process.window_left + pos_x
                    mov_y = self.img_process.window_top + pos_y

                    speed = settings.get_speed() if settings else 0.8
                    pyautogui.moveTo(mov_x, mov_y, uniform(0, 1.0 - speed))

                pyautogui.mouseUp(button="left")

            while self.app.is_paused and self.app.is_solving:
                time.sleep(0.1)

        self.app.is_solving = False
        self.app.is_paused = False

    # ── Solve ───────────────────────────────────────────────────────

    def solve_game(self) -> None:
        grid = self.app.grid_widget
        settings = self.app.settings
        if not grid or not grid.frame or not settings:
            return

        def after_solving() -> None:
            if self.app.state_label:
                self.app.state_label.destroy()
            settings.enable_solve_btn()
            settings.enable_scan_window_btn()

        def task() -> None:
            letter_grid = grid.extract_letters()
            if not grid.is_valid():
                return

            self.solver.set_letter_grid(letter_grid)
            self.solver.solve()

            hwnd = self.app.get_mirror_hwnd()
            if not hwnd:
                return

            # UI updates — pass callbacks (no parentheses!)
            self.app.after(0, lambda: self.app.create_state_label(row=0, col=0))
            self.app.after(0, settings.disable_solve_btn)
            self.app.after(0, settings.disable_scan_window_btn)

            if not settings or settings.get_input_mode() != "ADB":
                self.solver.set_screen_front(hwnd)
            self._automate()

            self.app.after(0, after_solving)

        threading.Thread(target=task, daemon=True).start()
