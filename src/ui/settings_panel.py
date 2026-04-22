from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.solver import LANG_MAP

if TYPE_CHECKING:
    from ui.app import App

log = logging.getLogger("settings_panel")


class SettingsPanel:
    """Fixed-width sidebar: device, language, speed, and action controls."""

    def __init__(self, master: ctk.CTkFrame, app: App) -> None:
        self.app = app
        self.color = app.color
        self.device_manager = app.controller.device_manager

        self.solve_btn: ctk.CTkButton | None = None
        self.scan_window_btn: ctk.CTkButton | None = None
        self.connect_btn: ctk.CTkButton | None = None
        self.device_combo: ctk.CTkComboBox | None = None
        self.status_label: ctk.CTkLabel | None = None
        self.speed_slider: ctk.CTkSlider | None = None
        self.speed_value_label: ctk.CTkLabel | None = None
        self.min_word_length_slider: ctk.CTkSlider | None = None
        self.max_word_length_slider: ctk.CTkSlider | None = None
        self.order_menu: ctk.CTkOptionMenu | None = None
        self.max_words_slider: ctk.CTkSlider | None = None
        self.max_words_value_label: ctk.CTkLabel | None = None
        self.human_mode_seg: ctk.CTkSegmentedButton | None = None
        self.jitter_slider: ctk.CTkSlider | None = None
        self.pause_slider: ctk.CTkSlider | None = None
        self.input_mode_seg: ctk.CTkSegmentedButton | None = None

        # Score / progress widgets
        self._score_frame: ctk.CTkFrame | None = None
        self._score_total_label: ctk.CTkLabel | None = None
        self._score_breakdown_label: ctk.CTkLabel | None = None
        self._progress_bar: ctk.CTkProgressBar | None = None
        self._progress_label: ctk.CTkLabel | None = None

        self._devices: list[dict[str, str]] = []

        c = self.color

        # ── Scrollable content fills the sidebar ────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            master,
            fg_color=c.surface,
            scrollbar_button_color=c.border,
            scrollbar_button_hover_color=c.border_hi,
            corner_radius=0,
        )
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self._scroll.grid_columnconfigure(0, weight=1)

        # ── Sections ────────────────────────────────────────────────
        self._create_device_section(row=0)
        self._create_divider(row=2)
        self._create_language_section(row=3)
        self._create_divider(row=5)
        self._create_word_length_section(row=6)
        self._create_divider(row=8)
        self._create_order_section(row=9)
        self._create_divider(row=11)
        self._create_max_words_section(row=12)
        self._create_divider(row=14)
        self._create_speed_section(row=15)
        self._create_divider(row=17)
        self._create_human_mode_section(row=18)
        self._create_divider(row=20)
        self._create_input_mode_section(row=21)
        self._create_action_section(row=23)
        self._create_score_section(row=25)
        self._create_credits_section(row=27)

    # ── Layout helpers ───────────────────────────────────────────────

    def _section_header(
        self,
        row: int,
        title: str,
        btn_text: str | None = None,
        btn_cmd=None,
    ) -> None:
        """Renders a small-caps section label with an optional inline action button."""
        c = self.color
        frame = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=0)
        frame.grid(row=row, column=0, sticky="nsew", padx=16, pady=(16, 4))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont("Poppins Medium", size=10),
            text_color=c.subtext,
            fg_color="transparent",
            anchor="w",
        ).grid(row=0, column=0, sticky="nsew")

        if btn_text and btn_cmd:
            ctk.CTkButton(
                frame,
                text=btn_text,
                command=btn_cmd,
                width=26,
                height=20,
                corner_radius=4,
                fg_color=c.surface_hi,
                text_color=c.subtext,
                hover_color=c.border_hi,
                font=ctk.CTkFont("Poppins Medium", size=12),
            ).grid(row=0, column=1, sticky="e")

    def _section_body(self, row: int) -> ctk.CTkFrame:
        """Transparent frame that contains a section's widgets."""
        frame = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=0)
        frame.grid(row=row, column=0, sticky="nsew", padx=16, pady=(0, 4))
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _create_divider(self, row: int) -> None:
        ctk.CTkFrame(
            self._scroll,
            height=1,
            fg_color=self.color.border,
            corner_radius=0,
        ).grid(row=row, column=0, sticky="ew", padx=16, pady=(8, 0))

    # ── Reusable: labeled integer slider ───────────────────────────

    def _make_slider_row(
        self,
        parent: ctk.CTkFrame,
        row: int,
        label_text: str,
        from_: int,
        to: int,
        initial: int,
        format_value=lambda v: str(v),
        on_change=None,
    ) -> tuple[ctk.CTkSlider, ctk.CTkLabel]:
        """A small label + value-on-the-right + slider. Returns (slider, value_label)."""
        c = self.color
        head = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        head.grid(row=row, column=0, sticky="ew", pady=(0, 2))
        head.grid_columnconfigure(0, weight=1)
        head.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            head, text=label_text,
            font=ctk.CTkFont("Poppins Medium", size=10),
            text_color=c.subtext, fg_color="transparent", anchor="w",
        ).grid(row=0, column=0, sticky="w")

        value_label = ctk.CTkLabel(
            head, text=format_value(initial),
            font=ctk.CTkFont("Poppins Medium", size=11),
            text_color=c.primary, fg_color="transparent", anchor="e",
        )
        value_label.grid(row=0, column=1, sticky="e")

        steps = max(1, to - from_)

        def _on_slide(v: float) -> None:
            iv = int(round(v))
            value_label.configure(text=format_value(iv))
            if on_change:
                on_change(iv)

        slider = ctk.CTkSlider(
            parent, from_=from_, to=to, number_of_steps=steps,
            command=_on_slide,
            progress_color=c.primary,
            button_color=c.primary,
            button_hover_color=c.primary_hover,
            fg_color=c.surface_hi,
            height=14,
        )
        slider.set(initial)
        slider.grid(row=row + 1, column=0, sticky="ew", pady=(0, 8))
        return slider, value_label

    # ── Device ───────────────────────────────────────────────────────

    def _create_device_section(self, row: int) -> None:
        c = self.color
        self._section_header(row, "DEVICE", "↻", self._on_refresh_devices)

        body = self._section_body(row + 1)

        self.device_combo = ctk.CTkComboBox(
            body,
            values=["No devices"],
            state="readonly",
            font=ctk.CTkFont("Poppins Medium", size=13),
            dropdown_font=ctk.CTkFont("Poppins Medium", size=13),
            fg_color=c.surface_hi,
            border_color=c.border,
            border_width=1,
            button_color=c.border,
            button_hover_color=c.primary,
            text_color=c.text,
            dropdown_fg_color=c.surface_hi,
            dropdown_text_color=c.text,
            dropdown_hover_color=c.border_hi,
            corner_radius=6,
            height=36,
        )
        self.device_combo.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        self.connect_btn = ctk.CTkButton(
            body,
            text="Connect",
            command=self._on_connect_toggle,
            height=40,
            corner_radius=6,
            fg_color=c.primary,
            hover_color=c.primary_hover,
            text_color="#FFFFFF",
            font=ctk.CTkFont("Poppins Medium", size=14),
        )
        self.connect_btn.grid(row=1, column=0, sticky="nsew", pady=(0, 6))

        self.status_label = ctk.CTkLabel(
            body,
            text="● Disconnected",
            font=ctk.CTkFont("Poppins Medium", size=12),
            text_color=c.subtext,
            fg_color="transparent",
            anchor="w",
        )
        self.status_label.grid(row=2, column=0, sticky="w")

    def _on_refresh_devices(self) -> None:
        log.debug("_on_refresh_devices()")
        self._devices = self.device_manager.get_connected_devices()
        if self._devices:
            labels = [d["label"] for d in self._devices]
            self.device_combo.configure(values=labels)
            self.device_combo.set(labels[0])
            self.status_label.configure(
                text=f"{len(self._devices)} device(s) found",
                text_color=self.color.subtext,
            )
            log.info("Found %d device(s)", len(self._devices))
        else:
            self.device_combo.configure(values=["No devices"])
            self.device_combo.set("No devices")
            self.status_label.configure(
                text="No devices found", text_color=self.color.subtext
            )
            log.warning("No devices found")

    def _on_connect_toggle(self) -> None:
        c = self.color
        if self.device_manager.is_scrcpy_running():
            log.info("_on_connect_toggle() — disconnecting")
            self.device_manager.stop_scrcpy()
            self._set_conn_state(connected=False)
            self.app.set_header_disconnected()
            return

        if not self._devices:
            log.warning("_on_connect_toggle() — no devices in list, refreshing first")
            self._on_refresh_devices()
            if not self._devices:
                self.status_label.configure(
                    text="Refresh device list first", text_color=c.warning
                )
                return

        selected = self.device_combo.get()
        device = next((d for d in self._devices if d["label"] == selected), None)
        if not device:
            log.warning("_on_connect_toggle() — selected device not in list: %s", selected)
            return

        log.info("_on_connect_toggle() — connecting to %s", device["serial"])
        self.connect_btn.configure(state="disabled")
        self.status_label.configure(text="Connecting…", text_color=c.subtext)

        import threading

        def connect_task() -> None:
            ok = self.device_manager.launch_scrcpy(device["serial"])
            self.app.after(0, lambda: self._finish_connect(ok, device))

        threading.Thread(target=connect_task, daemon=True).start()

    def _finish_connect(self, ok: bool, device: dict) -> None:
        c = self.color
        self.connect_btn.configure(state="normal")
        if ok:
            log.info("Connection successful: %s", device["label"])
            self._set_conn_state(connected=True, label=device["label"])
            self.app.set_header_connected(device["label"])
            self.app.after(500, self._update_action_buttons)
            self._start_health_monitor()
        else:
            log.error("Connection failed for %s", device["serial"])
            self.status_label.configure(
                text="Failed to start scrcpy", text_color=c.error
            )
            self._set_conn_state(connected=False)

    def _start_health_monitor(self) -> None:
        """Periodically check that scrcpy is still alive."""
        self._health_monitor_active = True
        self._check_health()

    def _stop_health_monitor(self) -> None:
        self._health_monitor_active = False

    def _check_health(self) -> None:
        if not getattr(self, '_health_monitor_active', False):
            return
        if not self.device_manager.is_scrcpy_running():
            log.warning("Health monitor: scrcpy died — auto-disconnecting")
            self.device_manager.stop_scrcpy()
            self._set_conn_state(connected=False)
            self.app.set_header_disconnected()
            self._health_monitor_active = False
            return
        self.app.after(3000, self._check_health)

    def _set_conn_state(self, connected: bool, label: str = "") -> None:
        c = self.color
        if connected:
            self.connect_btn.configure(
                text="Disconnect",
                fg_color=c.error,
                hover_color="#D05050",
                text_color="#FFFFFF",
            )
            self.status_label.configure(
                text=f"● Connected — {label}", text_color=c.success
            )
        else:
            self._stop_health_monitor()
            self.connect_btn.configure(
                text="Connect",
                fg_color=c.primary,
                hover_color=c.primary_hover,
                text_color="#FFFFFF",
            )
            self.status_label.configure(text="● Disconnected", text_color=c.subtext)
            self._update_action_buttons()

    # ── Language ─────────────────────────────────────────────────────

    def _create_language_section(self, row: int) -> None:
        self._section_header(row, "LANGUAGE")
        body = self._section_body(row + 1)

        c = self.color
        languages = list(LANG_MAP.keys())
        seg = ctk.CTkSegmentedButton(
            body,
            values=languages,
            command=self._on_language_change,
            font=ctk.CTkFont("Poppins Medium", size=13),
            selected_color=c.primary,
            selected_hover_color=c.primary_hover,
            unselected_color=c.surface_hi,
            unselected_hover_color=c.border_hi,
            text_color=c.text,
            text_color_disabled=c.muted,
            fg_color=c.surface_hi,
            corner_radius=6,
            height=36,
            border_width=0,
        )
        seg.set(languages[0])
        seg.grid(row=0, column=0, sticky="nsew")

    def _on_language_change(self, language: str) -> None:
        self.app.controller.set_language(language)

    # ── Word Length (min + max sliders, 3..10, 10 = "Any") ────────

    _MAX_LEN_CAP = 10

    def _format_max_len(self, v: int) -> str:
        return "Any" if v >= self._MAX_LEN_CAP else str(v)

    def _create_word_length_section(self, row: int) -> None:
        self._section_header(row, "WORD LENGTH")
        body = self._section_body(row + 1)
        body.grid_columnconfigure(0, weight=1)

        self.min_word_length_slider, _ = self._make_slider_row(
            body, row=0, label_text="Min", from_=3, to=8, initial=3,
            on_change=self._on_min_word_length_change,
        )
        self.max_word_length_slider, _ = self._make_slider_row(
            body, row=2, label_text="Max", from_=3, to=self._MAX_LEN_CAP,
            initial=self._MAX_LEN_CAP,
            format_value=self._format_max_len,
            on_change=self._on_max_word_length_change,
        )

    def _on_min_word_length_change(self, value: int) -> None:
        self.app.controller.set_min_word_length(value)
        # Clamp max ≥ min
        if self.max_word_length_slider:
            cur_max = int(round(self.max_word_length_slider.get()))
            if cur_max < value:
                self.max_word_length_slider.set(value)
                # Trigger label refresh
                self.max_word_length_slider._command(value)  # type: ignore[attr-defined]

    def _on_max_word_length_change(self, value: int) -> None:
        if self.min_word_length_slider:
            cur_min = int(round(self.min_word_length_slider.get()))
            if cur_min > value:
                self.min_word_length_slider.set(value)
                self.min_word_length_slider._command(value)  # type: ignore[attr-defined]
                self.app.controller.set_min_word_length(value)

    def get_max_word_length(self) -> int:
        if not self.max_word_length_slider:
            return 99
        v = int(round(self.max_word_length_slider.get()))
        return 99 if v >= self._MAX_LEN_CAP else v

    # ── Order (dropdown) ──────────────────────────────────────────

    _ORDER_VALUES = [
        "Highest score",
        "Random",
        "Shortest first",
        "Longest first",
        "Alphabetical",
    ]

    def _create_order_section(self, row: int) -> None:
        self._section_header(row, "ORDER")
        body = self._section_body(row + 1)
        c = self.color
        self.order_menu = ctk.CTkOptionMenu(
            body,
            values=self._ORDER_VALUES,
            font=ctk.CTkFont("Poppins Medium", size=13),
            dropdown_font=ctk.CTkFont("Poppins Medium", size=13),
            fg_color=c.surface_hi,
            button_color=c.border,
            button_hover_color=c.primary,
            text_color=c.text,
            dropdown_fg_color=c.surface_hi,
            dropdown_text_color=c.text,
            dropdown_hover_color=c.border_hi,
            corner_radius=6,
            height=36,
            anchor="w",
        )
        self.order_menu.set(self._ORDER_VALUES[0])
        self.order_menu.grid(row=0, column=0, sticky="ew")

    def get_order(self) -> str:
        return self.order_menu.get() if self.order_menu else self._ORDER_VALUES[0]

    # ── Max Words (slider, 0 = All) ───────────────────────────────

    _MAX_WORDS_CAP = 200  # "All" sentinel

    def _format_max_words(self, v: int) -> str:
        return "All" if v >= self._MAX_WORDS_CAP else str(v)

    def _create_max_words_section(self, row: int) -> None:
        self._section_header(row, "MAX WORDS")
        body = self._section_body(row + 1)
        body.grid_columnconfigure(0, weight=1)

        self.max_words_slider, self.max_words_value_label = self._make_slider_row(
            body, row=0, label_text="Limit", from_=1, to=self._MAX_WORDS_CAP,
            initial=self._MAX_WORDS_CAP,
            format_value=self._format_max_words,
        )

    def get_max_words(self) -> int:
        if not self.max_words_slider:
            return 0
        v = int(round(self.max_words_slider.get()))
        return 0 if v >= self._MAX_WORDS_CAP else v

    # ── Human Mode (preset + custom jitter / pause sliders) ───────

    def _create_human_mode_section(self, row: int) -> None:
        self._section_header(row, "HUMAN MODE")
        body = self._section_body(row + 1)
        body.grid_columnconfigure(0, weight=1)

        c = self.color
        self.human_mode_seg = ctk.CTkSegmentedButton(
            body,
            values=["Off", "Subtle", "Realistic", "Custom"],
            command=self._on_human_mode_change,
            font=ctk.CTkFont("Poppins Medium", size=12),
            selected_color=c.primary,
            selected_hover_color=c.primary_hover,
            unselected_color=c.surface_hi,
            unselected_hover_color=c.border_hi,
            text_color=c.text,
            text_color_disabled=c.muted,
            fg_color=c.surface_hi,
            corner_radius=6,
            height=32,
            border_width=0,
        )
        self.human_mode_seg.set("Off")
        self.human_mode_seg.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.jitter_slider, _ = self._make_slider_row(
            body, row=1, label_text="Jitter (px)", from_=0, to=20, initial=0,
            on_change=lambda v: self._mark_human_custom(),
        )
        self.pause_slider, _ = self._make_slider_row(
            body, row=3, label_text="Pause (ms max)",
            from_=0, to=1500, initial=0,
            on_change=lambda v: self._mark_human_custom(),
        )

    _HUMAN_PRESETS = {
        "Off":       {"jitter": 0,  "pause": 0},
        "Subtle":    {"jitter": 2,  "pause": 200},
        "Realistic": {"jitter": 6,  "pause": 850},
    }

    def _on_human_mode_change(self, value: str) -> None:
        preset = self._HUMAN_PRESETS.get(value)
        if not preset or not self.jitter_slider or not self.pause_slider:
            return
        # Apply preset to sliders without re-marking as custom
        self._suppress_custom_mark = True
        try:
            self.jitter_slider.set(preset["jitter"])
            self.jitter_slider._command(preset["jitter"])  # type: ignore[attr-defined]
            self.pause_slider.set(preset["pause"])
            self.pause_slider._command(preset["pause"])  # type: ignore[attr-defined]
        finally:
            self._suppress_custom_mark = False

    def _mark_human_custom(self) -> None:
        if getattr(self, "_suppress_custom_mark", False):
            return
        if self.human_mode_seg and self.human_mode_seg.get() != "Custom":
            self.human_mode_seg.set("Custom")

    def get_human_jitter_px(self) -> int:
        return int(round(self.jitter_slider.get())) if self.jitter_slider else 0

    def get_human_pause_max_s(self) -> float:
        if not self.pause_slider:
            return 0.0
        return self.pause_slider.get() / 1000.0

    # Legacy compatibility (kept so older callers still work)
    def get_human_mode(self) -> str:
        return self.human_mode_seg.get() if self.human_mode_seg else "Off"

    # ── Speed ─────────────────────────────────────────────────────────

    def _create_speed_section(self, row: int) -> None:
        c = self.color

        # Custom header with inline value label (right-aligned)
        header = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=0)
        header.grid(row=row, column=0, sticky="nsew", padx=16, pady=(16, 4))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            header,
            text="SPEED",
            font=ctk.CTkFont("Poppins Medium", size=10),
            text_color=c.subtext,
            fg_color="transparent",
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.speed_value_label = ctk.CTkLabel(
            header,
            text="0.80",
            font=ctk.CTkFont("Poppins Medium", size=10),
            text_color=c.primary,
            fg_color="transparent",
            anchor="e",
        )
        self.speed_value_label.grid(row=0, column=1, sticky="e")

        body = self._section_body(row + 1)

        def on_slider(val: float) -> None:
            if self.speed_value_label:
                self.speed_value_label.configure(text=f"{val:.2f}")

        self.speed_slider = ctk.CTkSlider(
            body,
            from_=0,
            to=1,
            command=on_slider,
            progress_color=c.primary,
            button_color=c.primary,
            button_hover_color=c.primary_hover,
            fg_color=c.surface_hi,
            height=16,
        )
        self.speed_slider.set(0.8)
        self.speed_slider.grid(row=0, column=0, sticky="ew", pady=(0, 4))

    def get_speed(self) -> float:
        return self.speed_slider.get() if self.speed_slider else 0.8

    # ── Input Mode ────────────────────────────────────────────────

    def _create_input_mode_section(self, row: int) -> None:
        self._section_header(row, "INPUT MODE")
        body = self._section_body(row + 1)

        c = self.color
        self.input_mode_seg = ctk.CTkSegmentedButton(
            body,
            values=["Mouse", "ADB"],
            command=self._on_input_mode_change,
            font=ctk.CTkFont("Poppins Medium", size=13),
            selected_color=c.primary,
            selected_hover_color=c.primary_hover,
            unselected_color=c.surface_hi,
            unselected_hover_color=c.border_hi,
            text_color=c.text,
            text_color_disabled=c.muted,
            fg_color=c.surface_hi,
            corner_radius=6,
            height=36,
            border_width=0,
        )
        self.input_mode_seg.set("Mouse")
        self.input_mode_seg.grid(row=0, column=0, sticky="nsew")

    def _on_input_mode_change(self, value: str) -> None:
        if value == "ADB":
            dm = self.device_manager
            if not dm.device_serial:
                self.input_mode_seg.set("Mouse")
                return
            if not dm.adb_input or not dm.adb_input.status()[0]:
                ok, msg = dm.setup_adb_input()
                if not ok:
                    self.input_mode_seg.set("Mouse")
                    if self.status_label:
                        self.status_label.configure(
                            text=msg, text_color=self.color.warning
                        )
                    return
            if self.status_label and dm.adb_input:
                _, msg = dm.adb_input.status()
                self.status_label.configure(
                    text=msg, text_color=self.color.success
                )

    def get_input_mode(self) -> str:
        return self.input_mode_seg.get() if self.input_mode_seg else "Mouse"

    # ── Actions ───────────────────────────────────────────────────────

    def _create_action_section(self, row: int) -> None:
        c = self.color
        body = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=0)
        body.grid(row=row, column=0, sticky="nsew", padx=16, pady=(20, 16))
        body.grid_columnconfigure(0, weight=1)

        self.scan_window_btn = ctk.CTkButton(
            body,
            text="Scan Window",
            command=self._on_scan_click,
            height=40,
            corner_radius=6,
            font=ctk.CTkFont("Poppins Medium", size=14),
            fg_color=c.surface_hi,
            text_color=c.text,
            hover_color=c.border_hi,
            border_color=c.border_hi,
            border_width=1,
        )
        self.scan_window_btn.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.disable_scan_window_btn()

        self.solve_btn = ctk.CTkButton(
            body,
            text="Solve",
            command=self._on_solve_click,
            height=52,
            corner_radius=6,
            font=ctk.CTkFont("Poppins Bold", size=17),
            fg_color=c.primary,
            text_color="#FFFFFF",
            hover_color=c.primary_hover,
        )
        self.solve_btn.grid(row=1, column=0, sticky="nsew")
        self.disable_solve_btn()

    def _on_scan_click(self) -> None:
        log.info("_on_scan_click()")
        hwnd = self.app.get_mirror_hwnd()
        if not hwnd or self.app.is_scanning:
            log.warning("_on_scan_click() — blocked (hwnd=%s, is_scanning=%s)", hwnd, self.app.is_scanning)
            return
        grid = self.app.grid_widget
        if not grid or not grid.inner_frame_label:
            return
        self.hide_score_panel()
        self.app.controller.set_game()

    def _on_solve_click(self) -> None:
        log.info("_on_solve_click()")
        if self.app.is_solving or self.app.is_scanning:
            log.warning("_on_solve_click() — blocked (is_solving=%s, is_scanning=%s)",
                        self.app.is_solving, self.app.is_scanning)
            return
        self.app.controller.solve_game()

    # ── Button state management ───────────────────────────────────────

    def _disabled_style(self) -> dict:
        c = self.color
        return {
            "fg_color": c.surface_hi,
            "text_color": c.muted,
            "hover_color": c.surface_hi,
            "border_width": 0,
            "cursor": "arrow",
        }

    def disable_solve_btn(self) -> None:
        if self.solve_btn:
            self.solve_btn.configure(**self._disabled_style())

    def enable_solve_btn(self) -> None:
        grid = self.app.grid_widget
        if (
            self.app.get_mirror_hwnd()
            and not self.app.is_solving
            and not self.app.is_scanning
            and grid
            and grid.is_valid()
        ):
            c = self.color
            self.solve_btn.configure(
                fg_color=c.primary,
                text_color="#FFFFFF",
                hover_color=c.primary_hover,
                border_width=0,
                cursor="hand2",
            )

    def disable_scan_window_btn(self) -> None:
        if self.scan_window_btn:
            self.scan_window_btn.configure(**self._disabled_style())

    def enable_scan_window_btn(self) -> None:
        if (
            self.app.get_mirror_hwnd()
            and not self.app.is_solving
            and not self.app.is_scanning
        ):
            c = self.color
            self.scan_window_btn.configure(
                fg_color=c.surface_hi,
                text_color=c.text,
                hover_color=c.border_hi,
                border_color=c.border_hi,
                border_width=1,
                cursor="hand2",
            )

    def _update_action_buttons(self) -> None:
        """Re-evaluate whether scan / solve should be enabled."""
        if self.app.get_mirror_hwnd():
            self.enable_scan_window_btn()
        else:
            self.disable_scan_window_btn()
            self.disable_solve_btn()

    # ── Score / Progress ─────────────────────────────────────────────

    def _create_score_section(self, row: int) -> None:
        c = self.color
        self._score_frame = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=0)
        self._score_frame.grid(row=row, column=0, sticky="nsew", padx=16, pady=(12, 4))
        self._score_frame.grid_columnconfigure(0, weight=1)
        # Hidden until solve
        self._score_frame.grid_remove()

        # Total points heading
        self._score_total_label = ctk.CTkLabel(
            self._score_frame,
            text="",
            font=ctk.CTkFont("Poppins Bold", size=14),
            text_color=c.text,
            fg_color="transparent",
            anchor="w",
        )
        self._score_total_label.grid(row=0, column=0, sticky="w", pady=(0, 2))

        # Breakdown text
        self._score_breakdown_label = ctk.CTkLabel(
            self._score_frame,
            text="",
            font=ctk.CTkFont("Poppins Medium", size=11),
            text_color=c.subtext,
            fg_color="transparent",
            anchor="w",
            justify="left",
        )
        self._score_breakdown_label.grid(row=1, column=0, sticky="w", pady=(0, 6))

        # Progress bar
        self._progress_bar = ctk.CTkProgressBar(
            self._score_frame,
            progress_color=c.primary,
            fg_color=c.surface_hi,
            height=10,
            corner_radius=5,
        )
        self._progress_bar.set(0)
        self._progress_bar.grid(row=2, column=0, sticky="ew", pady=(0, 2))

        # Progress label
        self._progress_label = ctk.CTkLabel(
            self._score_frame,
            text="",
            font=ctk.CTkFont("Poppins Medium", size=11),
            text_color=c.subtext,
            fg_color="transparent",
            anchor="w",
        )
        self._progress_label.grid(row=3, column=0, sticky="w")

    def show_score_summary(self, summary: dict) -> None:
        """Display pre-solve score prediction."""
        if not self._score_frame:
            return
        c = self.color
        total = summary["total_points"]
        words = summary["total_words"]
        bonus_w = summary["bonus_words"]
        bonus_p = summary["bonus_points"]
        lc = summary["length_counts"]

        self._score_total_label.configure(
            text=f"⭐  {total} pts  ·  {words} words"
        )

        lines = []
        pt_map = {"3": 1, "4": 6, "5": 8, "6": 10, "7": 12, "8+": 14}
        for bucket in ["3", "4", "5", "6", "7", "8+"]:
            cnt = lc.get(bucket, 0)
            if cnt:
                lines.append(f"{bucket} letters: {cnt}  (+{cnt * pt_map[bucket]} pts)")
        if bonus_w:
            lines.append(f"★ Bonus tile: {bonus_w} words  (+{bonus_p} pts)")
        self._score_breakdown_label.configure(text="\n".join(lines))

        self._progress_bar.set(0)
        self._progress_label.configure(text="Waiting…")
        self._score_frame.grid()

    def update_progress(self, played: int, total: int, earned: int,
                        expected: int, done: bool = False) -> None:
        """Update the live progress bar and label during automation."""
        if not self._progress_bar or not self._progress_label:
            return
        frac = played / total if total else 0
        self._progress_bar.set(frac)
        pct = int(frac * 100)
        if done:
            self._progress_label.configure(
                text=f"Done — {played}/{total} words · {earned} pts",
                text_color=self.color.success,
            )
            self._progress_bar.configure(progress_color=self.color.success)
        else:
            self._progress_label.configure(
                text=f"{played}/{total}  ({pct}%)  ·  {earned}/{expected} pts",
            )

    def hide_score_panel(self) -> None:
        """Hide the score / progress panel."""
        if self._score_frame:
            self._score_frame.grid_remove()
        if self._progress_bar:
            self._progress_bar.configure(progress_color=self.color.primary)

    # ── Credits ───────────────────────────────────────────────────────

    def _create_credits_section(self, row: int) -> None:
        c = self.color
        frame = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=0)
        frame.grid(row=row, column=0, sticky="sew", padx=16, pady=(20, 12))
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="Developed by Fabian Barua",
            font=ctk.CTkFont("Poppins Medium", size=11),
            text_color=c.subtext,
            fg_color="transparent",
            anchor="center",
        ).grid(row=0, column=0, sticky="ew")

        link = ctk.CTkLabel(
            frame,
            text="github.com/FabianBarua",
            font=ctk.CTkFont("Poppins Medium", size=11),
            text_color=c.primary,
            fg_color="transparent",
            anchor="center",
            cursor="hand2",
        )
        link.grid(row=1, column=0, sticky="ew")
        link.bind("<Button-1>", lambda e: __import__("webbrowser").open(
            "https://github.com/FabianBarua/"))
