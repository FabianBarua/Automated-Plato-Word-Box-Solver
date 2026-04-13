import re
from functools import partial
from typing import List

import customtkinter as ctk


class Grid(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        """Interactive grid component for displaying and editing letter matrices."""
        super().__init__(master, **kwargs)
        self.img_process = app.controller.img_process
        self.color =  app.color
        self.app = app
        
        self.inner_frame = None
        self.inner_frame_label = None
        self.frame = None

        
        self.inner_frame_text: str = "No Grid Found" # initial text on start
        
        self.cells = []
        self.grid_col_size = 0
        self.grid_row_size = 0
        
        self.empty_entries : set[ctk.CTkEntry]= set()
        
        self._apply_styles()
        self.create_grid_frame()
        
        
    def _apply_styles(self):
        """Grid UI stylings"""
        CELL_BORDER_WIDTH: int = 1
        CELL_CORNER_RADIUS: int = 0
        GRID_FRAME_CORNER_RADIUS: int = 8
        GRID_FRAME_BORDER_WIDTH: int = 1
        GRID_INNER_FRAME_CORNER_RADIUS: int = 0
        GRID_INNER_FRAME_BORDER_WIDTH: int = 0

        self.grid_frame_styles = {
            "corner_radius": GRID_FRAME_CORNER_RADIUS,
            "fg_color": self.color.neutral,
            "border_color": self.color.border,
            "border_width": GRID_FRAME_BORDER_WIDTH,
        }
        self.grid_inner_frame_styles = {
            "corner_radius": GRID_INNER_FRAME_CORNER_RADIUS,
            "fg_color": self.color.on_primary,
            "border_color": self.color.neutral,
            "border_width": GRID_INNER_FRAME_BORDER_WIDTH,
        }
        self.grid_inner_frame_label = {
            "fg_color": self.color.on_primary,
            "font": ctk.CTkFont("Poppins Medium", size=18),
            "text_color": self.color.subtext,
        }
        self.base_cell_styles = {
            "font": ctk.CTkFont("Poppins Bold", size=32),
            "justify": "center",
            "fg_color": self.color.on_primary,
            "text_color": self.color.primary,
            "border_width": CELL_BORDER_WIDTH,
            "border_color": self.color.border,
            "corner_radius": CELL_CORNER_RADIUS,
        }
        self.cell_styles_focus_in = {
            "border_color": self.color.primary,
        }
        self.cell_styles_focus_out = {
            "border_color": self.color.border,
        }
    
    def create_grid_frame(self) -> None:
        """
        Method handles the creation of the grid on the left frame.
        Follows a responsive design
        """
        margin : int = 100
        pad : int = 50
        
        self.cells = []
        self.empty_entries.clear()
        
        def stay_square(event) -> None:
            """Maintains square aspect ratio for grid frame during window resize"""
            size: int = min(event.width, event.height) 
            self.frame.place_configure(relx=0.5, rely=0.5, anchor="center", width=(size-margin), height=(size-margin))
            self.inner_frame.place_configure(relx=0.5, rely=0.5, anchor="center", width=(size-margin - pad), height=(size-margin - pad))
        
        # Create outer content frame
        self.frame = ctk.CTkFrame(
            self.master,
            **self.grid_frame_styles,        
        )
        
        # Create inner content frame
        self.inner_frame = ctk.CTkFrame(
            self.frame,
            **self.grid_inner_frame_styles
        )

        # Create status label
        self.inner_frame_label = ctk.CTkLabel(
            master=self.inner_frame,
            **self.grid_inner_frame_label,
            text=self.inner_frame_text
        )
        
        # Initial placement and sizing
        size = min(self.master.winfo_width(), self.master.winfo_height()) 
        
        self.frame.place_configure(relx=0.5, rely=0.5, anchor="center", width=(size-margin), height=(size-margin))
        self.inner_frame.place_configure(relx=0.5, rely=0.5, anchor="center", width=(size-margin- pad), height=(size-margin- pad))
        self.inner_frame_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Bind resize event for responsive behavior
        self.master.bind("<Configure>", stay_square)
        
        self.configure_solve_btn()

    def fill_grid(self) -> None:
        """Populates the grid ui with the letters discovered from OCR processing"""
        # Highlight the current cell clicked and unhighlight the others
        def on_focus_in(entry) :
            entry.configure(**self.cell_styles_focus_in)
            
        def on_focus_out(entry) -> None:
            entry.configure(**self.cell_styles_focus_out)
        
        def on_entry_change(entry, var, *args) -> None:
            """Validates and formats cell input in real-time"""
            val = var.get()
            val = val[:2] # Limit to 2 characters
            val = re.sub('[^A-Za-z]', '', val) # Remove non-alphabetic characters
            val = val.capitalize()

            if (var.get()!= val):
                var.set(val)
            
            # Empty cells visuals
            if (val == "") :
                self.empty_entries.add(entry)
                entry.configure(fg_color=self.color.error_container)
            else:
                if entry in self.empty_entries:
                    self.empty_entries.remove(entry)
                entry.configure(fg_color=self.color.on_primary)
                
            self.configure_solve_btn()

        # Get grid dimensions from OCR results
        self.grid_row_size = len(self.img_process.contour_info_grid)
        self.grid_col_size = len(self.img_process.contour_info_grid[0]) if self.grid_row_size > 0 else 0

        # Prevent a 1 x 1 grid from being made
        if (self.grid_row_size < 2 and self.grid_col_size < 2):
            return
        
        # Allows the cells to be contained in an NxN grid
        for i in range(self.grid_row_size):
            self.inner_frame.grid_columnconfigure(i,weight=1)
            self.inner_frame.grid_rowconfigure(i,weight=1)
        
        
        for row in range(self.grid_row_size):
            row_cells = []
            for col in range(self.grid_col_size):
                letter : str = self.img_process.contour_info_grid[row][col][2].capitalize()

                var = ctk.StringVar()
            
                entry = ctk.CTkEntry(
                    self.inner_frame,
                    **self.base_cell_styles,
                    textvariable=var
                )

                entry.grid(
                    row=row,
                    column=col,
                    sticky="nsew",
                    padx=0,
                    pady=0
                )
                var.trace_add("write",  partial(on_entry_change, entry, var))
                entry.insert(0, letter)
                

                if letter.strip() == "":
                    self.empty_entries.add(entry)
                    entry.configure(fg_color=self.color.error_container)
                    
                entry.bind("<FocusIn>", lambda event, e=entry: on_focus_in(e))
                entry.bind("<FocusOut>", lambda event, e=entry: on_focus_out(e))
                

                row_cells.append(entry)
            
            self.cells.append(row_cells)
        
        self.configure_solve_btn()
    
    def is_valid(self) -> int :
        return len(self.empty_entries) == 0 and len(self.cells) >= 4
        
    def extract_letters(self) -> List[List[str]]:
        return [[cell.get().lower() for cell in row ]for row  in self.cells]
    
    def set_inner_frame_text(self, text : str) -> None:
        """Text in the grid"""
        self.inner_frame_text = text
        
    def set_grid_row_col_size(self, row_size : int, col_size : int) -> None:
        """Initialize the grid's column size or row size"""
        self.grid_row_size = row_size
        self.grid_col_size = col_size
        
    def configure_solve_btn(self) -> None:
        settings = self.app.settings
        if not settings or self.app.is_solving:
            return
        if self.is_valid():
            settings.enable_solve_btn()
        else:
            settings.disable_solve_btn()
        