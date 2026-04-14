from __future__ import annotations

import logging
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

log = logging.getLogger("controller")


class AppController:
    def __init__(self, app: App) -> None:
        self.app = app
        self.device_manager = DeviceManager()
        self.img_process = ImgProcessing(self)
        self.solver = WordBoxSolver()

    # ── Language ────────────────────────────────────────────────────

    def set_language(self, language: str) -> None:
        log.debug("set_language(%s)", language)
        self.solver.set_language(language)

    def set_min_word_length(self, length: int) -> None:
        log.debug("set_min_word_length(%d)", length)
        self.solver.set_min_word_length(length)

    # ── Scan game ───────────────────────────────────────────────────

    def set_game(self) -> None:
        grid = self.app.grid_widget
        settings = self.app.settings
        hwnd = self.app.get_mirror_hwnd()

        if not hwnd or self.app.is_solving:
            log.warning("set_game() — skipped (hwnd=%s, is_solving=%s)", hwnd, self.app.is_solving)
            return

        log.info("set_game() — starting scan")

        def destroy_grid() -> None:
            if not grid or not grid.frame:
                return
            grid.frame.destroy()
            grid.set_inner_frame_text("Scanning…")
            settings.disable_scan_window_btn()
            grid.create_grid_frame()

        def task() -> None:
            try:
                self.app.after(0, destroy_grid)
                self.img_process.pipeline()
                self.solver.set_cell_positions(self.img_process.contour_info_grid)
                log.info("set_game() — scan complete, grid=%dx%s",
                         len(self.img_process.contour_info_grid),
                         len(self.img_process.contour_info_grid[0]) if self.img_process.contour_info_grid else 0)
                self.app.after(0, update_ui)
            except Exception:
                log.exception("set_game() — task crashed")
                self.app.is_scanning = False
                self.app.after(0, on_error)

        def on_error() -> None:
            if settings:
                settings.enable_scan_window_btn()
            if grid and grid.inner_frame_label:
                grid.inner_frame_label.configure(text="Scan failed — check logs")

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
        solver = self.solver
        total_words = len(solver.found_words)
        log.info("_automate() — starting, %d words to play", total_words)

        fav = (self.app.grid_widget.favorite_cell
               if self.app.grid_widget else None)
        log.info("_automate() — favorite_cell=%s", fav)

        # Pre-compute total expected score
        summary = solver.compute_score_summary(fav)
        total_expected = summary["total_points"]
        log.info("_automate() — expected total: %d pts (%d words, %d bonus)",
                 total_expected, summary["total_words"], summary["bonus_words"])

        # Show score summary in settings panel
        self.app.after(0, lambda: settings.show_score_summary(summary))

        def on_press(key: keyboard.Key) -> bool | None:
            try:
                if key == keyboard.Key.esc:
                    log.info("_automate() — ESC pressed, stopping")
                    self.app.is_solving = False
                    return False
                if key == keyboard.Key.space:
                    self.app.is_paused = not self.app.is_paused
                    log.info("_automate() — paused=%s", self.app.is_paused)
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

        # Sort: highest points first, fewest path cells to break ties
        sorted_words = sorted(
            solver.found_words.items(),
            key=lambda x: (
                -(solver.word_points(x[0][0])
                  + (3 if solver.path_uses_cell(x[1], fav) else 0)),
                len(x[1]),
            ),
        )

        use_adb = (settings.get_input_mode() == "ADB"
                    and self.device_manager.adb_input
                    and self.device_manager.adb_input.status()[0])
        log.info("_automate() — use_adb=%s, word_count=%d", use_adb, len(sorted_words))

        earned = 0
        played = 0

        for (word, _), path in sorted_words:
            if not self.app.is_solving:
                self.app.is_paused = False
                break

            base = solver.word_points(word)
            bonus = 3 if solver.path_uses_cell(path, fav) else 0
            pts = base + bonus
            earned += pts
            played += 1

            log.info("_automate() — [%d/%d] '%s' +%d pts (total %d/%d)",
                     played, total_words, word, pts, earned, total_expected)

            # Update progress bar
            self.app.after(0, lambda p=played, e=earned: settings.update_progress(
                p, total_words, e, total_expected))

            if use_adb:
                points = []
                for py, px in path:
                    pos_x, pos_y = solver.cell_window_positions[py][px]
                    points.append((pos_x, pos_y))
                self.device_manager.adb_input.swipe_path(
                    points,
                    self.img_process.window_width,
                    self.img_process.window_height,
                )
                speed = settings.get_speed() if settings else 0.8
                time.sleep(max(0.08, 0.4 * (1.0 - speed)))
            else:
                y, x = path[0]
                pos_x, pos_y = solver.cell_window_positions[y][x]

                pyautogui.moveTo(
                    self.img_process.window_left + pos_x,
                    self.img_process.window_top + pos_y,
                )
                pyautogui.mouseDown(button="left")

                for i in range(1, len(path)):
                    y, x = path[i]
                    pos_x, pos_y = solver.cell_window_positions[y][x]
                    mov_x = self.img_process.window_left + pos_x
                    mov_y = self.img_process.window_top + pos_y

                    speed = settings.get_speed() if settings else 0.8
                    pyautogui.moveTo(mov_x, mov_y, uniform(0, 1.0 - speed))

                pyautogui.mouseUp(button="left")

            while self.app.is_paused and self.app.is_solving:
                time.sleep(0.1)

        self.app.is_solving = False
        self.app.is_paused = False
        # Final update
        self.app.after(0, lambda: settings.update_progress(
            played, total_words, earned, total_expected, done=True))
        log.info("_automate() — finished: played %d/%d words, %d/%d pts",
                 played, total_words, earned, total_expected)

    # ── Solve ───────────────────────────────────────────────────────

    def solve_game(self) -> None:
        grid = self.app.grid_widget
        settings = self.app.settings
        if not grid or not grid.frame or not settings:
            log.warning("solve_game() — skipped (missing grid/settings)")
            return

        log.info("solve_game() — starting")

        def after_solving() -> None:
            if self.app.state_label:
                self.app.state_label.destroy()
            settings.enable_solve_btn()
            settings.enable_scan_window_btn()

        def task() -> None:
            try:
                letter_grid = grid.extract_letters()
                if not grid.is_valid():
                    log.warning("solve_game() — grid not valid, aborting")
                    return

                log.debug("solve_game() — grid: %s", letter_grid)
                self.solver.set_letter_grid(letter_grid)
                self.solver.solve()
                log.info("solve_game() — solver found %d words", len(self.solver.found_words))

                hwnd = self.app.get_mirror_hwnd()
                if not hwnd:
                    log.warning("solve_game() — mirror hwnd gone, aborting")
                    return

                self.app.after(0, lambda: self.app.create_state_label(row=0, col=0))
                self.app.after(0, settings.disable_solve_btn)
                self.app.after(0, settings.disable_scan_window_btn)

                if not settings or settings.get_input_mode() != "ADB":
                    self.solver.set_screen_front(hwnd)
                self._automate()

                self.app.after(0, after_solving)
            except Exception:
                log.exception("solve_game() — task crashed")
                self.app.is_solving = False
                self.app.is_paused = False
                self.app.after(0, after_solving)

        threading.Thread(target=task, daemon=True).start()
