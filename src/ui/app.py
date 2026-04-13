import ctypes

import customtkinter as ctk

from ui.colors import Colors
from core.controller import AppController
from ui.settings_panel import SettingsPanel
from ui.grid_frame import Grid


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.controller = AppController(self)
        self.color = Colors()

        self.state_label: ctk.CTkLabel | None = None
        self.header_status: ctk.CTkLabel | None = None
        self.left_frame: ctk.CTkFrame | None = None
        self.right_frame: ctk.CTkFrame | None = None
        self.grid_widget: Grid | None = None
        self.settings: SettingsPanel | None = None

        self.is_solving: bool = False
        self.is_paused: bool = False
        self.is_scanning: bool = False

        self._load_custom_fonts()
        self._apply_styles()
        self._setup_window()
        self._configure_layout()
        self._create_widgets()

    def get_mirror_hwnd(self) -> int:
        """Returns the window handle for the scrcpy mirror window, or 0 if not found."""
        return self.controller.device_manager.get_window_handle()

    # ── Styles ──────────────────────────────────────────────────────

    def _apply_styles(self) -> None:
        c = self.color
        _base = {
            "font": ctk.CTkFont("Poppins Medium", size=13),
            "height": 34,
            "corner_radius": 0,
        }
        self.state_label_base_style = {
            **_base,
            "fg_color": c.primary_dim,
            "text_color": c.primary,
        }
        self.state_label_solving_style = {
            **self.state_label_base_style,
            "text": "  Solving…   ·   Space = Pause   ·   Esc = Stop  ",
        }
        self.state_label_paused_style = {
            **self.state_label_base_style,
            "text": "  Paused   ·   Space = Resume   ·   Esc = Stop  ",
        }

    # ── Window setup ────────────────────────────────────────────────

    def _setup_window(self) -> None:
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.title("Word Box Solver")
        self.geometry("1280x720")
        self.minsize(960, 600)
        self.configure(fg_color=self.color.bg)

    def _configure_layout(self) -> None:
        # Column 0: grid area (expands); Column 1: fixed 280 px sidebar
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=280)
        self.grid_rowconfigure(0, weight=0)  # header bar
        self.grid_rowconfigure(1, weight=0)  # state bar (hidden until solving)
        self.grid_rowconfigure(2, weight=1)  # main content

    def _create_widgets(self) -> None:
        self._create_header(row=0)
        self._create_left_frame(row=2, col=0)
        self._create_right_frame(row=2, col=1)

    def _load_custom_fonts(self) -> None:
        from core.paths import FONTS_DIR
        fonts_dir = FONTS_DIR
        for ttf in fonts_dir.glob("*.ttf"):
            ctypes.windll.gdi32.AddFontResourceW(str(ttf))

    # ── Header ──────────────────────────────────────────────────────

    def _create_header(self, row: int) -> None:
        c = self.color
        header = ctk.CTkFrame(
            self,
            fg_color=c.surface,
            corner_radius=0,
            border_color=c.border,
            border_width=1,
            height=48,
        )
        header.grid(row=row, column=0, columnspan=2, sticky="nsew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            header,
            text="Word Box Solver",
            font=ctk.CTkFont("Poppins Bold", size=16),
            text_color=c.text,
            fg_color="transparent",
            anchor="w",
        ).grid(row=0, column=0, sticky="nsew", padx=(18, 0))

        self.header_status = ctk.CTkLabel(
            header,
            text="● No Device",
            font=ctk.CTkFont("Poppins Medium", size=12),
            text_color=c.subtext,
            fg_color="transparent",
            anchor="e",
        )
        self.header_status.grid(row=0, column=1, sticky="nsew", padx=(0, 18))

    # ── Frames ──────────────────────────────────────────────────────

    def _create_left_frame(self, row: int, col: int) -> None:
        self.left_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color=self.color.bg, border_width=0
        )
        self.left_frame.grid(row=row, column=col, sticky="nsew")
        self.grid_widget = Grid(self.left_frame, self)

    def _create_right_frame(self, row: int, col: int) -> None:
        self.right_frame = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=self.color.surface,
            border_color=self.color.border,
            border_width=0,
            width=280,
        )
        self.right_frame.grid(row=row, column=col, sticky="nsew")
        self.right_frame.grid_propagate(False)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.settings = SettingsPanel(self.right_frame, self)

    # ── State bar ───────────────────────────────────────────────────

    def create_state_label(self, row: int = 1, col: int = 0) -> None:
        """Narrow status strip that appears between the header and content while solving."""
        self.state_label = ctk.CTkLabel(self, **self.state_label_solving_style)
        self.state_label.grid(row=1, column=0, columnspan=2, sticky="nsew")

    # ── Header status helpers ────────────────────────────────────────

    def set_header_connected(self, device_label: str) -> None:
        if self.header_status:
            self.header_status.configure(
                text=f"● {device_label}", text_color=self.color.success
            )

    def set_header_disconnected(self) -> None:
        if self.header_status:
            self.header_status.configure(
                text="● No Device", text_color=self.color.subtext
            )
