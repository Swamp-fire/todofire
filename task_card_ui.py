import tkinter as tk
from tkinter import ttk
import ttkbootstrap as bs
import logging
import datetime # Ensure this import is present

logger = logging.getLogger(__name__)

class TaskCard(bs.Frame):
    def __init__(self, parent, task, app_callbacks=None):
        super().__init__(parent, borderwidth=0, relief="solid", padding=7)
        self.task = task
        self.app_callbacks = app_callbacks if app_callbacks else {}
        self.is_selected = False

        self.default_bootstyle = "dark" # Changed to "dark" for a more definitive dark background
        self.selected_bootstyle = "primary" # Selected card color (e.g., orange)
        self.configure(bootstyle=self.default_bootstyle)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=0)

        # --- Title (Row 0, Col 0) ---
        title_text = self.task.title if self.task and self.task.title else "No Title"
        self.title_label = bs.Label(self, text=title_text, font=("Helvetica", 12, "bold"), anchor="w") # No explicit bootstyle
        self.title_label.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(0,5))

        # --- Due Date (Row 0, Col 1) ---
        due_date_str = "N/A"
        due_time_str = "-"
        if self.task and self.task.due_date:
            try:
                dt_obj = datetime.datetime.fromisoformat(self.task.due_date)
                due_date_str = dt_obj.strftime("%a, %d %b")
                due_time_str = dt_obj.strftime("%H:%M")
            except ValueError:
                logger.warning(f"TaskCard ID {self.task.id}: Could not parse due_date '{self.task.due_date}' for date/time. Displaying raw or N/A.")
                due_date_str = self.task.due_date
        self.due_date_label = bs.Label(self, text=due_date_str, font=("Helvetica", 10)) # No explicit bootstyle
        self.due_date_label.grid(row=0, column=1, sticky="ne", padx=(5,0))

        # --- Due Time (Row 0, Col 2) ---
        self.due_time_label = bs.Label(self, text=due_time_str, font=("Helvetica", 10)) # No explicit bootstyle
        self.due_time_label.grid(row=0, column=2, sticky="ne", padx=(5,0))

        # --- Status (Row 1, Col 0) ---
        status_text = f"Status: {self.task.status}" if self.task else "Status: N/A"
        self.status_label = bs.Label(self, text=status_text, font=("Helvetica", 10), anchor="w") # No explicit bootstyle
        self.status_label.grid(row=1, column=0, sticky="sw", pady=(5,0))

        # --- Repetition Cycle (Row 1, Col 1) ---
        repetition_text = self.task.repetition if self.task and self.task.repetition and self.task.repetition != "None" else "-"
        self.repetition_label = bs.Label(self, text=f"Rep: {repetition_text}", font=("Helvetica", 10), anchor="w") # No explicit bootstyle
        self.repetition_label.grid(row=1, column=1, sticky="sw", padx=(5,0), pady=(5,0))

        # --- Duration (Row 1, Col 2) ---
        duration_str = "-"
        if self.task and self.task.duration and self.task.duration > 0:
            hours = self.task.duration // 60
            minutes = self.task.duration % 60
            if hours > 0 and minutes > 0: duration_str = f"{hours}h {minutes}m"
            elif hours > 0: duration_str = f"{hours}h"
            else: duration_str = f"{minutes}m"
        self.duration_label = bs.Label(self, text=f"Work: {duration_str}", font=("Helvetica", 10)) # No explicit bootstyle
        self.duration_label.grid(row=1, column=2, sticky="se", pady=(5,0), padx=(5,0))

        # All labels are now direct children and should have transparent backgrounds by default.
        # Their text color will be handled by ttkbootstrap based on the parent's (self) bootstyle.
        self.themable_widgets = [self, self.title_label, self.due_date_label, self.due_time_label, self.status_label, self.duration_label, self.repetition_label]

        for widget in self.themable_widgets:
            widget.bind("<Button-1>", self._on_click)

        # Explicitly set initial background of all labels to match the card's default background
        self.update_idletasks() # Ensure card's style is applied and background color can be read
        try:
            style = ttk.Style()
            # Construct the style name for the frame based on its bootstyle
            # For bs.Frame, if bootstyle is "dark", ttk style might be "dark.TFrame"
            frame_stylename = f"{self.default_bootstyle}.TFrame"
            actual_card_bg = style.lookup(frame_stylename, "background")

            if actual_card_bg:
                for widget in self.themable_widgets:
                    if widget is not self: # Only apply to child labels, not the card frame itself
                        try:
                            widget.configure(background=actual_card_bg)
                        except tk.TclError as e_label:
                            logger.warning(f"Could not set initial background for label {widget}: {e_label}")
            else:
                logger.warning(f"Could not determine actual background for {frame_stylename} to apply to labels.")

        except tk.TclError as e_init_style: # Error from ttk.Style() or initial style.lookup
            logger.error(f"Error during initial label background styling in TaskCard.__init__: {e_init_style}")

        logger.debug(f"TaskCard created for task ID: {self.task.id if self.task else 'N/A'}")

    def _on_click(self, event):
        logger.debug(f"TaskCard clicked for task ID: {self.task.id if self.task else 'N/A'}")
        if 'on_card_selected' in self.app_callbacks and callable(self.app_callbacks['on_card_selected']):
            try:
                self.app_callbacks['on_card_selected'](self.task.id, self)
            except Exception as e:
                logger.error(f"Error calling on_card_selected callback from TaskCard: {e}", exc_info=True)
        else:
            logger.warning("'on_card_selected' callback not found or not callable in app_callbacks.")

    def select(self):
        self.is_selected = True
        self.configure(bootstyle=self.selected_bootstyle) # Main card frame

        self.update_idletasks() # Ensure card's style is applied and background color can be read
        try:
            style = ttk.Style()
            frame_stylename = f"{self.selected_bootstyle}.TFrame"
            actual_card_bg = style.lookup(frame_stylename, "background")

            if actual_card_bg:
                for widget in self.themable_widgets:
                    if widget is not self: # Only apply to child labels
                        try:
                            widget.configure(background=actual_card_bg)
                        except tk.TclError as e_label:
                            logger.warning(f"Could not set selected background for label {widget}: {e_label}")
            else:
                logger.warning(f"Could not determine actual background for {frame_stylename} in select() to apply to labels.")

        except tk.TclError as e_select_style:
            logger.error(f"Error during selected label background styling in TaskCard.select(): {e_select_style}")

        logger.debug(f"TaskCard ID {self.task.id} BOOTSTYLE set to {self.selected_bootstyle}. Child labels text color will adapt.")

    def deselect(self):
        self.is_selected = False
        self.configure(bootstyle=self.default_bootstyle) # Main card frame

        self.update_idletasks() # Ensure card's style is applied and background color can be read
        try:
            style = ttk.Style()
            frame_stylename = f"{self.default_bootstyle}.TFrame"
            actual_card_bg = style.lookup(frame_stylename, "background")

            if actual_card_bg:
                for widget in self.themable_widgets:
                    if widget is not self: # Only apply to child labels
                        try:
                            widget.configure(background=actual_card_bg)
                        except tk.TclError as e_label:
                            logger.warning(f"Could not set default background for label {widget}: {e_label}")
            else:
                logger.warning(f"Could not determine actual background for {frame_stylename} in deselect() to apply to labels.")

        except tk.TclError as e_deselect_style:
            logger.error(f"Error during deselected label background styling in TaskCard.deselect(): {e_deselect_style}")

        logger.debug(f"TaskCard ID {self.task.id} BOOTSTYLE set to {self.default_bootstyle}. Child labels text color will adapt.")

if __name__ == '__main__':
    root = bs.Window(themename="solar") # solar is a dark theme, "secondary" might be light in it.
                                      # Consider "dark" for self.default_bootstyle if solar is used.
    root.geometry("400x600")

    class DummyTask:
        def __init__(self, id, title, description, duration, creation_date, repetition, priority, category, due_date=None, status="Pending", last_reset_date=None):
            self.id = id
            self.title = title
            self.description = description
            self.duration = duration
            self.creation_date = creation_date
            self.repetition = repetition
            self.priority = priority
            self.category = category
            self.due_date = due_date
            self.status = status
            self.last_reset_date = last_reset_date if last_reset_date else datetime.date.today().isoformat()

    sample_tasks_data = [
        (1, "Complete Project Proposal", "Finalize and submit the project proposal document.", 120, datetime.datetime.now().isoformat(), "None", 3, "Work", (datetime.datetime.now() + datetime.timedelta(days=2)).isoformat(), "Pending"),
        (2, "Grocery Shopping", "Buy milk, eggs, bread, and cheese.", 45, datetime.datetime.now().isoformat(), "Weekly", 2, "Personal", (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat(), "Pending"),
    ]

    dummy_tasks = [DummyTask(*data) for data in sample_tasks_data]

    # Test with different default card bootstyles
    # Card with "secondary" default bootstyle
    card1_frame = bs.Frame(root, padding=10)
    card1_frame.pack(fill=tk.X)
    bs.Label(card1_frame, text="Card with 'secondary' default bootstyle:").pack(anchor='w')
    card1 = TaskCard(card1_frame, dummy_tasks[0])
    card1.pack(pady=5, fill=tk.X, expand=True)

    # Card with "dark" default bootstyle
    card2_frame = bs.Frame(root, padding=10)
    card2_frame.pack(fill=tk.X)
    bs.Label(card2_frame, text="Card with 'dark' default bootstyle (if solar theme):").pack(anchor='w')
    card2 = TaskCard(card2_frame, dummy_tasks[1])
    card2.default_bootstyle = "dark" # Override for testing
    card2.configure(bootstyle=card2.default_bootstyle)
    # Manually ensure labels are transparent against this new default for testing __init__ effect
    card2.update_idletasks()
    try:
        dark_bg = ttk.Style().lookup("dark.TFrame", "background")
        for label in [card2.title_label, card2.due_date_label, card2.due_time_label, card2.status_label, card2.repetition_label, card2.duration_label]:
            label.configure(background=dark_bg)
    except: pass # Ignore if style lookup fails
    card2.pack(pady=5, fill=tk.X, expand=True)

    # Simulate selection
    # card1.select()
    # card2.select()

    root.mainloop()
