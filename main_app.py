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

        self.global_controls_frame = bs.Frame(self.root, padding=(10, 5))
        self.global_controls_frame.grid(row=0, column=1, sticky="ew", padx=10, pady=(5,0))

        self.global_create_task_button = bs.Button(
            self.global_controls_frame, text="Create New Task",
            command=self._toggle_task_form_visibility, bootstyle="primary"
        )
        self.global_create_task_button.pack(side=tk.LEFT)

        self.form_frame = bs.Frame(self.root, padding=(20, 10))
        self.form_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
        self.form_frame.columnconfigure(1, weight=1)
        self.form_frame.grid_remove()

        title_label = bs.Label(master=self.form_frame, text="Title: *")
        title_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['title'] = ttk.Entry(master=self.form_frame, width=50)
        self.input_widgets['title'].grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        desc_label = bs.Label(master=self.form_frame, text="Description:")
        desc_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")
        self.input_widgets['description'] = tk.Text(master=self.form_frame, height=4, width=38)
        self.input_widgets['description'].grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        current_form_row = 2
        self.duration_h_m_label = bs.Label(self.form_frame, text="Duration:")
        self.duration_h_m_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        duration_frame = bs.Frame(self.form_frame)
        duration_frame.grid(row=current_form_row, column=1, padx=5, pady=5, sticky="ew")
        self.input_widgets['duration_hours'] = ttk.Spinbox(duration_frame, from_=0, to=99, width=4)
        self.input_widgets['duration_hours'].pack(side=tk.LEFT, padx=(0,2))
        self.input_widgets['duration_hours'].set(0)
        dur_hrs_label = bs.Label(duration_frame, text="hrs")
        dur_hrs_label.pack(side=tk.LEFT, padx=(0,5))
        self.input_widgets['duration_minutes'] = ttk.Spinbox(duration_frame, from_=0, to=55, increment=5, width=4)
        self.input_widgets['duration_minutes'].pack(side=tk.LEFT, padx=(0,2))
        self.input_widgets['duration_minutes'].set(30)
        dur_min_label = bs.Label(duration_frame, text="min")
        dur_min_label.pack(side=tk.LEFT, padx=(0,0))
        current_form_row += 1

        rep_label = bs.Label(master=self.form_frame, text="Repetition:")
        rep_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['repetition'] = ttk.Combobox(master=self.form_frame, values=['None', 'Daily', 'Weekly', 'Monthly', 'Yearly'], width=47, state="readonly")
        self.input_widgets['repetition'].set('None')
        self.input_widgets['repetition'].grid(row=current_form_row, column=1, padx=5, pady=5, sticky="ew")
        current_form_row += 1

        priority_label = bs.Label(master=self.form_frame, text="Priority:")
        priority_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['priority'] = ttk.Combobox(master=self.form_frame, values=['Low', 'Medium', 'High'], width=47, state="readonly")
        self.input_widgets['priority'].set('Medium')
        self.input_widgets['priority'].grid(row=current_form_row, column=1, padx=5, pady=5, sticky="ew")
        current_form_row += 1

        category_label = bs.Label(master=self.form_frame, text="Category:")
        category_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['category'] = ttk.Entry(master=self.form_frame, width=50)
        self.input_widgets['category'].grid(row=current_form_row, column=1, padx=5, pady=5, sticky="ew")
        current_form_row += 1

        due_date_label = bs.Label(master=self.form_frame, text="Due Date:")
        due_date_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['due_date'] = bs.DateEntry(self.form_frame, dateformat="%Y-%m-%d", firstweekday=0)
        self.input_widgets['due_date'].grid(row=current_form_row, column=1, padx=5, pady=5, sticky="ew")
        current_form_row += 1

        due_time_label = bs.Label(master=self.form_frame, text="Due Time (HH:MM):")
        due_time_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        time_frame = bs.Frame(self.form_frame)
        time_frame.grid(row=current_form_row, column=1, padx=0, pady=5, sticky="ew")
        self.input_widgets['due_hour'] = ttk.Combobox(master=time_frame, state="readonly", width=5, values=[f"{h:02d}" for h in range(24)])
        self.input_widgets['due_hour'].set("12")
        self.input_widgets['due_hour'].pack(side=tk.LEFT, padx=(5,2))
        time_separator_label = bs.Label(master=time_frame, text=":")
        time_separator_label.pack(side=tk.LEFT, padx=0)
        self.input_widgets['due_minute'] = ttk.Combobox(master=time_frame, state="readonly", width=5, values=[f"{m:02d}" for m in range(0, 60, 5)])
        self.input_widgets['due_minute'].set("00")
        self.input_widgets['due_minute'].pack(side=tk.LEFT, padx=(2,5))
        current_form_row += 1

        button_frame = bs.Frame(self.form_frame)
        button_frame.grid(row=current_form_row, column=0, columnspan=2, pady=10)
        self.save_button = bs.Button(master=button_frame, text="Save Task", command=self.save_task_action, bootstyle="success")
        self.save_button.pack(side=tk.LEFT, padx=(0, 5))
        clear_button = bs.Button(master=button_frame, text="Clear Form", command=self.clear_form_fields_and_reset_state, bootstyle="warning")
        clear_button.pack(side=tk.LEFT)

        tree_container_frame = bs.Frame(self.root, padding=(0, 10, 0, 0))
        tree_container_frame.grid(row=2, column=1, sticky='nsew', padx=10, pady=(0, 10))

        tree_container_frame.columnconfigure(0, weight=1)
        tree_container_frame.columnconfigure(1, weight=0)

        tree_container_frame.rowconfigure(0, weight=0)
        tree_container_frame.rowconfigure(1, weight=1)

        list_title_label = bs.Label(tree_container_frame, text="Task List", font=("-size 12 -weight bold"))
        list_title_label.grid(row=0, column=0, sticky='w', padx=5, pady=(0, 5))

        top_right_actions_frame = bs.Frame(tree_container_frame)
        top_right_actions_frame.grid(row=0, column=1, sticky='e', padx=5, pady=(0,5))

        edit_button = bs.Button(top_right_actions_frame, text="Edit Selected",
                                command=self.load_selected_task_for_edit, bootstyle="info")
        edit_button.pack(side=tk.LEFT, padx=(0, 5))

        delete_button = bs.Button(top_right_actions_frame, text="Delete Selected",
                                  command=self.delete_selected_task, bootstyle="danger")
        delete_button.pack(side=tk.LEFT, padx=(0, 5))

        self.card_list_outer_frame = bs.Frame(tree_container_frame)
        self.card_list_outer_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=5, pady=10)

        self.card_list_outer_frame.rowconfigure(0, weight=1)
        self.card_list_outer_frame.columnconfigure(0, weight=1)

        self.task_list_canvas = bs.Canvas(self.card_list_outer_frame)
        self.task_list_canvas.grid(row=0, column=0, sticky='nsew')

        self.task_list_scrollbar = bs.Scrollbar(self.card_list_outer_frame, orient=tk.VERTICAL, command=self.task_list_canvas.yview)
        self.task_list_scrollbar.grid(row=0, column=1, sticky='ns')

        self.task_list_canvas.configure(yscrollcommand=self.task_list_scrollbar.set)

        self.cards_frame = bs.Frame(self.task_list_canvas)
        self.task_list_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw", tags="self.cards_frame")

        self.cards_frame.bind("<Configure>", self._on_cards_frame_configure)

        self.task_list_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.task_list_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.task_list_canvas.bind_all("<Button-5>", self._on_mousewheel)

        self.task_tree = None

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
            if not is_related_to_canvas: pass

            if event.delta:
                self.task_list_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            elif event.num == 4:
                self.task_list_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.task_list_canvas.yview_scroll(1, "units")
        else:
            logger.debug("_on_mousewheel: task_list_canvas not ready.")

    def _toggle_task_form_visibility(self):
        if not hasattr(self, 'form_frame'):
            logger.error("Task creation form (self.form_frame) not found."); return
        if not hasattr(self, 'global_create_task_button'):
            logger.error("Global create task button (self.global_create_task_button) not found.")

        if self.form_frame.winfo_ismapped():
            self.form_frame.grid_remove()
            if hasattr(self, 'global_create_task_button'):
                self.global_create_task_button.config(text="Create New Task")
            logger.info("Task creation form hidden.")
        else:
            self.form_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
            self.clear_form_fields_and_reset_state()
            if hasattr(self, 'global_create_task_button'):
                self.global_create_task_button.config(text="Hide Task Form")
            logger.info("Task creation form shown.")
            if hasattr(self, 'input_widgets') and 'title' in self.input_widgets and \
               hasattr(self.input_widgets['title'], 'focus_set'):
                self.input_widgets['title'].focus_set()
            else: logger.warning("Could not set focus to title widget on form show.")

    def clear_form_fields_and_reset_state(self):
        if self.headless_mode:
            self.currently_editing_task_id = None
            logger.info("Form fields state reset (headless mode)."); return

        self.input_widgets['title'].delete(0, tk.END)
        self.input_widgets['description'].delete("1.0", tk.END)
        self.input_widgets['repetition'].set('None')
        self.input_widgets['priority'].set('Medium')
        self.input_widgets['category'].delete(0, tk.END)
        if 'duration_hours' in self.input_widgets:
            self.input_widgets['duration_hours'].set(0)
            self.input_widgets['duration_minutes'].set(30)
        if 'due_date' in self.input_widgets:
            self.input_widgets['due_date'].entry.delete(0, tk.END)
            self.input_widgets['due_hour'].set("12")
            self.input_widgets['due_minute'].set("00")
        self.currently_editing_task_id = None
        if self.save_button: self.save_button.config(text="Save Task")
        logger.info("Form fields cleared and state reset.")

    def load_selected_task_for_edit(self):
        if not self.headless_mode and self.form_frame and not self.form_frame.winfo_ismapped():
            # Ensure the form is shown with correct grid options
            self.form_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
            if hasattr(self, 'global_create_task_button'):
                 self.global_create_task_button.config(text="Hide Task Form")

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

        # NOTE: The orphaned 'except ValueError:' block that might have been here
        # (causing SyntaxError if its 'try' was removed) is intentionally omitted in this corrected version.

        conn = None
        try:
            conn = database_manager.create_connection()
            if not conn:
                try:
                    messagebox.showerror("Database Error", "Could not connect to the database.", parent=self.root)
                except tk.TclError: logger.error("DB Error: Could not connect (messagebox not available).")
                return
            task_to_edit = database_manager.get_task(conn, task_id)
            if not task_to_edit:
                try:
                    messagebox.showerror("Error", f"Could not retrieve task with ID: {task_id}", parent=self.root)
                except tk.TclError: logger.error(f"Error retrieving task ID {task_id} (messagebox not available).")
                return

            self.input_widgets['title'].delete(0, tk.END)
            self.input_widgets['title'].insert(0, task_to_edit.title)
            self.input_widgets['description'].delete("1.0", tk.END)
            self.input_widgets['description'].insert('1.0', task_to_edit.description)
            total_minutes = task_to_edit.duration if task_to_edit.duration is not None else 0
            load_hours = total_minutes // 60
            load_minutes = total_minutes % 60
            self.input_widgets['duration_hours'].set(load_hours)
            self.input_widgets['duration_minutes'].set(load_minutes)
            self.input_widgets['category'].delete(0, tk.END)
            self.input_widgets['category'].insert(0, task_to_edit.category)
            self.input_widgets['repetition'].set(task_to_edit.repetition if task_to_edit.repetition else 'None')
            self.input_widgets['priority'].set(self.priority_map_display.get(task_to_edit.priority, "Medium"))

            if task_to_edit.due_date:
                try:
                    dt_obj = datetime.datetime.fromisoformat(task_to_edit.due_date)
                    self.input_widgets['due_date'].entry.delete(0, tk.END)
                    self.input_widgets['due_date'].entry.insert(0, dt_obj.strftime("%Y-%m-%d"))
                    self.input_widgets['due_hour'].set(dt_obj.strftime("%H"))
                    minute_val = int(dt_obj.strftime("%M"))
                    minute_to_set = f"{(minute_val // 5) * 5:02d}"
                    self.input_widgets['due_minute'].set(minute_to_set)
                except ValueError: # This ValueError is for date parsing, it's valid.
                    self.input_widgets['due_date'].entry.delete(0, tk.END)
                    self.input_widgets['due_hour'].set("12")
                    self.input_widgets['due_minute'].set("00")
            else:
                self.input_widgets['due_date'].entry.delete(0, tk.END)
                self.input_widgets['due_hour'].set("12")
                self.input_widgets['due_minute'].set("00")

            self.currently_editing_task_id = task_to_edit.id
            if self.save_button:
                self.save_button.config(text="Update Task")
            logger.info(f"Editing task ID: {self.currently_editing_task_id}")
            if hasattr(self.input_widgets.get('title'), 'focus_set'):
                 self.input_widgets['title'].focus_set()
        except Exception as e:
            error_msg = f"Failed to load task for editing: {e}"
            try:
                messagebox.showerror("Error", error_msg, parent=self.root)
            except tk.TclError: logger.error(f"Error: {error_msg} (messagebox not available).")
            logger.error(f"Error in load_selected_task_for_edit: {e}", exc_info=True)
        finally:
            if conn: conn.close()

    def save_task_action(self):
        if self.headless_mode:
            logger.error("save_task_action called in headless_mode. This should not happen via UI.")
            return

        title_value = self.input_widgets['title'].get().strip()
        if not title_value:
            try:
                messagebox.showerror("Validation Error", "Title field cannot be empty.", parent=self.root)
            except tk.TclError: logger.error("Validation Error: Title is empty (messagebox not available).")
            return

        description = self.input_widgets['description'].get("1.0", tk.END).strip()
        current_task_repetition = self.input_widgets['repetition'].get()
        priority_str = self.input_widgets['priority'].get()
        category = self.input_widgets['category'].get().strip()

        try:
            hours_str = self.input_widgets['duration_hours'].get()
            minutes_str = self.input_widgets['duration_minutes'].get()
            hours = int(hours_str) if hours_str else 0
            minutes = int(minutes_str) if minutes_str else 0
            if not (0 <= hours <= 99):
                if not self.headless_mode: messagebox.showerror("Invalid Duration", "Hours must be between 0 and 99.", parent=self.root)
                else: logger.error("Validation Error: Hours must be between 0 and 99.")
                return
            if not (0 <= minutes <= 59):
                if not self.headless_mode: messagebox.showerror("Invalid Duration", "Minutes must be between 0 and 59.", parent=self.root)
                else: logger.error("Validation Error: Minutes must be between 0 and 59.")
                return
            task_duration_total_minutes = (hours * 60) + minutes
        except ValueError:
            try:
                messagebox.showerror("Invalid Duration", "Duration hours and minutes must be numbers.", parent=self.root)
            except tk.TclError: logger.error("Validation Error: Duration hrs/min not numbers (messagebox not available).")
            return
        except tk.TclError:
            logger.error("Validation Error: Duration TclError (messagebox not available / TclError).")
            return

        due_date_str = ""
        if hasattr(self, 'input_widgets') and 'due_date' in self.input_widgets and self.input_widgets['due_date'].entry:
            due_date_str = self.input_widgets['due_date'].entry.get().strip()

        if not self.headless_mode and not due_date_str:
            logger.warning("Save Task Aborted: Due Date is required.")
            try:
                messagebox.showerror("Validation Error", "Due Date is required. Please select a due date for the task.", parent=self.root)
            except tk.TclError:
                logger.error("Validation Error: Due Date is required (messagebox error).")
            return

        task_due_datetime_iso = None
        due_hour_str = ""
        due_minute_str = ""

        if hasattr(self, 'input_widgets') and 'due_hour' in self.input_widgets:
            due_hour_str = self.input_widgets['due_hour'].get()
        if hasattr(self, 'input_widgets') and 'due_minute' in self.input_widgets:
            due_minute_str = self.input_widgets['due_minute'].get()

        if due_date_str:
            if not self.headless_mode and (not due_hour_str or not due_minute_str):
                logger.warning("Save Task Aborted: Due Time is required when Due Date is set.")
                try:
                    messagebox.showerror("Missing Time", "If Due Date is set, Due Time (HH:MM) must also be selected.", parent=self.root)
                except tk.TclError:
                     logger.error("Validation Error: Missing time for due date (messagebox error).")
                return

            if due_hour_str and due_minute_str:
                try:
                    dt_obj = datetime.datetime.strptime(f"{due_date_str} {due_hour_str}:{due_minute_str}", "%Y-%m-%d %H:%M")
                    task_due_datetime_iso = dt_obj.isoformat()
                except ValueError:
                    logger.warning(f"Save Task Aborted: Invalid date/time format for Due Date '{due_date_str}' and Time '{due_hour_str}:{due_minute_str}'.")
                    if not self.headless_mode:
                        try:
                            messagebox.showerror("Invalid Date/Time", "Due Date or Time is not valid. Please use YYYY-MM-DD format for date and select HH:MM for time.", parent=self.root)
                        except tk.TclError:
                            logger.error("Validation Error: Invalid date/time format (messagebox error).")
                    return
            elif self.headless_mode and not task_due_datetime_iso:
                logger.warning("Headless mode: Due date string present but time parts missing, and task_due_datetime_iso not pre-set.")

        if task_duration_total_minutes > 0 and not task_due_datetime_iso:
            if not self.headless_mode:
                logger.warning("Conflict check skipped: Due date/time not fully specified for a task with duration.")
            else:
                logger.info("Headless mode: Conflict check skipped as due date/time not provided for task with duration.")

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
                        if not self.headless_mode:
                             messagebox.showwarning("DB Warning", "Could not check for task conflicts. Save cautiously.", parent=self.root)
                    else:
                        existing_tasks = database_manager.get_all_tasks(conn_check)
                        perf_after_get_all_tasks = time.perf_counter()
                        logger.debug(f"Conflict Check Perf: Fetched all tasks for check at {perf_after_get_all_tasks:.4f}. DB query time: {perf_after_get_all_tasks - perf_start_conflict_check_section:.4f}s")
                        conflict_found = False
                        for existing_task in existing_tasks:
                            if self.currently_editing_task_id and existing_task.id == self.currently_editing_task_id:
                                continue
                            if existing_task.status == 'Completed':
                                continue
                            if not existing_task.due_date or not existing_task.duration or existing_task.duration == 0:
                                continue
                            try:
                                et_start_dt = datetime.datetime.fromisoformat(existing_task.due_date)
                                et_end_dt = et_start_dt + timedelta(minutes=existing_task.duration)
                            except ValueError:
                                logger.warning(f"Invalid date format for existing task ID {existing_task.id} ('{existing_task.due_date}'). Skipping in conflict check.")
                                continue
                            is_potential_conflict = False
                            existing_task_repetition = existing_task.repetition if existing_task.repetition else 'None'
                            if current_task_repetition == existing_task_repetition:
                                logger.debug(f"Conflict Check: Same repetition type ('{current_task_repetition}') for current task '{title_value}' and existing task '{existing_task.title}' (ID: {existing_task.id}). Performing specific check.")
                                if current_task_repetition == 'None':
                                    time_overlap_result = database_manager.check_timeslot_overlap(ct_start_dt, ct_end_dt, et_start_dt, et_end_dt)
                                    logger.debug(f"  ONE-TIME_VS_ONE-TIME Check for Current Task '{title_value}' vs Existing '{existing_task.title}':")
                                    logger.debug(f"    Current Task Slot: {ct_start_dt.isoformat()} - {ct_end_dt.isoformat()}")
                                    logger.debug(f"    Existing Task Slot: {et_start_dt.isoformat()} - {et_end_dt.isoformat()}")
                                    logger.debug(f"    check_timeslot_overlap returned: {time_overlap_result}")
                                    if time_overlap_result: is_potential_conflict = True
                                else:
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
                                        logger.debug(f"  {current_task_repetition.upper()}_VS_{current_task_repetition.upper()} Check for Current Task '{title_value}' vs Existing '{existing_task.title}':")
                                        if current_task_repetition != 'Daily': logger.debug(f"    Date parts match criteria (e.g., weekday, day of month).")
                                        logger.debug(f"    Current Task Time Slot (for check_time_only_overlap): {ct_start_time.isoformat()} - {ct_end_time_val.isoformat()}")
                                        logger.debug(f"    Existing Task Time Slot (for check_time_only_overlap): {et_start_time.isoformat()} - {et_end_time_val.isoformat()}")
                                        time_overlap_result = database_manager.check_time_only_overlap(ct_start_time, ct_end_time_val, et_start_time, et_end_time_val)
                                        logger.debug(f"    check_time_only_overlap returned: {time_overlap_result}")
                                        if time_overlap_result: is_potential_conflict = True
                                    else:
                                         logger.debug(f"  {current_task_repetition.upper()}_VS_{current_task_repetition.upper()} Check for Current Task '{title_value}' vs Existing '{existing_task.title}': Date parts do not match criteria. No time overlap check needed.")
                                logger.debug(f"  is_potential_conflict after {current_task_repetition} check: {is_potential_conflict}")
                            else:
                                logger.debug(f"Conflict Check: Different repetition types ('{current_task_repetition}' for current task '{title_value}' vs '{existing_task_repetition}' for existing task '{existing_task.title}' ID {existing_task.id}). No overlap check performed as per rules.")
                                is_potential_conflict = False
                            if is_potential_conflict:
                                logger.warning(f"Task conflict detected: Current task '{title_value}' ({current_task_repetition}) overlaps with existing task '{existing_task.title}' (ID: {existing_task.id}, Rep: {existing_task_repetition}).")
                                conflict_msg = (f"Task '{title_value}' ({ct_start_dt.strftime('%Y-%m-%d %H:%M')}, Rep: {current_task_repetition}) conflicts with existing task '{existing_task.title}' (ID: {existing_task.id}, Due: {et_start_dt.strftime('%Y-%m-%d %H:%M')}, Rep: {existing_task_repetition}, duration: {existing_task.duration} min). Please choose a different time, duration, or repetition.")
                                logger.warning(conflict_msg)
                                if not self.headless_mode: messagebox.showerror("Task Conflict", conflict_msg, parent=self.root)
                                else: logger.error(f"HEADLESS_SAVE_ERROR: {conflict_msg}")
                                conflict_found = True
                                break
                        if conflict_found:
                            perf_after_conflict_loop = time.perf_counter()
                            logger.debug(f"Conflict Check Perf: Finished conflict processing loop (conflict found) at {perf_after_conflict_loop:.4f}. Loop processing time: {perf_after_conflict_loop - perf_after_get_all_tasks:.4f}s")
                            if conn_check: conn_check.close()
                            return
                        perf_after_conflict_loop = time.perf_counter()
                        logger.debug(f"Conflict Check Perf: Finished conflict processing loop (no conflict found yet) at {perf_after_conflict_loop:.4f}. Loop processing time: {perf_after_conflict_loop - perf_after_get_all_tasks:.4f}s")
                except Exception as e_check:
                    logger.error(f"Error during conflict check: {e_check}", exc_info=True)
                    if not self.headless_mode: messagebox.showerror("Conflict Check Error", "An error occurred while checking for task conflicts. Saving aborted.", parent=self.root)
                    else: logger.error("HEADLESS_SAVE_ERROR: Conflict Check Error during save_task_action")
                    if conn_check: conn_check.close()
                    return
                finally:
                    if conn_check:
                        conn_check.close()
                        logger.debug("Conflict check DB connection closed.")
                perf_end_conflict_check_section = time.perf_counter()
                logger.debug(f"Conflict Check Perf: Exiting conflict check section (no conflict found) at {perf_end_conflict_check_section:.4f}. Total time in conflict check section: {perf_end_conflict_check_section - perf_start_conflict_check_section:.4f}s")
            except ValueError:
                 logger.error(f"Invalid due_date ('{task_due_datetime_iso}') for current task '{title_value}' during conflict check setup. Aborting save.", exc_info=True)
                 if not self.headless_mode: messagebox.showerror("Invalid Date", "The due date for the current task is invalid. Cannot save.", parent=self.root)
                 else: logger.error("HEADLESS_SAVE_ERROR: Invalid Date for current task for conflict check")
                 return

        priority_display_to_model_map = {"Low": 1, "Medium": 2, "High": 3}
        priority = priority_display_to_model_map.get(priority_str, 2)

        conn_save = None
        try:
            conn_save = database_manager.create_connection()
            if not conn_save:
                logger.error("DB Save Op: Failed to create database connection.")
                if not self.headless_mode:
                    messagebox.showerror("Database Error", "Cannot save task: DB connection failed.", parent=self.root)
                return

            database_manager.create_table(conn_save)

            if self.currently_editing_task_id is not None:
                logger.info(f"Attempting to update task ID: {self.currently_editing_task_id}")
                task_before_edit = None
                try:
                    task_before_edit = database_manager.get_task(conn_save, self.currently_editing_task_id)
                except Exception as e_fetch:
                    logger.error(f"Error fetching original task {self.currently_editing_task_id} for status check: {e_fetch}", exc_info=True)
                if task_before_edit is None:
                    logger.error(f"Original task (ID: {self.currently_editing_task_id}) not found. Cannot proceed with update or status check.")
                    if not self.headless_mode:
                        messagebox.showerror("Error", "Original task not found. Update failed.", parent=self.root)
                    return
                status_to_save = task_before_edit.status
                task_id_being_edited = self.currently_editing_task_id
                new_due_date_iso_from_form = task_due_datetime_iso
                if task_before_edit.status == 'Completed':
                    original_due_date_iso = task_before_edit.due_date
                    is_due_date_changed = (original_due_date_iso != new_due_date_iso_from_form)
                    if is_due_date_changed:
                        status_to_save = 'Pending'
                        logger.info(f"Task ID {task_before_edit.id} ('{task_before_edit.title}') was 'Completed'. Due date changed from '{original_due_date_iso}' to '{new_due_date_iso_from_form}'. Status auto-reverted to 'Pending'.")
                        if not self.headless_mode:
                            try: messagebox.showinfo("Status Changed", f"Task '{task_before_edit.title}' status has been reset to 'Pending' because its due date was changed.", parent=self.root)
                            except tk.TclError: logger.warning("Status Changed messagebox failed in UI mode.")
                updated_creation_date = task_before_edit.creation_date
                updated_last_reset_date = task_before_edit.last_reset_date
                task_data_obj = Task(id=self.currently_editing_task_id, title=title_value, description=description, duration=task_duration_total_minutes, creation_date=updated_creation_date, repetition=current_task_repetition, priority=priority, category=category, due_date=new_due_date_iso_from_form, status=status_to_save, last_reset_date=updated_last_reset_date)
                success = database_manager.update_task(conn_save, task_data_obj)
                if success:
                    logger.info(f"Task ID {task_id_being_edited} updated. Checking for active popup.")
                    if task_id_being_edited in self.active_popups:
                        active_popup_instance = self.active_popups.get(task_id_being_edited)
                        if active_popup_instance and active_popup_instance.winfo_exists():
                            logger.info(f"Closing active popup for updated task ID: {task_id_being_edited}")
                            active_popup_instance._cleanup_and_destroy()
                    try: messagebox.showinfo("Success", "Task updated successfully!", parent=self.root)
                    except tk.TclError: logger.info("Success: Task updated (messagebox not available).")
                    self.clear_form_fields_and_reset_state()
                    self.refresh_task_list()
                    self.request_reschedule_reminders()
                else:
                    try: messagebox.showerror("Error", "Failed to update task.", parent=self.root)
                    except tk.TclError: logger.error("Error: Failed to update task (messagebox not available).")
            else:
                logger.info("Attempting to add new task.")
                creation_date = datetime.datetime.now().isoformat()
                new_task_obj = Task(id=0, title=title_value, description=description, duration=task_duration_total_minutes, creation_date=creation_date, repetition=current_task_repetition, priority=priority, category=category, due_date=task_due_datetime_iso)
                task_id = database_manager.add_task(conn_save, new_task_obj)
                if task_id:
                    try: messagebox.showinfo("Success", f"Task saved successfully with ID: {task_id}!", parent=self.root)
                    except tk.TclError: logger.info(f"Success: Task saved ID {task_id} (messagebox not available).")
                    self.clear_form_fields_and_reset_state()
                    self.refresh_task_list()
                    self.request_reschedule_reminders()
                else:
                    try: messagebox.showerror("Error", "Failed to save task to database.", parent=self.root)
                    except tk.TclError: logger.error("Error: Failed to save task (messagebox not available).")
        except tk.TclError as e_tk:
             if not self.headless_mode: logger.error(f"A TclError occurred: {e_tk}. (Likely messagebox in headless environment)", exc_info=True)
             else: logger.warning(f"A TclError was suppressed in headless mode: {e_tk}")
        except Exception as e:
            error_message = f"An unexpected error occurred in save_task_action: {e}"
            logger.error(error_message, exc_info=True)
            if not self.headless_mode:
                try: messagebox.showerror("Error", error_message, parent=self.root)
                except tk.TclError: pass
        finally:
            if conn_save:
                conn_save.close()
                logger.debug("DB Save Op: Connection closed.")

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

    def _format_duration_display(self, total_minutes: int) -> str:
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
                        card.pack(pady=5, padx=5, fill=tk.X)
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
