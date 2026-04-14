class Colors:
    """
    Dark professional color palette for Word Box Solver.
    Legacy aliases at the bottom maintain backward-compatibility with grid_frame.py.
    """

    def __init__(self) -> None:
        # ── Backgrounds ───────────────────────────────────────────────
        self.bg         = "#0E0E11"   # window / outermost background
        self.surface    = "#16161B"   # panels, sidebar, cards
        self.surface_hi = "#1E1E26"   # elevated widgets, disabled bg

        # ── Borders ───────────────────────────────────────────────────
        self.border     = "#2A2A37"   # default border
        self.border_hi  = "#44445E"   # focused / active border

        # ── Accent — indigo / lavender ────────────────────────────────
        self.primary        = "#8878EC"  # main accent
        self.primary_hover  = "#7060D4"  # hover state
        self.primary_dim    = "#1C1A38"  # tinted background

        # ── Semantic ──────────────────────────────────────────────────
        self.success    = "#4ADE80"   # connected / ok
        self.success_bg = "#0D2B1A"
        self.error      = "#F87171"   # error / disconnected
        self.error_bg   = "#2B1010"
        self.warning    = "#F0A04B"
        self.star       = "#F5C418"   # gold, favourite cell border/accent
        self.star_bg    = "#251E08"   # dark gold, favourite cell background

        # ── Text ──────────────────────────────────────────────────────
        self.text    = "#E4E4EE"   # primary text
        self.subtext = "#7878A0"   # secondary / caption
        self.muted   = "#3C3C50"   # disabled / placeholder

        # ── Legacy aliases (backward-compat with grid_frame.py) ───────
        self.neutral            = self.bg
        self.on_primary         = self.surface
        self.secondary          = self.primary_hover
        self.tertiary           = "#7D5260"
        self.neutral_variant    = self.surface_hi
        self.on_neutral_variant = self.subtext
        self.error_container    = self.error_bg
        self.primary_container  = self.primary_dim