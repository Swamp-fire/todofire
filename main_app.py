import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as bs
import datetime # Keep this, timedelta will be used as datetime.timedelta
from datetime import timedelta # Explicitly import timedelta
import queue
from task_model import Task
import database_manager
from database_manager import check_timeslot_overlap # Ensure this is imported
import scheduler_manager
import logging
from reminder_popup_ui import ReminderPopupUI
from tts_manager import tts_manager
from task_card_ui import TaskCard # Added import
import time
import sys

# Logging level will be set in if __name__ == '__main__'
logger = logging.getLogger(__name__)

class TaskManagerApp:
    # Constants for popup positioning
    POPUP_INITIAL_X = 1530
    POPUP_INITIAL_Y = 200
    POPUP_DEFAULT_WIDTH = 350
    POPUP_DEFAULT_HEIGHT = 85
    POPUP_VERTICAL_GAP = 15
    POPUP_HORIZONTAL_GAP = 15
    POPUP_BOTTOM_MARGIN = 50
    POPUP_LEFT_MARGIN = 10

    def __init__(self, root_window, headless_mode=False):
        self.headless_mode = headless_mode
        self.root = root_window
        self.active_popups = {}

        if not self.headless_mode and self.root:
             # If screen width is needed for POPUP_INITIAL_X, it should be done after root is available
             # Example: TaskManagerApp.POPUP_INITIAL_X = self.root.winfo_screenwidth() - TaskManagerApp.POPUP_DEFAULT_WIDTH - TaskManagerApp.POPUP_HORIZONTAL_GAP
             pass # Using class constant for now
        self.popup_next_x = TaskManagerApp.POPUP_INITIAL_X
        self.popup_next_y = TaskManagerApp.POPUP_INITIAL_Y
        self.current_task_view = "all"

        logger.info(f"Initializing TaskManagerApp in {'HEADLESS' if self.headless_mode else 'GUI'} mode.")

        if not self.headless_mode and self.root:
            self.root.title("Task Manager")
            self.root.geometry("800x700")

        self.currently_editing_task_id = None
        self.input_widgets = {}
        self.task_tree = None # Remains None as Treeview is replaced by card view
        self.selected_card_instance = None # Initialized
        self.selected_task_id_for_card_view = None # Initialized
        self.save_button = None
        self.form_frame = None # Will be initialized in _setup_ui
        self.global_controls_frame = None # Will be initialized in _setup_ui
        self.global_create_task_button = None # Will be initialized in _setup_ui

        # Attributes for the new creation strip values
        self.strip_title_value = tk.StringVar() # Using StringVar for potential binding if needed
        self.strip_description_value = ""
        self.strip_repetition_value = "None"
        self.strip_priority_value = "Medium"
        self.strip_category_value = ""
        self.strip_duration_hours_value = 0
        self.strip_duration_minutes_value = 30 # Default duration
        self.strip_due_date_value = None # Store as string "YYYY-MM-DD" or None
        self.strip_due_hour_value = "12" # Store as string "HH"
        self.strip_due_minute_value = "00" # Store as string "MM"

        # Display labels on the creation strip - will be dynamically created/shown
        self.strip_repetition_display_label = None
        self.strip_due_date_display_label = None
        self.strip_duration_display_label = None
        self.strip_description_display_label = None
        self.strip_priority_display_label = None
        self.strip_category_display_label = None
        self.strip_label_options = {} # Will be populated in _setup_ui

        self.reminder_queue = queue.Queue()
        self.scheduler = None
        self.priority_map_display = {1: "Low", 2: "Medium", 3: "High"}
        self.tree_columns = ("id", "title", "status", "priority", "due_date", "repetition", "duration_display", "category")

        if not self.headless_mode and self.root:
            self._setup_ui()
            self.refresh_task_list()
            self.root.bind('<Control-m>', self.toggle_tts_mute)
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self._check_reminder_queue()
        elif self.headless_mode:
            logger.info("UI setup and UI-based queue polling skipped in HEADLESS mode.")

        logger.info("Initializing scheduler...")
        try:
            self.scheduler = scheduler_manager.initialize_scheduler(self.reminder_queue)
            if self.scheduler:
                logger.info("Scheduler initialized successfully.")
            else:
                logger.error("Scheduler failed to initialize (returned None).")
        except Exception as e:
            logger.error(f"Exception during scheduler initialization: {e}", exc_info=True)

        logger.info("TaskManagerApp initialization complete.")

    def _setup_ui(self):
        if self.headless_mode or not self.root:
            logger.error("_setup_ui called in headless_mode or without root. This should not happen.")
            return

        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=3)

        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=0)
        self.root.rowconfigure(2, weight=1)

        self.side_panel_frame = bs.Frame(self.root, padding=(10, 10), bootstyle="secondary")
        self.side_panel_frame.grid(row=0, column=0, sticky="nswe", rowspan=3, padx=(0,5), pady=0)

        side_panel_title = bs.Label(self.side_panel_frame, text="Task Views", font=("-size 14 -weight bold"), bootstyle="inverse-secondary")
        side_panel_title.pack(pady=(0,10), fill=tk.X)

        btn_all_tasks = bs.Button(
            self.side_panel_frame, text="All Tasks",
            command=lambda: self._handle_menu_selection("all"), bootstyle="primary-outline"
        )
        btn_all_tasks.pack(fill=tk.X, pady=5, padx=5)

        btn_today_tasks = bs.Button(
            self.side_panel_frame, text="Today's Tasks",
            command=lambda: self._handle_menu_selection("today"), bootstyle="primary-outline"
        )
        btn_today_tasks.pack(fill=tk.X, pady=5, padx=5)

        btn_completed_tasks = bs.Button(
            self.side_panel_frame, text="Completed Tasks",
            command=lambda: self._handle_menu_selection("completed"), bootstyle="primary-outline"
        )
        btn_completed_tasks.pack(fill=tk.X, pady=5, padx=5)

        btn_missed_skipped = bs.Button(
            self.side_panel_frame, text="Missing/Skipped",
            command=lambda: self._handle_menu_selection("missed_skipped"), bootstyle="primary-outline"
        )
        btn_missed_skipped.pack(fill=tk.X, pady=5, padx=5)

        btn_reschedule_section = bs.Button(
            self.side_panel_frame, text="Reschedule View",
            command=lambda: self._handle_menu_selection("reschedule_section"), bootstyle="primary-outline"
        )
        btn_reschedule_section.pack(fill=tk.X, pady=5, padx=5)

        # self.global_controls_frame = bs.Frame(self.root, padding=(10, 5))
        # self.global_controls_frame.grid(row=0, column=1, sticky="ew", padx=10, pady=(5,0))

        # self.global_create_task_button = bs.Button(
        #     self.global_controls_frame, text="Create New Task",
        #     command=self._toggle_task_form_visibility, bootstyle="primary"
        # )
        # self.global_create_task_button.pack(side=tk.LEFT)

        # self.form_frame = bs.Frame(self.root, padding=(20, 10))
        # self.form_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
        # self.form_frame.columnconfigure(1, weight=1)
        # self.form_frame.grid_remove()
        # # All widgets previously in self.form_frame are removed along with it.
        # # self.input_widgets will be repurposed or re-evaluated for the new strip.
        # # self.save_button is also removed as it was part of form_frame.

        # The old form_frame was at self.root, row=1, column=1.
        # The task list (tree_container_frame) is at self.root, row=2, column=1.
        # We will place the new creation strip above the task list.

        tree_container_frame = bs.Frame(self.root, padding=(0, 0, 0, 0)) # Adjusted padding
        tree_container_frame.grid(row=1, column=1, rowspan=2, sticky='nsew', padx=10, pady=(5, 10)) # Span row 1 and 2 for new layout
                                                                                                 # pady adjusted for top
        tree_container_frame.columnconfigure(0, weight=1)
        # tree_container_frame.columnconfigure(1, weight=0) # This was for old list_title_label and top_right_actions_frame

        # tree_container_frame.rowconfigure(0, weight=0) # Old: list_title_label and top_right_actions_frame
        tree_container_frame.rowconfigure(0, weight=0) # New: For Creation Strip
        tree_container_frame.rowconfigure(1, weight=0) # New: For list_title_label and top_right_actions_frame
        tree_container_frame.rowconfigure(2, weight=1) # New: For card_list_outer_frame (actual list)


        # --- New Creation Card/Strip ---
        self.creation_strip_frame = bs.Frame(tree_container_frame, padding=(5, 5), bootstyle="light")
        self.creation_strip_frame.grid(row=0, column=0, columnspan=1, sticky='ew', padx=0, pady=(0, 10))

        # Configure self.creation_strip_frame for 2 rows and 4 columns
        # Col 0 (Add Btn / Desc): Fixed size
        self.creation_strip_frame.columnconfigure(0, weight=0)
        # Col 1 (Title / Duration): Fixed size (Title width reduced)
        self.creation_strip_frame.columnconfigure(1, weight=0)
        # Col 2 (Rep / Cat): Expanding
        self.creation_strip_frame.columnconfigure(2, weight=1)
        # Col 3 (Due / Prio): Expanding
        self.creation_strip_frame.columnconfigure(3, weight=1)

        self.creation_strip_frame.rowconfigure(0, weight=0)
        self.creation_strip_frame.rowconfigure(1, weight=0)

        # Common padding for items in the strip grid
        grid_item_padx = (2, 2)
        grid_item_pady = (2, 2)

        # --- Populate Top Row (row 0) ---
        # Add Button
        self.strip_add_button = bs.Button(
            self.creation_strip_frame,
            text="+",
            bootstyle="success",
            command=self._create_task_from_strip,
            width=3 # Keep width small
        )
        self.strip_add_button.grid(row=0, column=0, padx=grid_item_padx, pady=grid_item_pady, sticky="w")

        # Title Entry - Reduced width
        self.strip_title_entry = ttk.Entry(
            self.creation_strip_frame,
            textvariable=self.strip_title_value,
            width=25 # Reduced width for title entry
        )
        self.strip_title_entry.grid(row=0, column=1, padx=grid_item_padx, pady=grid_item_pady, sticky="ew")

        # Style for borderless entry (copied from previous implementation)
        style = ttk.Style() # Ensure style is available
        try:
            style.configure("Borderless.TEntry", borderwidth=-1)
            logger.info("Attempted to configure 'Borderless.TEntry' style for strip_title_entry.")
        except tk.TclError as e_style:
            logger.warning(f"Could not configure 'Borderless.TEntry' effectively: {e_style}. ")
            if "Borderless.TEntry" not in style.theme_names():
                try:
                    style.layout("Borderless.TEntry", style.layout("TEntry"))
                    options_to_copy = {}
                    for option_key in ["background", "foreground", "fieldbackground", "insertcolor", "font", "padding"]:
                        try: options_to_copy[option_key] = style.lookup("TEntry", option_key)
                        except tk.TclError: pass
                    if options_to_copy: style.configure("Borderless.TEntry", **options_to_copy)
                    else: style.configure("Borderless.TEntry")
                except Exception as e_alias: logger.error(f"Failed to create 'Borderless.TEntry' as an alias: {e_alias}")
        self.strip_title_entry.bind("<FocusIn>", self._on_title_focus_in)
        self.strip_title_entry.bind("<FocusOut>", self._on_title_focus_out)
        self._set_title_entry_appearance(focused=False)

        # Change creation_strip_frame to dark
        self.creation_strip_frame.config(bootstyle="dark") # Already created, so config

        # Get the background color and options for dynamic labels (now for dark background)
        temp_styled_frame = bs.Frame(self.creation_strip_frame, bootstyle="dark")
        temp_styled_frame.update_idletasks()
        actual_dark_bg_color = style.lookup(temp_styled_frame.winfo_class(), 'background')
        temp_styled_frame.destroy()
        self.strip_label_options = {"background": actual_dark_bg_color, "borderwidth": 0, "relief": "flat"}

        # Repetition (Top Row, Col 2)
        self.rep_field_frame = bs.Frame(self.creation_strip_frame, bootstyle="dark")
        self.rep_field_frame.grid(row=0, column=2, padx=grid_item_padx, pady=grid_item_pady, sticky="w")
        self.strip_repetition_button = bs.Button(self.rep_field_frame, text="🔁", bootstyle="link", command=self._open_repetition_popup) # Changed to link
        self.strip_repetition_button.pack(side=tk.LEFT, padx=(0,1))
        # Dynamic label self.strip_repetition_display_label managed by _update_or_create_display_label

        # Due Date (Top Row, Col 3)
        self.due_date_field_frame = bs.Frame(self.creation_strip_frame, bootstyle="dark")
        self.due_date_field_frame.grid(row=0, column=3, padx=grid_item_padx, pady=grid_item_pady, sticky="w")
        self.strip_due_date_button = bs.Button(self.due_date_field_frame, text="📅", bootstyle="link", command=self._open_due_date_popup) # Changed to link
        self.strip_due_date_button.pack(side=tk.LEFT, padx=(0,1))
        # Dynamic label self.strip_due_date_display_label

        # --- Sub-Frame for Bottom Row for even spacing ---
        bottom_row_frame = bs.Frame(self.creation_strip_frame, bootstyle="dark")
        bottom_row_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=0, pady=grid_item_pady[1])

        # Configure bottom_row_frame with 4 equal-weight columns
        for i in range(4):
            bottom_row_frame.columnconfigure(i, weight=1)

        # --- Populate Bottom Row (within bottom_row_frame) ---
        # Description (Bottom Row, Col 0 of bottom_row_frame)
        self.desc_field_frame = bs.Frame(bottom_row_frame, bootstyle="dark")
        self.desc_field_frame.grid(row=0, column=0, padx=grid_item_padx, pady=0, sticky="ew")
        self.strip_description_button = bs.Button(self.desc_field_frame, text="📝", bootstyle="link", command=self._open_description_popup) # Changed to link
        self.strip_description_button.pack(side=tk.LEFT, padx=(0,1))
        # Dynamic label self.strip_description_display_label

        # Duration (Bottom Row, Col 1 of bottom_row_frame)
        self.duration_field_frame = bs.Frame(bottom_row_frame, bootstyle="dark")
        self.duration_field_frame.grid(row=0, column=1, padx=grid_item_padx, pady=0, sticky="ew")
        self.strip_duration_button = bs.Button(self.duration_field_frame, text="⏱️", bootstyle="link", command=self._open_duration_popup) # Changed to link
        self.strip_duration_button.pack(side=tk.LEFT, padx=(0,1))
        # Dynamic label self.strip_duration_display_label

        # Category (Bottom Row, Col 2 of bottom_row_frame)
        self.category_field_frame = bs.Frame(bottom_row_frame, bootstyle="dark")
        self.category_field_frame.grid(row=0, column=2, padx=grid_item_padx, pady=0, sticky="ew")
        self.strip_category_button = bs.Button(self.category_field_frame, text="🏷️", bootstyle="link", command=self._open_category_popup) # Changed to link
        self.strip_category_button.pack(side=tk.LEFT, padx=(0,1))
        # Dynamic label self.strip_category_display_label

        # Priority (Bottom Row, Col 3 of bottom_row_frame)
        self.priority_field_frame = bs.Frame(bottom_row_frame, bootstyle="dark")
        self.priority_field_frame.grid(row=0, column=3, padx=grid_item_padx, pady=0, sticky="ew")
        self.strip_priority_button = bs.Button(self.priority_field_frame, text="⭐", bootstyle="link", command=self._open_priority_popup) # Changed to link
        self.strip_priority_button.pack(side=tk.LEFT, padx=(0,1))
        # Dynamic label self.strip_priority_display_label

        # list_title_label and top_right_actions_frame are now in row 1 of tree_container_frame
        list_actions_header_frame = bs.Frame(tree_container_frame)
        list_actions_header_frame.grid(row=1, column=0, columnspan=1, sticky='ew', padx=5, pady=(0,5)) # columnspan changed to 1
        list_actions_header_frame.columnconfigure(0, weight=1) # For title to take available space

        list_title_label = bs.Label(list_actions_header_frame, text="Task List", font=("-size 12 -weight bold"))
        list_title_label.grid(row=0, column=0, sticky='w') # Removed padx, pady from here as parent has padding

        top_right_actions_frame = bs.Frame(list_actions_header_frame)
        top_right_actions_frame.grid(row=0, column=1, sticky='e') # Removed padx, pady

        edit_button = bs.Button(top_right_actions_frame, text="Edit Selected",
                                command=self.load_selected_task_for_edit, bootstyle="info")
        edit_button.pack(side=tk.LEFT, padx=(0, 5))

        delete_button = bs.Button(top_right_actions_frame, text="Delete Selected",
                                  command=self.delete_selected_task, bootstyle="danger")
        delete_button.pack(side=tk.LEFT, padx=(0, 5)) # Original had (0,5)

        self.card_list_outer_frame = bs.Frame(tree_container_frame)
        self.card_list_outer_frame.grid(row=2, column=0, columnspan=1, sticky='nsew', padx=5, pady=10) # Corrected columnspan

        # Duplicated block (lines 284-296) and Redefinition block (lines 298-299) are removed by this diff.

        self.card_list_outer_frame.rowconfigure(0, weight=1)
        self.card_list_outer_frame.columnconfigure(0, weight=1)

        self.task_list_canvas = bs.Canvas(self.card_list_outer_frame)
        self.task_list_canvas.grid(row=0, column=0, sticky='nsew')

        self.task_list_scrollbar = bs.Scrollbar(self.card_list_outer_frame, orient=tk.VERTICAL, command=self.task_list_canvas.yview)
        self.task_list_scrollbar.grid(row=0, column=1, sticky='ns')

        self.task_list_canvas.configure(yscrollcommand=self.task_list_scrollbar.set)

        self.cards_frame = bs.Frame(self.task_list_canvas)
        # REMOVED Diagnostic background color for self.cards_frame

        self.task_list_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw", tags="self.cards_frame")

        self.cards_frame.bind("<Configure>", self._on_cards_frame_configure) # This updates scrollregion

        # Ensure the frame within the canvas resizes with the canvas width
        def _on_canvas_configure(event):
            canvas_width = event.width
            # Check if canvas and cards_frame exist to prevent errors during setup/teardown
            if hasattr(self, 'task_list_canvas') and self.task_list_canvas.winfo_exists() and \
               hasattr(self, 'cards_frame') and self.cards_frame.winfo_exists():
                self.task_list_canvas.itemconfig("self.cards_frame", width=canvas_width)

        self.task_list_canvas.bind("<Configure>", _on_canvas_configure)

        self.task_list_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.task_list_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.task_list_canvas.bind_all("<Button-5>", self._on_mousewheel)

        self.task_tree = None # Remains None as Treeview is replaced by card view

    def _on_cards_frame_configure(self, event=None):
        if hasattr(self, 'task_list_canvas') and self.task_list_canvas.winfo_exists() and \
           hasattr(self, 'cards_frame') and self.cards_frame.winfo_exists():
            self.task_list_canvas.configure(scrollregion=self.task_list_canvas.bbox("all"))
        else:
            logger.debug("_on_cards_frame_configure: Canvas or cards_frame not ready.")

    def _on_mousewheel(self, event):
        if hasattr(self, 'task_list_canvas') and self.task_list_canvas.winfo_exists():
            widget_under_mouse = event.widget
            is_related_to_canvas = False
            try:
                if widget_under_mouse == self.task_list_canvas: is_related_to_canvas = True
                else:
                    parent = widget_under_mouse
                    while parent is not None:
                        if parent == self.cards_frame:
                            is_related_to_canvas = True; break
                        parent = parent.master
            except tk.TclError: is_related_to_canvas = False
            if not is_related_to_canvas: pass # Explicitly do nothing if not related

            if event.delta: # For Windows and macOS (wheel scroll)
                self.task_list_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            elif event.num == 4: # For Linux (scroll up)
                self.task_list_canvas.yview_scroll(-1, "units")
            elif event.num == 5: # For Linux (scroll down)
                self.task_list_canvas.yview_scroll(1, "units")
        else:
            logger.debug("_on_mousewheel: task_list_canvas not ready.")

    # def _toggle_task_form_visibility(self):
        # This method is no longer needed as the creation strip is always visible.
        # if not hasattr(self, 'form_frame'):
        #     logger.error("Task creation form (self.form_frame) not found."); return
        # if not hasattr(self, 'global_create_task_button'):
        #     logger.error("Global create task button (self.global_create_task_button) not found.")

        # if self.form_frame.winfo_ismapped():
        #     self.form_frame.grid_remove()
        #     if hasattr(self, 'global_create_task_button'):
        #         self.global_create_task_button.config(text="Create New Task")
        #     logger.info("Task creation form hidden.")
        # else:
        #     self.form_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
        #     self.clear_form_fields_and_reset_state() # This would now target strip inputs
        #     if hasattr(self, 'global_create_task_button'):
        #         self.global_create_task_button.config(text="Hide Task Form")
        #     logger.info("Task creation form shown.")
            # Focus logic would also need to target the new title entry in the strip
            # if hasattr(self, 'input_widgets') and 'title' in self.input_widgets and \
            #    hasattr(self.input_widgets['title'], 'focus_set'):
            #     self.input_widgets['title'].focus_set()
            # else: logger.warning("Could not set focus to title widget on form show.")

    def clear_form_fields_and_reset_state(self): # Will be adapted for the new strip later
        if self.headless_mode:
            self.currently_editing_task_id = None
            logger.info("Form fields state reset (headless mode)."); return

        # --- Old form clearing logic - To be replaced ---
        # self.input_widgets['title'].delete(0, tk.END)
        # self.input_widgets['description'].delete("1.0", tk.END)
        # self.input_widgets['repetition'].set('None')
        # self.input_widgets['priority'].set('Medium')
        # self.input_widgets['category'].delete(0, tk.END)
        # if 'duration_hours' in self.input_widgets:
        #     self.input_widgets['duration_hours'].set(0)
        #     self.input_widgets['duration_minutes'].set(30)
        # if 'due_date' in self.input_widgets:
        #     self.input_widgets['due_date'].entry.delete(0, tk.END)
        #     self.input_widgets['due_hour'].set("12")
        #     self.input_widgets['due_minute'].set("00")
        # self.currently_editing_task_id = None
        # if self.save_button: self.save_button.config(text="Save Task") # self.save_button removed
        logger.info("Form fields cleared and state reset (pending strip implementation).")
        # For now, just reset editing ID
        self.currently_editing_task_id = None
        # Placeholder for new strip input clearing
        if hasattr(self, 'strip_title_entry'):
            self.strip_title_entry.delete(0, tk.END)
        # Reset other strip-related temporary variables (to be defined later)
        self.strip_description_value = ""
        self.strip_repetition_value = "None"
        self.strip_priority_value = "Medium"
        self.strip_category_value = ""
        self.strip_duration_hours_value = 0
        self.strip_duration_minutes_value = 30 # Default duration
        self.strip_due_date_value = None
        self.strip_due_hour_value = "12"
        self.strip_due_minute_value = "00"

        # Clear/hide display labels on the strip using the helper function
        # The formatting functions will return "" if the underlying value is default/None,
        # and _update_or_create_display_label will hide the label if text_to_display is empty.
        self._update_or_create_display_label("strip_repetition_display_label", self.rep_field_frame, "", self.strip_repetition_button)
        self._update_or_create_display_label("strip_due_date_display_label", self.due_date_field_frame, "", self.strip_due_date_button)
        self._update_or_create_display_label("strip_duration_display_label", self.duration_field_frame, "", self.strip_duration_button)
        self._update_or_create_display_label("strip_description_display_label", self.desc_field_frame, "", self.strip_description_button)
        self._update_or_create_display_label("strip_priority_display_label", self.priority_field_frame, "", self.strip_priority_button)
        self._update_or_create_display_label("strip_category_display_label", self.category_field_frame, "", self.strip_category_button)


    def load_selected_task_for_edit(self):
        # if not self.headless_mode and self.form_frame and not self.form_frame.winfo_ismapped():
        #     # Ensure the form is shown with correct grid options
        #     self.form_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
        #     if hasattr(self, 'global_create_task_button'):
        #          self.global_create_task_button.config(text="Hide Task Form")
        # The above is removed as self.form_frame and self.global_create_task_button are gone.
        # Editing will now likely populate the temporary strip variables and perhaps change the "Add" button to "Update"
        # or rely on a separate "Update" button if the "Edit Selected" button is kept.
        # For now, this method will fetch the task and store its ID.
        # The actual population of input fields will be handled differently with popups.

        if self.headless_mode:
            logger.warning("load_selected_task_for_edit called in headless_mode. UI not available.")
            return

        if self.selected_task_id_for_card_view is None:
            try:
                messagebox.showwarning("No Selection", "Please select a task from the list to edit.", parent=self.root)
            except tk.TclError:
                logger.warning("No task selected for editing (messagebox not available).")
            return

        task_id = self.selected_task_id_for_card_view
        logger.info(f"Loading task ID {task_id} for edit (selected from card view).")

        # Storing the task ID for editing.
        self.currently_editing_task_id = task_id

        # We can't populate a form that doesn't exist.
        # Instead, when the user clicks "Edit", we could:
        # 1. Fetch the task data.
        # 2. Populate the strip's title entry directly.
        # 3. Store the other task attributes in the `self.strip_..._value` variables.
        # 4. Change the "Add" button on the strip to an "Update" button.
        # This logic will be more complex and will be part of step 4 or 5.
        # For now, just log that we're "editing" and let save_task_action handle it.

        conn = None
        try:
            conn = database_manager.create_connection()
            if not conn:
                logger.error("DB Error: Could not connect (messagebox not available).")
                if not self.headless_mode: messagebox.showerror("Database Error", "Could not connect to the database.", parent=self.root)
                return

            task_to_edit = database_manager.get_task(conn, task_id)
            if not task_to_edit:
                logger.error(f"Error retrieving task ID {task_id} (messagebox not available).")
                if not self.headless_mode: messagebox.showerror("Error", f"Could not retrieve task with ID: {task_id}", parent=self.root)
                return

            # Populate strip variables directly (these will be used by popups and the save action)
            if hasattr(self, 'strip_title_entry'):
                self.strip_title_entry.delete(0, tk.END)
                self.strip_title_entry.insert(0, task_to_edit.title)
            else: # Fallback if strip_title_entry isn't ready (should be)
                self.strip_title_value = task_to_edit.title # Assuming self.strip_title_value exists

            self.strip_description_value = task_to_edit.description
            total_minutes = task_to_edit.duration if task_to_edit.duration is not None else 0
            self.strip_duration_hours_value = total_minutes // 60
            self.strip_duration_minutes_value = total_minutes % 60
            self.strip_category_value = task_to_edit.category
            self.strip_repetition_value = task_to_edit.repetition if task_to_edit.repetition else 'None'
            self.strip_priority_value = self.priority_map_display.get(task_to_edit.priority, "Medium")

            if task_to_edit.due_date:
                try:
                    dt_obj = datetime.datetime.fromisoformat(task_to_edit.due_date)
                    self.strip_due_date_value = dt_obj.strftime("%Y-%m-%d")
                    self.strip_due_hour_value = dt_obj.strftime("%H")
                    minute_val = int(dt_obj.strftime("%M"))
                    self.strip_due_minute_value = f"{(minute_val // 5) * 5:02d}"
                except ValueError:
                    self.strip_due_date_value = None
                    self.strip_due_hour_value = "12"
                    self.strip_due_minute_value = "00"
            else:
                self.strip_due_date_value = None
                self.strip_due_hour_value = "12"
                self.strip_due_minute_value = "00"

            # If an "Add" button exists on the strip, change its text to "Update Task"
            if hasattr(self, 'strip_add_button'):
                 self.strip_add_button.config(text="Update Task")
            logger.info(f"Editing task ID: {self.currently_editing_task_id}. Strip values populated.")

            if hasattr(self, 'strip_title_entry') and hasattr(self.strip_title_entry, 'focus_set'):
                 self.strip_title_entry.focus_set()

            # Update/create display labels on the strip using the helper function
            self._update_or_create_display_label("strip_repetition_display_label", self.rep_field_frame, self._format_display_repetition(), self.strip_repetition_button)
            self._update_or_create_display_label("strip_due_date_display_label", self.due_date_field_frame, self._format_display_due_date(), self.strip_due_date_button)
            self._update_or_create_display_label("strip_duration_display_label", self.duration_field_frame, self._format_display_duration(), self.strip_duration_button)
            self._update_or_create_display_label("strip_description_display_label", self.desc_field_frame, self._format_display_description(), self.strip_description_button)
            self._update_or_create_display_label("strip_priority_display_label", self.priority_field_frame, self._format_display_priority(), self.strip_priority_button)
            self._update_or_create_display_label("strip_category_display_label", self.category_field_frame, self._format_display_category(), self.strip_category_button)

        except Exception as e:
            error_msg = f"Failed to load task for editing into strip: {e}"
            logger.error(f"Error in load_selected_task_for_edit: {e}", exc_info=True)
            if not self.headless_mode: messagebox.showerror("Error", error_msg, parent=self.root)
        finally:
            if conn: conn.close()

    def _set_title_entry_appearance(self, focused: bool):
        if not hasattr(self, 'strip_title_entry') or not self.strip_title_entry:
            return

        is_empty = not self.strip_title_entry.get()

        if focused:
            # Revert to the default 'TEntry' style, which usually indicates focus.
            try:
                if self.strip_title_entry.cget("style") != "TEntry":
                    self.strip_title_entry.configure(style="TEntry")
            except tk.TclError:
                logger.warning("Could not apply default 'TEntry' style to strip_title_entry on focus.")
        else: # Not focused
            if is_empty:
                # Try to apply "Borderless.TEntry" for the empty, unfocused state.
                try:
                    if self.strip_title_entry.cget("style") != "Borderless.TEntry":
                        self.strip_title_entry.configure(style="Borderless.TEntry")
                except tk.TclError:
                    logger.warning("Style 'Borderless.TEntry' could not be applied. Using default 'TEntry'.")
                    try:
                        if self.strip_title_entry.cget("style") != "TEntry":
                            self.strip_title_entry.configure(style="TEntry")
                    except tk.TclError:
                        logger.warning("Could not apply default 'TEntry' style as fallback for borderless.")
            else: # Not focused, but has text - should use default style.
                try:
                    if self.strip_title_entry.cget("style") != "TEntry":
                        self.strip_title_entry.configure(style="TEntry")
                except tk.TclError:
                    logger.warning("Could not apply default 'TEntry' style for non-empty unfocused entry.")


    def _on_title_focus_in(self, event=None):
        self._set_title_entry_appearance(focused=True)

    def _on_title_focus_out(self, event=None):
        self._set_title_entry_appearance(focused=False)

    def _open_repetition_popup(self):
        popup = bs.Toplevel(master=self.root, title="Set Repetition") # Explicitly set master
        popup.transient(self.root) # Keep popup on top of the main window
        popup.grab_set() # Modal behavior
        popup.geometry("300x150") # Adjust size as needed

        label = bs.Label(popup, text="Select repetition cycle:")
        label.pack(pady=10)

        repetition_values = ['None', 'Daily', 'Weekly', 'Monthly', 'Yearly']
        combo = ttk.Combobox(popup, values=repetition_values, state="readonly")
        current_repetition = self.strip_repetition_value if self.strip_repetition_value in repetition_values else 'None'
        combo.set(current_repetition)
        combo.pack(pady=5, padx=20, fill=tk.X)

        def on_save():
            self.strip_repetition_value = combo.get()
            logger.info(f"Repetition set to: {self.strip_repetition_value}")
            # Use the new helper to update/create the display label
            self._update_or_create_display_label(
                label_attr_name="strip_repetition_display_label",
                parent_frame=self.rep_field_frame,
                text_to_display=self._format_display_repetition(),
                icon_button_widget=self.strip_repetition_button
            )
            popup.destroy()

        def on_cancel():
            popup.destroy()

        button_frame = bs.Frame(popup)
        button_frame.pack(pady=10)

        save_btn = bs.Button(button_frame, text="Save", command=on_save, bootstyle="success")
        save_btn.pack(side=tk.LEFT, padx=5)

        cancel_btn = bs.Button(button_frame, text="Cancel", command=on_cancel, bootstyle="secondary")
        cancel_btn.pack(side=tk.LEFT, padx=5)

        # Center the popup relative to the root window
        popup.update_idletasks() # Ensure dimensions are calculated
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()
        x = root_x + (root_width // 2) - (popup_width // 2)
        y = root_y + (root_height // 2) - (popup_height // 2)
        popup.geometry(f'+{x}+{y}')

    def _open_due_date_popup(self):
        popup = bs.Toplevel(master=self.root, title="Set Due Date & Time") # Explicitly set master
        popup.transient(self.root)
        popup.grab_set()
        # popup.geometry("350x250") # Adjust size as needed

        # Due Date
        date_frame = bs.Frame(popup, padding=5)
        date_frame.pack(fill=tk.X)
        bs.Label(date_frame, text="Due Date:").pack(side=tk.LEFT, padx=(0,5))
        date_entry = bs.DateEntry(date_frame, dateformat="%Y-%m-%d", firstweekday=0)
        if self.strip_due_date_value:
            try:
                # Ensure the date_entry is populated correctly if a value exists
                datetime.datetime.strptime(self.strip_due_date_value, "%Y-%m-%d") # Validate format
                date_entry.entry.delete(0, tk.END)
                date_entry.entry.insert(0, self.strip_due_date_value)
            except ValueError:
                logger.warning(f"Invalid stored due date '{self.strip_due_date_value}', using current date for popup.")
                # Let DateEntry default to today or clear it if that's preferred
                date_entry.entry.delete(0, tk.END) # Clear if invalid
        date_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)


        # Due Time
        time_frame = bs.Frame(popup, padding=5)
        time_frame.pack(fill=tk.X)
        bs.Label(time_frame, text="Due Time:").pack(side=tk.LEFT, padx=(0,5))

        hour_combo = ttk.Combobox(time_frame, state="readonly", width=5, values=[f"{h:02d}" for h in range(24)])
        hour_combo.set(self.strip_due_hour_value if self.strip_due_hour_value else "12")
        hour_combo.pack(side=tk.LEFT)

        bs.Label(time_frame, text=":").pack(side=tk.LEFT)

        minute_combo = ttk.Combobox(time_frame, state="readonly", width=5, values=[f"{m:02d}" for m in range(0, 60, 5)])
        minute_combo.set(self.strip_due_minute_value if self.strip_due_minute_value else "00")
        minute_combo.pack(side=tk.LEFT)

        # Optional: "No Due Date" button
        def on_clear_due_date():
            self.strip_due_date_value = None
            self.strip_due_hour_value = "12" # Reset time too or leave as is?
            self.strip_due_minute_value = "00"
            logger.info("Due Date & Time cleared.")
            popup.destroy()

        clear_btn_frame = bs.Frame(popup, padding=(5,0,5,5)) # Add padding to separate from time_frame
        clear_btn_frame.pack(fill=tk.X)
        clear_due_date_btn = bs.Button(clear_btn_frame, text="No Due Date", command=on_clear_due_date, bootstyle="lightoutline")
        clear_due_date_btn.pack(side=tk.LEFT, pady=(5,0))


        def on_save():
            selected_date = date_entry.entry.get()
            if not selected_date: # Handle case where date entry might be empty
                if not self.headless_mode:
                    messagebox.showwarning("Missing Date", "Please select a due date or choose 'No Due Date'.", parent=popup)
                else:
                    logger.warning("Due date save attempted with empty date field.")
                return

            self.strip_due_date_value = selected_date
            self.strip_due_hour_value = hour_combo.get()
            self.strip_due_minute_value = minute_combo.get()
            logger.info(f"Due Date set to: {self.strip_due_date_value} {self.strip_due_hour_value}:{self.strip_due_minute_value}")
            self._update_or_create_display_label(
                label_attr_name="strip_due_date_display_label",
                parent_frame=self.due_date_field_frame,
                text_to_display=self._format_display_due_date(),
                icon_button_widget=self.strip_due_date_button
            )
            popup.destroy()

        def on_cancel():
            popup.destroy()

        # Optional: "No Due Date" button needs to update display label too
        def on_clear_due_date():
            self.strip_due_date_value = None
            # Reset time values as well for consistency, though format_display will handle None date
            self.strip_due_hour_value = "12"
            self.strip_due_minute_value = "00"
            logger.info("Due Date & Time cleared.")
            self._update_or_create_display_label(
                label_attr_name="strip_due_date_display_label",
                parent_frame=self.due_date_field_frame,
                text_to_display=self._format_display_due_date(), # Will return ""
                icon_button_widget=self.strip_due_date_button
            )
            popup.destroy()

        clear_btn_frame = bs.Frame(popup, padding=(5,0,5,5))
        clear_btn_frame.pack(fill=tk.X)
        clear_due_date_btn = bs.Button(clear_btn_frame, text="No Due Date", command=on_clear_due_date, bootstyle="lightoutline")
        clear_due_date_btn.pack(side=tk.LEFT, pady=(5,0))

        button_frame = bs.Frame(popup, padding=5)
        button_frame.pack(fill=tk.X, pady=(5,0)) # pady to give some space from content above

        save_btn = bs.Button(button_frame, text="Save", command=on_save, bootstyle="success")
        save_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        cancel_btn = bs.Button(button_frame, text="Cancel", command=on_cancel, bootstyle="secondary")
        cancel_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        popup.update_idletasks()
        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()
        # print(f"DueDate Popup dimensions: {popup_width}x{popup_height}") # For debugging size
        # popup.geometry(f"{popup_width}x{popup_height}") # Resize to fit content, might be redundant if packing is good

        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        x = root_x + (root_width // 2) - (popup_width // 2)
        y = root_y + (root_height // 2) - (popup_height // 2)
        popup.geometry(f'+{x}+{y}')

    def _open_duration_popup(self):
        popup = bs.Toplevel(master=self.root, title="Set Duration") # Explicitly set master
        popup.transient(self.root)
        popup.grab_set()
        # popup.geometry("300x200") # Adjust as needed

        label = bs.Label(popup, text="Set task duration (hours and minutes):")
        label.pack(pady=10, padx=10, fill=tk.X)

        duration_frame = bs.Frame(popup, padding=10)
        duration_frame.pack(fill=tk.BOTH, expand=True)

        # Hours
        bs.Label(duration_frame, text="Hours:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        hours_spinbox = ttk.Spinbox(duration_frame, from_=0, to=99, width=5)
        hours_spinbox.set(self.strip_duration_hours_value)
        hours_spinbox.grid(row=0, column=1, padx=5, pady=5)

        # Minutes
        bs.Label(duration_frame, text="Minutes:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        minutes_spinbox = ttk.Spinbox(duration_frame, from_=0, to=55, increment=5, width=5)
        minutes_spinbox.set(self.strip_duration_minutes_value)
        minutes_spinbox.grid(row=1, column=1, padx=5, pady=5)

        def on_save():
            try:
                hours = int(hours_spinbox.get())
                minutes = int(minutes_spinbox.get())

                if not (0 <= hours <= 99):
                    messagebox.showerror("Invalid Hours", "Hours must be between 0 and 99.", parent=popup)
                    return
                if not (0 <= minutes <= 59): # Max 59, typically to 55 for 5-min increments
                    messagebox.showerror("Invalid Minutes", "Minutes must be between 0 and 59.", parent=popup)
                    return

                self.strip_duration_hours_value = hours
                self.strip_duration_minutes_value = minutes
                logger.info(f"Duration set to: {hours}h {minutes}m")
                self._update_or_create_display_label(
                    label_attr_name="strip_duration_display_label",
                    parent_frame=self.duration_field_frame,
                    text_to_display=self._format_display_duration(),
                    icon_button_widget=self.strip_duration_button
                )
                popup.destroy()
            except ValueError:
                messagebox.showerror("Invalid Input", "Hours and minutes must be numbers.", parent=popup)
            except tk.TclError as e: # Could happen if spinbox value is invalid during get()
                messagebox.showerror("Invalid Input", f"Error reading duration values: {e}", parent=popup)


        def on_cancel():
            popup.destroy()

        button_frame = bs.Frame(popup, padding=10)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM) # Place buttons at the bottom

        save_btn = bs.Button(button_frame, text="Save", command=on_save, bootstyle="success")
        save_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        cancel_btn = bs.Button(button_frame, text="Cancel", command=on_cancel, bootstyle="secondary")
        cancel_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        popup.update_idletasks()
        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        x = root_x + (root_width // 2) - (popup_width // 2)
        y = root_y + (root_height // 2) - (popup_height // 2)
        popup.geometry(f'+{x}+{y}')

    def _open_description_popup(self):
        popup = bs.Toplevel(master=self.root, title="Set Description") # Explicitly set master
        popup.transient(self.root)
        popup.grab_set()
        popup.geometry("400x300") # Adjust as needed

        label = bs.Label(popup, text="Enter task description:")
        label.pack(pady=(10,0), padx=10, anchor="w")

        text_area_frame = bs.Frame(popup, padding=10)
        text_area_frame.pack(fill=tk.BOTH, expand=True)

        desc_text = tk.Text(text_area_frame, height=10, width=40, wrap=tk.WORD)
        # Add a scrollbar
        scrollbar = ttk.Scrollbar(text_area_frame, orient=tk.VERTICAL, command=desc_text.yview)
        desc_text.configure(yscrollcommand=scrollbar.set)

        desc_text.insert("1.0", self.strip_description_value if self.strip_description_value else "")

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        desc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        desc_text.focus_set()


        def on_save():
            self.strip_description_value = desc_text.get("1.0", tk.END).strip()
            logger.info(f"Description set (length: {len(self.strip_description_value)})")
            self._update_or_create_display_label(
                label_attr_name="strip_description_display_label",
                parent_frame=self.desc_field_frame,
                text_to_display=self._format_display_description(),
                icon_button_widget=self.strip_description_button
            )
            popup.destroy()

        def on_cancel():
            popup.destroy()

        button_frame = bs.Frame(popup, padding=10)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        save_btn = bs.Button(button_frame, text="Save", command=on_save, bootstyle="success")
        save_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        cancel_btn = bs.Button(button_frame, text="Cancel", command=on_cancel, bootstyle="secondary")
        cancel_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        popup.update_idletasks()
        # Recalculate position after content might have changed size
        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        x = root_x + (root_width // 2) - (popup_width // 2)
        y = root_y + (root_height // 2) - (popup_height // 2)
        popup.geometry(f'{popup_width}x{popup_height}+{x}+{y}') # Ensure size is also set

    def _open_priority_popup(self):
        popup = bs.Toplevel(master=self.root, title="Set Priority") # Explicitly set master
        popup.transient(self.root)
        popup.grab_set()
        popup.geometry("300x150") # Adjust as needed

            # Ensuring label and category_entry are defined correctly within the try block
        label = bs.Label(popup, text="Select task priority:")
        label.pack(pady=10)

        priority_values = list(self.priority_map_display.values()) # ['Low', 'Medium', 'High']
        combo = ttk.Combobox(popup, values=priority_values, state="readonly")

        current_priority_display = self.strip_priority_value
        if current_priority_display not in priority_values:
            # If self.strip_priority_value was stored as number (e.g. from old system or direct DB model)
            # try to map it, otherwise default.
            # For now, assume strip_priority_value is already display string like "Medium"
            current_priority_display = "Medium" # Default if not valid

        combo.set(current_priority_display if current_priority_display in priority_values else "Medium")
        combo.pack(pady=5, padx=20, fill=tk.X)

        def on_save():
            self.strip_priority_value = combo.get() # This is the display string e.g. "Medium"
            logger.info(f"Priority set to: {self.strip_priority_value}")
            self._update_or_create_display_label(
                label_attr_name="strip_priority_display_label",
                parent_frame=self.priority_field_frame,
                text_to_display=self._format_display_priority(),
                icon_button_widget=self.strip_priority_button
            )
            popup.destroy()

        def on_cancel():
            popup.destroy()

        button_frame = bs.Frame(popup)
        button_frame.pack(pady=10)

        save_btn = bs.Button(button_frame, text="Save", command=on_save, bootstyle="success")
        save_btn.pack(side=tk.LEFT, padx=5)

        cancel_btn = bs.Button(button_frame, text="Cancel", command=on_cancel, bootstyle="secondary")
        cancel_btn.pack(side=tk.LEFT, padx=5)

        popup.update_idletasks()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()
        x = root_x + (root_width // 2) - (popup_width // 2)
        y = root_y + (root_height // 2) - (popup_height // 2)
        popup.geometry(f'+{x}+{y}')

    def _open_category_popup(self):
        try:
            logger.debug("Attempting to open category popup...")
            popup = bs.Toplevel(master=self.root, title="Set Category")
            popup.transient(self.root)
            popup.grab_set()
            popup.geometry("300x150")

            label = bs.Label(popup, text="Enter task category:")
            label.pack(pady=10)

            category_entry = ttk.Entry(popup, width=30)
            category_entry.insert(0, self.strip_category_value if self.strip_category_value else "")
            category_entry.pack(pady=5, padx=20, fill=tk.X)
            category_entry.focus_set()

            # Define the save action handler
            def on_save_popup_action(event=None):
                self._save_category_popup(category_entry, popup)

            category_entry.bind("<Return>", on_save_popup_action)

            # Define cancel action
            def on_cancel_popup_action():
                popup.destroy()

            button_frame = bs.Frame(popup)
            button_frame.pack(pady=10)

            save_btn = bs.Button(button_frame, text="Save", command=on_save_popup_action, bootstyle="success")
            save_btn.pack(side=tk.LEFT, padx=5)

            cancel_btn = bs.Button(button_frame, text="Cancel", command=on_cancel_popup_action, bootstyle="secondary")
            cancel_btn.pack(side=tk.LEFT, padx=5)

            popup.update_idletasks()
            root_x = self.root.winfo_x()
            root_y = self.root.winfo_y()
            root_width = self.root.winfo_width()
            root_height = self.root.winfo_height()
            popup_width = popup.winfo_width()
            popup_height = popup.winfo_height()
            x = root_x + (root_width // 2) - (popup_width // 2)
            y = root_y + (root_height // 2) - (popup_height // 2)
            popup.geometry(f'+{x}+{y}')
            logger.debug("Category popup configured and should be visible.")

        except Exception as e:
            logger.error(f"Error in _open_category_popup: {e}", exc_info=True)
            if not self.headless_mode:
                parent_for_error = self.root if self.root and hasattr(self.root, 'winfo_exists') and self.root.winfo_exists() else None
                messagebox.showerror("Popup Error", f"Could not open category popup: {e}", parent=parent_for_error)

    def _save_category_popup(self, entry_widget, popup_window):
        """Helper method to save category from popup."""
        try:
            self.strip_category_value = entry_widget.get().strip()
            logger.info(f"Category set to: {self.strip_category_value}")
            self._update_or_create_display_label(
                label_attr_name="strip_category_display_label",
                parent_frame=self.category_field_frame,
                text_to_display=self._format_display_category(),
                icon_button_widget=self.strip_category_button
            )
        except Exception as e:
            logger.error(f"Error getting value in _save_category_popup: {e}", exc_info=True)
            if hasattr(popup_window, 'winfo_exists') and popup_window.winfo_exists():
                 if not self.headless_mode:
                      messagebox.showerror("Save Error", f"Could not retrieve category value: {e}", parent=popup_window)
                 return
        finally:
            if hasattr(popup_window, 'destroy'):
                popup_window.destroy()


    # _open_placeholder_popup is no longer needed as all icon buttons now have specific popups.
    # def _open_placeholder_popup(self, field_name: str):
    #     # This is a placeholder for Step 3 where real popups will be implemented
    #     logger.info(f"Placeholder: Open popup for {field_name}")
    #     if not self.headless_mode:
    #         # Using simpledialog for now as a temporary measure.
    #         # This will be replaced by custom Toplevel popups.
    #         from tkinter import simpledialog
    #         value = simpledialog.askstring(f"Input for {field_name}", f"Enter {field_name}:", parent=self.root)
    #         if value is not None:
    #             logger.info(f"Placeholder: {field_name} set to '{value}'")
    #             # Here, you would store this value in the corresponding self.strip_..._value attribute
    #             if field_name == "Repetition": self.strip_repetition_value = value
    #             elif field_name == "Due Date": self.strip_due_date_value = value # This will need proper parsing
    #             elif field_name == "Duration": pass # This will need hours/minutes parsing
    #             elif field_name == "Description": self.strip_description_value = value
    #             elif field_name == "Priority": self.strip_priority_value = value
    #             elif field_name == "Category": self.strip_category_value = value
    #         else:
    #             logger.info(f"Placeholder: {field_name} input cancelled.")
    #     # This is a placeholder for Step 3 where real popups will be implemented
    #     logger.info(f"Placeholder: Open popup for {field_name}")
    #     if not self.headless_mode:
    #         # Using simpledialog for now as a temporary measure.
    #         # This will be replaced by custom Toplevel popups.
    #         from tkinter import simpledialog
    #         value = simpledialog.askstring(f"Input for {field_name}", f"Enter {field_name}:", parent=self.root)
    #         if value is not None:
    #             logger.info(f"Placeholder: {field_name} set to '{value}'")
    #             # Here, you would store this value in the corresponding self.strip_..._value attribute
    #             if field_name == "Repetition": self.strip_repetition_value = value
    #             elif field_name == "Due Date": self.strip_due_date_value = value # This will need proper parsing
    #             elif field_name == "Duration": pass # This will need hours/minutes parsing
    #             elif field_name == "Description": self.strip_description_value = value
    #             elif field_name == "Priority": self.strip_priority_value = value
    #             elif field_name == "Category": self.strip_category_value = value
    #         else:
    #             logger.info(f"Placeholder: {field_name} input cancelled.")


    def _create_task_from_strip(self):
        if self.headless_mode: # Should not be callable via UI in headless but good check
            logger.error("_create_task_from_strip called in headless_mode. Aborting.")
            return

        title_value = self.strip_title_entry.get().strip()
        if not title_value:
            messagebox.showerror("Validation Error", "Title field cannot be empty.", parent=self.root)
            return

        # Retrieve values from strip attributes
        description = self.strip_description_value
        current_task_repetition = self.strip_repetition_value
        priority_str = self.strip_priority_value # This is display string like "Medium"
        category = self.strip_category_value

        try:
            hours = int(self.strip_duration_hours_value)
            minutes = int(self.strip_duration_minutes_value)
            if not (0 <= hours <= 99):
                messagebox.showerror("Invalid Duration", "Hours must be between 0 and 99.", parent=self.root)
                return
            if not (0 <= minutes <= 59):
                 messagebox.showerror("Invalid Duration", "Minutes must be between 0 and 59.", parent=self.root)
                 return
            task_duration_total_minutes = (hours * 60) + minutes
        except ValueError:
            messagebox.showerror("Invalid Duration", "Duration hours and minutes must be numbers.", parent=self.root)
            return

        due_date_str = self.strip_due_date_value # Already "YYYY-MM-DD" or None
        due_hour_str = self.strip_due_hour_value # Already "HH"
        due_minute_str = self.strip_due_minute_value # Already "MM"
        task_due_datetime_iso = None

        # Due date and time validation:
        # If a due date is provided, time must also be provided.
        if due_date_str:
            if not due_hour_str or not due_minute_str: # Should not happen if popups work correctly
                messagebox.showerror("Missing Time", "If Due Date is set, Due Time (HH:MM) must also be selected.", parent=self.root)
                return
            try:
                dt_obj = datetime.datetime.strptime(f"{due_date_str} {due_hour_str}:{due_minute_str}", "%Y-%m-%d %H:%M")
                task_due_datetime_iso = dt_obj.isoformat()
            except ValueError:
                messagebox.showerror("Invalid Date/Time", "Due Date or Time is not valid. Please use YYYY-MM-DD format for date and select HH:MM for time.", parent=self.root)
                return
        # If due_date_str is None, task_due_datetime_iso remains None (task has no due date)

        # If task has duration but no due date, it's a "floating" task, conflict check is not applicable in the same way.
        # The original code required a due date if duration > 0. We might want to keep that.
        # For now, let's assume a task can have duration without a due date.
        # If a due date is NOT set, but duration IS set, it's a "floating task with duration".
        # If a due date IS set, and duration IS set, then conflict checking applies.
        if not task_due_datetime_iso and task_duration_total_minutes > 0:
            # This is a floating task with a duration but no specific due date/time.
            # Original logic would require a due date here.
            # For now, we allow this. Conflict check is skipped.
            logger.info(f"Task '{title_value}' has duration but no due date. Skipping conflict check.")
            pass


        # Conflict Checking (adapted from save_task_action)
        if task_duration_total_minutes > 0 and task_due_datetime_iso:
            perf_start_conflict_check_section = time.perf_counter()
            logger.debug(f"Conflict Check Perf: Entering conflict check section at {perf_start_conflict_check_section:.4f}")
            try:
                ct_start_dt = datetime.datetime.fromisoformat(task_due_datetime_iso)
                ct_end_dt = ct_start_dt + timedelta(minutes=task_duration_total_minutes)
                logger.info(f"Conflict Check initiated for '{title_value}' slot: {ct_start_dt} to {ct_end_dt}")
                conn_check = None
                try:
                    conn_check = database_manager.create_connection()
                    if not conn_check:
                        logger.error("DB Error: Cannot check for task conflicts: DB connection failed for check.")
                        messagebox.showwarning("DB Warning", "Could not check for task conflicts. Save cautiously.", parent=self.root)
                    else:
                        existing_tasks = database_manager.get_all_tasks(conn_check)
                        perf_after_get_all_tasks = time.perf_counter()
                        logger.debug(f"Conflict Check Perf: Fetched all tasks for check at {perf_after_get_all_tasks:.4f}. DB query time: {perf_after_get_all_tasks - perf_start_conflict_check_section:.4f}s")
                        conflict_found = False
                        for existing_task in existing_tasks:
                            if self.currently_editing_task_id and existing_task.id == self.currently_editing_task_id:
                                continue # Skip self when editing
                            if existing_task.status == 'Completed':
                                continue # Skip completed tasks
                            if not existing_task.due_date or not existing_task.duration or existing_task.duration == 0:
                                continue # Skip tasks without due date or duration for conflict check
                            try:
                                et_start_dt = datetime.datetime.fromisoformat(existing_task.due_date)
                                et_end_dt = et_start_dt + timedelta(minutes=existing_task.duration)
                            except ValueError:
                                logger.warning(f"Invalid date format for existing task ID {existing_task.id} ('{existing_task.due_date}'). Skipping in conflict check.")
                                continue

                            is_potential_conflict = False
                            # current_task_repetition is from strip
                            existing_task_repetition = existing_task.repetition if existing_task.repetition else 'None'

                            if current_task_repetition == existing_task_repetition:
                                if current_task_repetition == 'None': # One-time vs One-time
                                    if database_manager.check_timeslot_overlap(ct_start_dt, ct_end_dt, et_start_dt, et_end_dt):
                                        is_potential_conflict = True
                                else: # Recurring vs Recurring (same type)
                                    ct_start_time = ct_start_dt.time()
                                    ct_end_time_val = (ct_start_dt + timedelta(minutes=task_duration_total_minutes)).time()
                                    et_start_time = et_start_dt.time()
                                    et_end_time_val = (et_start_dt + timedelta(minutes=existing_task.duration)).time()

                                    specific_match_criteria = False
                                    if current_task_repetition == 'Daily': specific_match_criteria = True
                                    elif current_task_repetition == 'Weekly':
                                        if ct_start_dt.weekday() == et_start_dt.weekday(): specific_match_criteria = True
                                    elif current_task_repetition == 'Monthly':
                                        if ct_start_dt.day == et_start_dt.day: specific_match_criteria = True
                                    elif current_task_repetition == 'Yearly':
                                        if ct_start_dt.month == et_start_dt.month and ct_start_dt.day == et_start_dt.day: specific_match_criteria = True

                                    if specific_match_criteria:
                                        if database_manager.check_time_only_overlap(ct_start_time, ct_end_time_val, et_start_time, et_end_time_val):
                                            is_potential_conflict = True
                            # No else needed: if repetition types are different, original logic implies no conflict for this check.

                            if is_potential_conflict:
                                conflict_msg = (f"Task '{title_value}' ({ct_start_dt.strftime('%Y-%m-%d %H:%M')}, Rep: {current_task_repetition}) conflicts with existing task '{existing_task.title}' (ID: {existing_task.id}, Due: {et_start_dt.strftime('%Y-%m-%d %H:%M')}, Rep: {existing_task_repetition}, duration: {existing_task.duration} min). Please choose a different time, duration, or repetition.")
                                logger.warning(conflict_msg)
                                messagebox.showerror("Task Conflict", conflict_msg, parent=self.root)
                                conflict_found = True
                                break # Exit loop once a conflict is found

                        if conflict_found:
                            if conn_check: conn_check.close()
                            return # Stop processing if conflict
                except Exception as e_check:
                    logger.error(f"Error during conflict check: {e_check}", exc_info=True)
                    messagebox.showerror("Conflict Check Error", "An error occurred while checking for task conflicts. Saving aborted.", parent=self.root)
                    if conn_check: conn_check.close()
                    return
                finally:
                    if conn_check: conn_check.close()
                perf_end_conflict_check_section = time.perf_counter()
                logger.debug(f"Conflict Check Perf: Exiting conflict check section. Total time: {perf_end_conflict_check_section - perf_start_conflict_check_section:.4f}s")
            except ValueError: # fromisoformat for current task's due_date
                 logger.error(f"Invalid due_date ('{task_due_datetime_iso}') for current task '{title_value}' during conflict check setup. Aborting save.", exc_info=True)
                 messagebox.showerror("Invalid Date", "The due date for the current task is invalid. Cannot save.", parent=self.root)
                 return

        # Priority mapping
        priority_display_to_model_map = {"Low": 1, "Medium": 2, "High": 3}
        priority = priority_display_to_model_map.get(priority_str, 2) # Default to Medium if string is somehow invalid

        conn_save = None
        try:
            conn_save = database_manager.create_connection()
            if not conn_save:
                logger.error("DB Save Op: Failed to create database connection.")
                messagebox.showerror("Database Error", "Cannot save task: DB connection failed.", parent=self.root)
                return
            database_manager.create_table(conn_save) # Ensure table exists

            if self.currently_editing_task_id is not None: # Update existing task
                logger.info(f"Attempting to update task ID: {self.currently_editing_task_id}")
                task_before_edit = database_manager.get_task(conn_save, self.currently_editing_task_id)
                if task_before_edit is None:
                    messagebox.showerror("Error", "Original task not found. Update failed.", parent=self.root)
                    return

                status_to_save = task_before_edit.status
                # If a completed task's due date is changed, revert its status to 'Pending'
                if task_before_edit.status == 'Completed' and task_before_edit.due_date != task_due_datetime_iso:
                    status_to_save = 'Pending'
                    logger.info(f"Task ID {task_before_edit.id} ('{task_before_edit.title}') was 'Completed'. Due date changed. Status auto-reverted to 'Pending'.")
                    messagebox.showinfo("Status Changed", f"Task '{task_before_edit.title}' status has been reset to 'Pending' because its due date was changed.", parent=self.root)

                task_data_obj = Task(
                    id=self.currently_editing_task_id, title=title_value, description=description,
                    duration=task_duration_total_minutes, creation_date=task_before_edit.creation_date, # Keep original creation date
                    repetition=current_task_repetition, priority=priority, category=category,
                    due_date=task_due_datetime_iso, status=status_to_save,
                    last_reset_date=task_before_edit.last_reset_date # Keep original last_reset_date
                )
                success = database_manager.update_task(conn_save, task_data_obj)
                if success:
                    if self.currently_editing_task_id in self.active_popups: # Close reminder if it was active
                        active_popup_instance = self.active_popups.get(self.currently_editing_task_id)
                        if active_popup_instance and active_popup_instance.winfo_exists():
                            active_popup_instance._cleanup_and_destroy()
                    messagebox.showinfo("Success", "Task updated successfully!", parent=self.root)
                else:
                    messagebox.showerror("Error", "Failed to update task.", parent=self.root)

            else: # Add new task
                logger.info("Attempting to add new task.")
                creation_date = datetime.datetime.now().isoformat()
                new_task_obj = Task(
                    id=0, title=title_value, description=description, duration=task_duration_total_minutes,
                    creation_date=creation_date, repetition=current_task_repetition, priority=priority,
                    category=category, due_date=task_due_datetime_iso
                    # status defaults to 'Pending' in Task model, last_reset_date to None
                )
                task_id = database_manager.add_task(conn_save, new_task_obj)
                if task_id:
                    messagebox.showinfo("Success", f"Task saved successfully with ID: {task_id}!", parent=self.root)
                else:
                    messagebox.showerror("Error", "Failed to save task to database.", parent=self.root)

            # Common post-save actions
            self.clear_form_fields_and_reset_state() # Clears the strip and resets currently_editing_task_id
            if hasattr(self, 'strip_add_button'): # Reset button text if it was "Update Task"
                 self.strip_add_button.config(text="+")
            self.refresh_task_list()
            self.request_reschedule_reminders()

        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            logger.error(error_message, exc_info=True)
            messagebox.showerror("Error", error_message, parent=self.root)
        finally:
            if conn_save: conn_save.close()


    # save_task_action is now obsolete and can be removed.
    # def save_task_action(self): ...

    def delete_selected_task(self):
        if self.headless_mode:
            logger.warning("delete_selected_task called in headless_mode. UI not available.")
            return

        if self.selected_task_id_for_card_view is None:
            try:
                messagebox.showwarning("No Selection", "Please select a task from the list to delete.", parent=self.root)
            except tk.TclError:
                logger.warning("No task selected for deletion (messagebox not available).")
            return

        task_id = self.selected_task_id_for_card_view
        logger.info(f"Attempting to delete task ID {task_id} (selected from card view).")

        confirmed_delete = False
        try:
            confirmed_delete = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete task ID: {task_id}?", parent=self.root)
            if not confirmed_delete:
                logger.info(f"Deletion of task ID {task_id} cancelled by user.")
                return
        except tk.TclError:
            logger.info(f"Confirmation for deleting task ID {task_id} skipped (messagebox not available). Assuming NO for safety in headless.")
            return
        conn = None
        try:
            conn = database_manager.create_connection()
            if not conn:
                try: messagebox.showerror("Database Error", "Could not connect to the database.", parent=self.root)
                except tk.TclError: logger.error("DB Error: Could not connect for deletion (messagebox not available).")
                return
            success = database_manager.delete_task(conn, task_id)
            if success:
                try: messagebox.showinfo("Success", f"Task ID: {task_id} deleted successfully!", parent=self.root)
                except tk.TclError: logger.info(f"Success: Task {task_id} deleted (messagebox not available).")
                self.refresh_task_list()
                if self.currently_editing_task_id == task_id:
                    self.clear_form_fields_and_reset_state()
                self.request_reschedule_reminders()

                if self.selected_card_instance:
                    self.selected_card_instance = None
                self.selected_task_id_for_card_view = None
                logger.debug("Card selection cleared after task deletion.")
            else:
                try: messagebox.showerror("Error", f"Failed to delete task ID: {task_id}.", parent=self.root)
                except tk.TclError: logger.error(f"Error: Failed to delete task {task_id} (messagebox not available).")
        except Exception as e:
            error_msg = f"Failed to delete task: {e}"
            try: messagebox.showerror("Error", error_msg, parent=self.root)
            except tk.TclError: logger.error(f"Error: {error_msg} (messagebox not available).")
            logger.error(f"Error in delete_selected_task: {e}", exc_info=True)
        finally:
            if conn: conn.close()

    # --- Formatting Helper Methods for Creation Strip Display Labels ---

    def _format_display_due_date(self) -> str:
        """Formats due date and time for display on the creation strip."""
        if not self.strip_due_date_value: # Relies on self.strip_due_date_value, etc.
            return ""
        try:
            dt_obj = datetime.datetime.strptime(f"{self.strip_due_date_value} {self.strip_due_hour_value}:{self.strip_due_minute_value}", "%Y-%m-%d %H:%M")
            # Example: "Jul 15, 10:00" or "Today, 14:30" or "Tomorrow, 09:00"
            now = datetime.datetime.now()
            if dt_obj.date() == now.date():
                date_part = "Today"
            elif dt_obj.date() == (now + datetime.timedelta(days=1)).date():
                date_part = "Tomorrow"
            else:
                date_part = dt_obj.strftime("%b %d") # e.g., Jul 15
            return f"{date_part}, {dt_obj.strftime('%H:%M')}"
        except ValueError:
            return "Invalid Date" # Should not happen if validation in popup is correct

    def _format_display_duration(self) -> str:
        """Formats duration for display on the creation strip."""
        hours = self.strip_duration_hours_value
        minutes = self.strip_duration_minutes_value
        total_minutes = (hours * 60) + minutes
        if total_minutes == 0:
            return ""

        if hours > 0 and minutes > 0: return f"{hours}h {minutes}m"
        elif hours > 0: return f"{hours}h"
        else: return f"{minutes}m"

    def _format_display_repetition(self) -> str:
        """Formats repetition for display on the creation strip."""
        rep = self.strip_repetition_value
        return rep if rep and rep != "None" else ""

    def _format_display_priority(self) -> str:
        """Formats priority for display on the creation strip."""
        priority = self.strip_priority_value
        # Assuming "Medium" is the default and shouldn't be explicitly shown unless different
        return priority if priority and priority != "Medium" else ""

    def _format_display_category(self) -> str:
        """Formats category for display on the creation strip."""
        return self.strip_category_value.strip()

    def _format_display_description(self) -> str:
        """Formats description indicator for display on the creation strip."""
        return "[...]" if self.strip_description_value and self.strip_description_value.strip() else ""

    # --- Original _format_duration_display (for task list card) ---
    def _format_duration_display(self, total_minutes: int) -> str: # Keep this for existing task card list
        if total_minutes is None or total_minutes < 0: return "-"
        if total_minutes == 0: return "-"
        hours = total_minutes // 60
        minutes = total_minutes % 60
        if hours > 0 and minutes > 0: return f"{hours}h {minutes}m"
        elif hours > 0: return f"{hours}h"
        else: return f"{minutes}m"

    def refresh_task_list(self):
        if self.headless_mode:
            logger.debug("refresh_task_list called in headless_mode. Skipping UI update for cards.")
            return

        self.selected_card_instance = None
        self.selected_task_id_for_card_view = None
        logger.debug("Cleared existing card selection state before refresh.")

        if hasattr(self, 'cards_frame') and self.cards_frame:
            for widget in self.cards_frame.winfo_children():
                widget.destroy()
            logger.debug("Cleared old cards from cards_frame.")
        else:
            logger.warning("refresh_task_list: self.cards_frame not initialized. Cannot clear old cards.")
            return

        conn = None
        tasks = []
        try:
            conn = database_manager.create_connection()
            if not conn:
                logger.error("Database Error: Could not connect to refresh tasks for view.")
                if not self.headless_mode and self.root:
                    try: messagebox.showerror("Database Error", "Could not connect to the database.", parent=self.root)
                    except tk.TclError: logger.error("DB Error: Could not connect (messagebox not available).")
                return
            logger.info(f"Refreshing task list for view: {self.current_task_view}")
            database_manager.create_table(conn)
            if self.current_task_view == "all": tasks = database_manager.get_all_tasks(conn)
            elif self.current_task_view == "today": tasks = database_manager.get_tasks_due_today(conn)
            elif self.current_task_view == "completed": tasks = database_manager.get_completed_tasks(conn)
            elif self.current_task_view == "missed_skipped":
                missed = database_manager.get_missed_tasks(conn)
                skipped = database_manager.get_skipped_tasks_db(conn)
                tasks = missed + skipped
                tasks.sort(key=lambda t: t.due_date if t.due_date else '', reverse=True)
            elif self.current_task_view == "reschedule_section":
                tasks = database_manager.get_all_tasks(conn)
                logger.info("Displaying all tasks for 'Reschedule Section' (placeholder).")
            else:
                logger.warning(f"Unknown task view: {self.current_task_view}. Defaulting to all tasks.")
                tasks = database_manager.get_all_tasks(conn)

            if not tasks:
                logger.info(f"No tasks to display for view: {self.current_task_view}")
            else:
                logger.info(f"Populating task list with {len(tasks)} cards for view: {self.current_task_view}")
                card_callbacks = {
                    'on_card_selected': self.handle_card_selected
                }
                for task_obj in tasks:
                    try:
                        card = TaskCard(self.cards_frame, task_obj, card_callbacks)
                        card.pack(pady=5, padx=5, fill=tk.X, expand=True) # Added expand=True
                    except Exception as e:
                        logger.error(f"Error creating TaskCard for task ID {task_obj.id if task_obj else 'N/A'}: {e}", exc_info=True)

            if hasattr(self, '_on_cards_frame_configure'):
                 self._on_cards_frame_configure()
        except Exception as e:
            error_message = f"Error during task fetching or card population: {e}"
            logger.error(error_message, exc_info=True)
            if not self.headless_mode:
                try: messagebox.showerror("Error", error_message, parent=self.root)
                except tk.TclError: pass
        finally:
            if conn:
                conn.close()
                logger.debug("Database connection closed after refreshing task list.")

    def on_closing(self):
        logger.info("WM_DELETE_WINDOW: Closing application.")
        if hasattr(self, 'scheduler') and self.scheduler and self.scheduler.running:
            logger.info("Attempting to shut down the scheduler...")
            try:
                self.scheduler.shutdown(wait=False)
                logger.info("Scheduler shutdown successfully.")
            except Exception as e:
                logger.error(f"Error during scheduler shutdown: {e}", exc_info=True)
        if not self.headless_mode and self.root:
            logger.info("Destroying main window.")
            self.root.destroy()
        elif self.headless_mode:
            logger.info("Headless mode: No root window to destroy. Application will exit if main loop isn't running.")

    def request_reschedule_reminders(self):
        logger.info("Requesting reschedule of reminders.")
        if hasattr(self, 'scheduler') and self.scheduler and self.scheduler.running:
            try:
                run_time = datetime.datetime.now() + timedelta(seconds=3)
                job_id = 'immediate_reschedule_reminders_job'
                logger.debug(f"Adding/replacing job '{job_id}' to run scheduler_manager.schedule_task_reminders at {run_time.isoformat()}")
                self.scheduler.add_job(scheduler_manager.schedule_task_reminders, trigger='date', run_date=run_time, args=[self.scheduler, self.reminder_queue], id=job_id, replace_existing=True, misfire_grace_time=60)
            except Exception as e:
                logger.error(f"Error requesting immediate reschedule of reminders: {e}", exc_info=True)
        else:
            logger.warning("Scheduler not available or not running. Cannot request immediate reminder reschedule.")

    def _check_reminder_queue(self):
        if not self.headless_mode and (not self.root or not self.root.winfo_exists()):
            logger.warning("Root window not available in _check_reminder_queue (GUI mode). Stopping poll.")
            return
        logger.debug("Checking reminder queue...")
        try:
            while not self.reminder_queue.empty():
                reminder_data = self.reminder_queue.get_nowait()
                logger.debug(f"Retrieved from reminder_queue: {reminder_data}")
                task_id = reminder_data.get('task_id')
                if task_id is None:
                    logger.warning("Received reminder data without task_id from queue.")
                    continue
                logger.info(f"Processing reminder for task ID {task_id} from queue.")
                conn = None
                task_details = None
                try:
                    conn = database_manager.create_connection()
                    if conn:
                        task_details = database_manager.get_task(conn, task_id)
                        logger.debug(f"Fetched task details for ID {task_id}: {'Found' if task_details else 'Not Found'}")
                    else:
                        logger.error(f"Cannot process reminder for task ID {task_id}: DB connection failed.")
                        continue
                finally:
                    if conn: conn.close()
                if not task_details:
                    logger.warning(f"Could not retrieve full task details for task ID {task_id}. Cannot display/process reminder.")
                    continue
                if task_details.status == 'Completed':
                    logger.info(f"Task ID {task_id} ('{task_details.title}') is already completed. Skipping reminder.")
                    continue
                if self.headless_mode:
                    logger.info(f"HEADLESS_TEST: Reminder triggered for task ID: {task_id} - Title: '{task_details.title}'.")
                    if task_details.title:
                        logger.info(f"HEADLESS_TEST: Requesting TTS for: Task {task_details.title}")
                        tts_manager.speak(f"Reminder for task: {task_details.title}")
                    else:
                        logger.warning(f"HEADLESS_TEST: Task ID {task_id} has no title. Speaking generic reminder.")
                        tts_manager.speak("Reminder for task with no title.")
                else:
                    if task_id in self.active_popups and self.active_popups[task_id].winfo_exists():
                        logger.info(f"Popup for task ID {task_id} already active. Bringing to front.")
                        self.active_popups[task_id].deiconify()
                        self.active_popups[task_id].lift()
                        self.active_popups[task_id].focus_force()
                        continue
                    logger.info(f"Attempting to create ReminderPopupUI for task ID {task_id}. Active popups: {list(self.active_popups.keys())}")
                    app_callbacks = { 'reschedule': self.handle_reschedule_task, 'complete': self.handle_complete_task, 'remove_from_active': self._remove_popup_from_active, 'request_wrap_position': self._calculate_next_wrap_position, 'skip_task': self.handle_skip_task, }
                    target_x = self.popup_next_x
                    target_y = self.popup_next_y
                    logger.info(f"POPUP_STACKING: New popup (Task ID: {task_id}) target: X={target_x}, Y={target_y}")
                    self.popup_next_y += TaskManagerApp.POPUP_DEFAULT_HEIGHT + TaskManagerApp.POPUP_VERTICAL_GAP
                    logger.info(f"POPUP_STACKING: Next potential Y in column after this one: {self.popup_next_y}")
                    try:
                        screen_height = self.root.winfo_screenheight()
                        if self.popup_next_y + TaskManagerApp.POPUP_DEFAULT_HEIGHT + TaskManagerApp.POPUP_BOTTOM_MARGIN > screen_height:
                            logger.warning(f"POPUP_STACKING: Screen bottom reached (next_y={self.popup_next_y}). Resetting Y to {TaskManagerApp.POPUP_INITIAL_Y}, Shifting X.")
                            self.popup_next_y = TaskManagerApp.POPUP_INITIAL_Y
                            self.popup_next_x -= (TaskManagerApp.POPUP_DEFAULT_WIDTH + TaskManagerApp.POPUP_HORIZONTAL_GAP)
                            logger.info(f"POPUP_STACKING: New column X={self.popup_next_x}")
                            if self.popup_next_x < TaskManagerApp.POPUP_LEFT_MARGIN:
                                logger.warning(f"POPUP_STACKING: Screen left reached (next_x={self.popup_next_x}). Resetting X to {TaskManagerApp.POPUP_INITIAL_X}. Overlap may occur.")
                                self.popup_next_x = TaskManagerApp.POPUP_INITIAL_X
                    except (tk.TclError, AttributeError) as e:
                        logger.warning(f"POPUP_STACKING: Could not get screen dimensions for boundary check: {e}. Stacking may behave unpredictably.")
                    popup = ReminderPopupUI(self.root, task_details, app_callbacks, target_x=target_x, target_y=target_y)
                    self.active_popups[task_id] = popup
                    logger.info(f"ReminderPopupUI created for task ID {task_id} at X={target_x}, Y={target_y} and added to active_popups.")
        except queue.Empty: pass
        except Exception as e: logger.error(f"Error processing reminder queue: {e}", exc_info=True)
        if not self.headless_mode and self.root and self.root.winfo_exists():
             self.root.after(250, self._check_reminder_queue)

    def _update_or_create_display_label(self, label_attr_name: str, parent_frame: bs.Frame, text_to_display: str, icon_button_widget: bs.Button):
        """
        Dynamically creates, updates, or hides a display label on the creation strip.
        - label_attr_name: The string name of the instance attribute holding the label widget (e.g., "strip_repetition_display_label").
        - parent_frame: The bs.Frame this label belongs to (e.g., self.rep_field_frame).
        - text_to_display: The text to show. If empty, the label will be hidden.
        - icon_button_widget: The icon button widget that the label should be packed next to.
        """
        label_widget = getattr(self, label_attr_name, None)

        if not text_to_display: # Empty text means hide the label
            if label_widget and label_widget.winfo_exists() and label_widget.winfo_manager() == 'pack':
                label_widget.pack_forget()
                logger.debug(f"Hid label for {label_attr_name} as text is empty.")
            # Optionally, could also do: setattr(self, label_attr_name, None); label_widget.destroy()
            # For now, just hiding allows reuse and is simpler.
        else: # Text is not empty, so create or update and show
            if not label_widget or not label_widget.winfo_exists():
                # Create label if it doesn't exist or was destroyed
                label_widget = bs.Label(parent_frame, text=text_to_display, **self.strip_label_options)
                setattr(self, label_attr_name, label_widget)
                # Pack it next to the icon button
                label_widget.pack(side=tk.LEFT, after=icon_button_widget, padx=(1,0)) # Small padx to separate from icon
                logger.debug(f"Created and packed new label for {label_attr_name} with text: '{text_to_display}'")
            else:
                # Label exists, just update its text
                label_widget.config(text=text_to_display)
                # Ensure it's packed correctly if it was previously hidden
                if not label_widget.winfo_ismapped(): # Check if it's not visible
                     label_widget.pack(side=tk.LEFT, after=icon_button_widget, padx=(1,0))
                logger.debug(f"Updated existing label for {label_attr_name} with text: '{text_to_display}'")


    def handle_skip_task(self, task_id):
        if task_id is None:
            logger.warning("handle_skip_task called with None task_id.")
            return
        logger.info(f"Attempting to mark task ID: {task_id} as 'Skipped'.")
        conn = None
        try:
            conn = database_manager.create_connection()
            if not conn:
                logger.error(f"Failed to connect to DB for skipping task {task_id}.")
                return
            if database_manager.update_task_status(conn, task_id, "Skipped"):
                logger.info(f"Task ID: {task_id} status successfully updated to 'Skipped' in DB.")
            else:
                logger.error(f"Failed to update task ID: {task_id} status to 'Skipped' in DB.")
        except Exception as e:
            logger.error(f"Error in handle_skip_task for task ID {task_id}: {e}", exc_info=True)
        finally:
            if conn: conn.close()
        if not self.headless_mode and hasattr(self, 'refresh_task_list'):
            self.refresh_task_list()

    def _handle_menu_selection(self, view_name):
        self.current_task_view = view_name
        logger.info(f"Switched task view to: {self.current_task_view}")
        self.refresh_task_list()

    def handle_card_selected(self, task_id, card_instance):
        logger.info(f"Card selected: Task ID {task_id}")
        if self.selected_card_instance and self.selected_card_instance != card_instance:
            if hasattr(self.selected_card_instance, 'deselect') and callable(self.selected_card_instance.deselect):
                self.selected_card_instance.deselect()
            else:
                logger.warning("Previously selected card instance or its deselect method not found.")

        if hasattr(card_instance, 'select') and callable(card_instance.select):
            card_instance.select()
            self.selected_card_instance = card_instance
            self.selected_task_id_for_card_view = task_id
        else:
            logger.error("Current card instance or its select method not found. Cannot visually select.")

    def _calculate_next_wrap_position(self, wrapping_popup_id):
        logger.debug(f"POPUP_WRAP_POS: Calculating next wrap position for popup ID: {wrapping_popup_id}")
        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
        except tk.TclError:
            logger.warning("POPUP_WRAP_POS: Could not get screen dimensions, using fallback for base wrap corner.")
            screen_w = 1920
            screen_h = 1080
        wrapped_width = 110
        wrapped_height = 40
        edge_padding = 10
        bottom_padding = 40
        inter_popup_gap = 5
        base_x = screen_w - wrapped_width - edge_padding
        base_y = screen_h - wrapped_height - bottom_padding
        next_wrap_x = base_x
        next_wrap_y = base_y
        occupied_y_at_base_x = []
        for popup_id, p_instance in self.active_popups.items():
            if isinstance(p_instance, ReminderPopupUI) and \
               p_instance.is_in_wrapped_state and \
               p_instance.winfo_exists() and \
               popup_id != wrapping_popup_id:
                try:
                    if p_instance.winfo_x() == base_x:
                        occupied_y_at_base_x.append(p_instance.winfo_y())
                except tk.TclError:
                    logger.warning(f"POPUP_WRAP_POS: TclError getting geometry for wrapped popup {popup_id}")
        if occupied_y_at_base_x:
            occupied_y_at_base_x.sort()
            highest_occupied_y = occupied_y_at_base_x[0]
            next_wrap_y = highest_occupied_y - wrapped_height - inter_popup_gap
            logger.debug(f"POPUP_WRAP_POS: Other wrapped popups found at X={base_x}. Highest Y={highest_occupied_y}. New next_wrap_y={next_wrap_y}")
        else:
            logger.debug(f"POPUP_WRAP_POS: No other wrapped popups at X={base_x}. Using base_y: {next_wrap_y}")
        top_margin = 10
        if next_wrap_y < top_margin:
            logger.warning(f"POPUP_WRAP_POS: Calculated wrap Y {next_wrap_y} too high, adjusting to {top_margin}. May cause overlap if many popups.")
            next_wrap_y = top_margin
        logger.info(f"POPUP_WRAP_POS: Final calculated wrap position for ID {wrapping_popup_id}: X={next_wrap_x}, Y={next_wrap_y}")
        return (next_wrap_x, next_wrap_y)

    def handle_reschedule_task(self, task_id, minutes_to_add):
        logger.info(f"Attempting to reschedule task ID: {task_id} by {minutes_to_add} minutes.")
        conn = None
        try:
            conn = database_manager.create_connection()
            if not conn:
                logger.error("Failed to connect to DB for rescheduling.")
                if task_id in self.active_popups: del self.active_popups[task_id]
                return
            task = database_manager.get_task(conn, task_id)
            if not task:
                logger.error(f"Task ID {task_id} not found for rescheduling.")
                if task_id in self.active_popups: del self.active_popups[task_id]
                return
            current_due_datetime = datetime.datetime.now()
            if task.due_date:
                try: current_due_datetime = datetime.datetime.fromisoformat(task.due_date)
                except ValueError: logger.error(f"Invalid due_date format for task {task_id}: {task.due_date}. Using current time as base for reschedule.")
            new_due_datetime = current_due_datetime + timedelta(minutes=minutes_to_add)
            task.due_date = new_due_datetime.isoformat()
            if database_manager.update_task(conn, task): logger.info(f"Task ID: {task_id} rescheduled successfully to {task.due_date}.")
            else: logger.error(f"Failed to update task ID: {task_id} in DB for rescheduling.")
        except Exception as e: logger.error(f"Error in handle_reschedule_task for task ID {task_id}: {e}", exc_info=True)
        finally:
            if conn: conn.close()
        if not self.headless_mode: self.refresh_task_list()
        self.request_reschedule_reminders()

    def handle_complete_task(self, task_id):
        logger.info(f"Attempting to mark task ID: {task_id} as 'Completed'.")
        conn = None
        try:
            conn = database_manager.create_connection()
            if not conn:
                logger.error("Failed to connect to DB for completing task.")
                if task_id in self.active_popups: del self.active_popups[task_id]
                return
            task = database_manager.get_task(conn, task_id)
            if not task:
                logger.error(f"Task ID {task_id} not found for completion.")
                if task_id in self.active_popups: del self.active_popups[task_id]
                return
            task.status = "Completed"
            if database_manager.update_task(conn, task): logger.info(f"Task ID: {task_id} marked as 'Completed' successfully.")
            else: logger.error(f"Failed to update task ID: {task_id} status to 'Completed' in DB.")
        except Exception as e: logger.error(f"Error in handle_complete_task for task ID {task_id}: {e}", exc_info=True)
        finally:
            if conn: conn.close()
        if not self.headless_mode: self.refresh_task_list()
        self.request_reschedule_reminders()

    def _remove_popup_from_active(self, task_id):
        if task_id in self.active_popups:
            del self.active_popups[task_id]
            logger.debug(f"Popup for task ID {task_id} removed from active list.")
            if not self.active_popups:
                self.popup_next_x = TaskManagerApp.POPUP_INITIAL_X
                self.popup_next_y = TaskManagerApp.POPUP_INITIAL_Y
                logger.info("POPUP_STACKING: All popups closed. Resetting next popup position to initial defaults.")

    def toggle_tts_mute(self, event=None):
        if tts_manager:
            try:
                current_mute_state = tts_manager.is_muted
                new_mute_state = not current_mute_state
                tts_manager.set_mute(new_mute_state)
                logger.info(f"TTS Mute toggled via keyboard shortcut. New state: {'Muted' if new_mute_state else 'Unmuted'}")
            except Exception as e: logger.error(f"Error toggling TTS mute: {e}", exc_info=True)
        else: logger.warning("TTS manager instance (tts_manager) not found. Cannot toggle mute.")

if __name__ == '__main__':
    root = None
    app = None
    try:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)-8s - %(name)-25s - %(message)s')
        logger.info("Application starting...")
        root = bs.Window(themename="solar")
        logger.info("GUI mode detected. Initializing TaskManagerApp for GUI.")
        app = TaskManagerApp(root_window=root, headless_mode=False)
        logger.info("Starting Tkinter mainloop...")
        root.mainloop()
        logger.info("Tkinter mainloop finished.")
    except tk.TclError as e:
        logger.error(f"Tkinter TclError occurred: {e}", exc_info=True)
        if "display name" in str(e).lower() or "couldn't connect to display" in str(e).lower():
            logger.info("No display found, attempting to run in HEADLESS test mode.")
            app = TaskManagerApp(root_window=None, headless_mode=True)
            if app.headless_mode:
                logger.info("Running in HEADLESS test mode. Scheduler and queue processing active.")
                logger.info("Application will simulate running for up to 5 minutes. Press Ctrl+C to interrupt.")
                if not app.scheduler or not app.scheduler.running: logger.warning("Scheduler not running in headless mode. Reminders might not be processed.")
                end_time = time.time() + (60 * 5)
                try:
                    while time.time() < end_time:
                        app._check_reminder_queue()
                        time.sleep(0.25)
                    logger.info("HEADLESS test mode finished after 5 minutes.")
                except KeyboardInterrupt: logger.info("HEADLESS test mode interrupted by user (Ctrl+C).")
                finally:
                    logger.info("HEADLESS_TEST: Main loop ending. Preparing to shut down scheduler...")
                    if hasattr(app, 'scheduler') and app.scheduler and app.scheduler.running:
                        logger.info("HEADLESS_TEST: Shutting down scheduler.")
                        app.scheduler.shutdown()
                    logger.info("HEADLESS_TEST: Application exiting.")
                    sys.exit(0)
            else:
                logger.error("Failed to correctly initialize in headless_mode. Exiting.")
                sys.exit(1)
        else: logger.critical(f"An unexpected Tkinter TclError occurred on startup (not a display issue): {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"A critical unexpected error occurred at app root level: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if app:
             if not app.headless_mode and app.root and app.root.winfo_exists(): pass
             elif app.headless_mode :
                 if hasattr(app, 'scheduler') and app.scheduler and app.scheduler.running:
                     logger.info("Ensuring scheduler shutdown in main finally block (headless).")
                     app.scheduler.shutdown()
        logger.info("Application terminated.")
