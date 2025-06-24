import tkinter as tk
from tkinter import ttk
import ttkbootstrap as bs
import logging
import datetime # Ensure this import is present

logger = logging.getLogger(__name__)

class TaskCard(bs.Frame):
    def __init__(self, parent, task, app_callbacks=None):
        super().__init__(parent, borderwidth=1, relief="solid", padding=7)
        self.task = task
        self.app_callbacks = app_callbacks if app_callbacks else {}
        self.is_selected = False

        self.default_bootstyle = "light"
        self.selected_bootstyle = "primary"
        self.configure(bootstyle=self.default_bootstyle)
        # self.default_bg logic removed

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        # --- Title (Row 0, Col 0) ---
        title_text = self.task.title if self.task and self.task.title else "No Title"
        title_label = bs.Label(self, text=title_text, font=("Helvetica", 12, "bold"), anchor="w")
        title_label.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(0,5))

        # --- Due Date (Row 0, Col 1) ---
        due_date_str = "N/A"
        if self.task and self.task.due_date:
            try:
                # NEW LINE:
                dt_obj = datetime.datetime.fromisoformat(self.task.due_date)
                due_date_str = dt_obj.strftime("%a, %d %b") # Compact format
            except ValueError:
                logger.warning(f"TaskCard ID {self.task.id}: Could not parse due_date '{self.task.due_date}' with fromisoformat. Displaying raw.")
                due_date_str = self.task.due_date
        due_date_label = bs.Label(self, text=due_date_str, font=("Helvetica", 10))
        due_date_label.grid(row=0, column=1, sticky="ne", padx=(5,0))

        # --- Status (Row 1, Col 0) ---
        status_text = f"Status: {self.task.status}" if self.task else "Status: N/A"
        status_label = bs.Label(self, text=status_text, font=("Helvetica", 10), anchor="w")
        status_label.grid(row=1, column=0, sticky="sw", pady=(5,0))

        # --- Duration (Row 1, Col 1) ---
        duration_str = "-"
        if self.task and self.task.duration and self.task.duration > 0:
            hours = self.task.duration // 60
            minutes = self.task.duration % 60
            if hours > 0 and minutes > 0: duration_str = f"{hours}h {minutes}m"
            elif hours > 0: duration_str = f"{hours}h"
            else: duration_str = f"{minutes}m"
        duration_label = bs.Label(self, text=f"Work: {duration_str}", font=("Helvetica", 10))
        duration_label.grid(row=1, column=1, sticky="se", pady=(5,0), padx=(5,0))

        # ID Label is removed. details_frame is removed.

        self.themable_widgets = [self, title_label, due_date_label, status_label, duration_label]

        for widget in self.themable_widgets:
            if widget is not self:
                 widget.bind("<Button-1>", self._on_click)
        self.bind("<Button-1>", self._on_click)

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
        self.configure(bootstyle=self.selected_bootstyle)
        # Child labels with default/no explicit bootstyle should adapt automatically.
        self.is_selected = True
        logger.debug(f"TaskCard ID {self.task.id} BOOTSTYLE set to {self.selected_bootstyle}.")

    def deselect(self):
        self.configure(bootstyle=self.default_bootstyle)
        # Child labels should revert with parent's bootstyle change.
        self.is_selected = False
        logger.debug(f"TaskCard ID {self.task.id} BOOTSTYLE set to {self.default_bootstyle}.")

if __name__ == '__main__':
    # Example usage for testing TaskCard independently
    root = bs.Window(themename="solar")
    root.geometry("400x600")

    # Dummy Task class for testing
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
        (3, "Book Doctor Appointment", "Schedule a check-up.", 15, datetime.datetime.now().isoformat(), "None", 2, "Health", (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat(), "Completed"),
        (4, "Gym Session", "Leg day workout.", 60, datetime.datetime.now().isoformat(), "Daily", 1, "Fitness", datetime.datetime.now().isoformat(), "Skipped"),
        (5, "Read 'The Pragmatic Programmer'", "Chapter 3: Basic Tools.", 90, datetime.datetime.now().isoformat(), "None", 2, "Learning", None, "Pending")
    ]

    dummy_tasks = [DummyTask(*data) for data in sample_tasks_data]

    main_frame = bs.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    for i, task_obj in enumerate(dummy_tasks):
        card = TaskCard(main_frame, task_obj)
        card.pack(pady=5, fill=tk.X, expand=True)
        if i == 1: # Example of manually calling select for testing look
            # card.select() # This would require uncommenting select/deselect and _on_click
            pass

    root.mainloop()
