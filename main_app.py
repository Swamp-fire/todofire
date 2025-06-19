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
import time
import sys

# Logging level will be set in if __name__ == '__main__'
logger = logging.getLogger(__name__)

class TaskManagerApp:
    def __init__(self, root_window, headless_mode=False):
        self.headless_mode = headless_mode
        self.root = root_window
        self.active_popups = {}

        logger.info(f"Initializing TaskManagerApp in {'HEADLESS' if self.headless_mode else 'GUI'} mode.")

        if not self.headless_mode and self.root:
            self.root.title("Task Manager")
            self.root.geometry("800x700")

        self.currently_editing_task_id = None
        self.input_widgets = {}
        self.task_tree = None
        self.save_button = None

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
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)

        form_frame = bs.Frame(self.root, padding=(20, 10))
        form_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        form_frame.columnconfigure(1, weight=1)

        title_label = bs.Label(master=form_frame, text="Title: *")
        title_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['title'] = ttk.Entry(master=form_frame, width=50)
        self.input_widgets['title'].grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        desc_label = bs.Label(master=form_frame, text="Description:")
        desc_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")
        self.input_widgets['description'] = tk.Text(master=form_frame, height=4, width=38)
        self.input_widgets['description'].grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        current_form_row = 2

        self.duration_h_m_label = bs.Label(form_frame, text="Duration:")
        self.duration_h_m_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        duration_frame = bs.Frame(form_frame)
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

        rep_label = bs.Label(master=form_frame, text="Repetition:")
        rep_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['repetition'] = ttk.Combobox(master=form_frame,
                                                        values=['None', 'Daily', 'Weekly', 'Monthly', 'Yearly'],
                                                        width=47, state="readonly")
        self.input_widgets['repetition'].set('None')
        self.input_widgets['repetition'].grid(row=current_form_row, column=1, padx=5, pady=5, sticky="ew")
        current_form_row += 1

        priority_label = bs.Label(master=form_frame, text="Priority:")
        priority_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['priority'] = ttk.Combobox(master=form_frame,
                                                      values=['Low', 'Medium', 'High'],
                                                      width=47, state="readonly")
        self.input_widgets['priority'].set('Medium')
        self.input_widgets['priority'].grid(row=current_form_row, column=1, padx=5, pady=5, sticky="ew")
        current_form_row += 1

        category_label = bs.Label(master=form_frame, text="Category:")
        category_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['category'] = ttk.Entry(master=form_frame, width=50)
        self.input_widgets['category'].grid(row=current_form_row, column=1, padx=5, pady=5, sticky="ew")
        current_form_row += 1

        due_date_label = bs.Label(master=form_frame, text="Due Date:")
        due_date_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['due_date'] = bs.DateEntry(form_frame, dateformat="%Y-%m-%d", firstweekday=0)
        self.input_widgets['due_date'].grid(row=current_form_row, column=1, padx=5, pady=5, sticky="ew")
        current_form_row += 1

        due_time_label = bs.Label(master=form_frame, text="Due Time (HH:MM):")
        due_time_label.grid(row=current_form_row, column=0, padx=5, pady=5, sticky="w")
        time_frame = bs.Frame(form_frame)
        time_frame.grid(row=current_form_row, column=1, padx=0, pady=5, sticky="ew")
        self.input_widgets['due_hour'] = ttk.Combobox(master=time_frame, state="readonly", width=5,
                                                      values=[f"{h:02d}" for h in range(24)])
        self.input_widgets['due_hour'].set("12")
        self.input_widgets['due_hour'].pack(side=tk.LEFT, padx=(5,2))
        time_separator_label = bs.Label(master=time_frame, text=":")
        time_separator_label.pack(side=tk.LEFT, padx=0)
        self.input_widgets['due_minute'] = ttk.Combobox(master=time_frame, state="readonly", width=5,
                                                        values=[f"{m:02d}" for m in range(0, 60, 5)])
        self.input_widgets['due_minute'].set("00")
        self.input_widgets['due_minute'].pack(side=tk.LEFT, padx=(2,5))
        current_form_row += 1

        button_frame = bs.Frame(form_frame)
        button_frame.grid(row=current_form_row, column=0, columnspan=2, pady=10)
        self.save_button = bs.Button(master=button_frame, text="Save Task",
                                     command=self.save_task_action, bootstyle="success")
        self.save_button.pack(side=tk.LEFT, padx=(0, 5))
        clear_button = bs.Button(master=button_frame, text="Clear Form",
                                 command=self.clear_form_fields_and_reset_state, bootstyle="warning")
        clear_button.pack(side=tk.LEFT)

        tree_container_frame = bs.Frame(self.root, padding=(0, 10, 0, 0))
        tree_container_frame.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))
        tree_container_frame.columnconfigure(0, weight=1)
        tree_container_frame.rowconfigure(2, weight=1)

        list_title_label = bs.Label(tree_container_frame, text="Task List", font=("-size 12 -weight bold"))
        list_title_label.grid(row=0, column=0, sticky='w', padx=5, pady=(0, 5))

        list_action_button_frame = bs.Frame(tree_container_frame)
        list_action_button_frame.grid(row=1, column=0, sticky='w', padx=5, pady=(0, 5))
        edit_button = bs.Button(list_action_button_frame, text="Edit Selected",
                                command=self.load_selected_task_for_edit, bootstyle="info")
        edit_button.pack(side=tk.LEFT, padx=(0, 5))
        delete_button = bs.Button(list_action_button_frame, text="Delete Selected",
                                  command=self.delete_selected_task, bootstyle="danger")
        delete_button.pack(side=tk.LEFT, padx=(0, 5))

        self.task_tree = None
        tree_frame = ttk.Frame(tree_container_frame)
        tree_frame.grid(row=2, column=0, sticky='nsew', padx=5, pady=0)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Use self.tree_columns defined in __init__
        self.task_tree = ttk.Treeview(tree_frame, columns=self.tree_columns, show="headings", selectmode="browse")

        # Configure columns based on self.tree_columns
        # Order: ("id", "title", "status", "priority", "due_date", "repetition", "duration_display", "category")

        self.task_tree.heading("id", text="ID", anchor='w')
        self.task_tree.column("id", width=40, minwidth=30, stretch=tk.NO)

        self.task_tree.heading("title", text="Title", anchor='w')
        self.task_tree.column("title", width=200, minwidth=100, stretch=tk.YES)

        self.task_tree.heading("status", text="Status", anchor='w')
        self.task_tree.column("status", width=80, minwidth=70, stretch=tk.NO)

        self.task_tree.heading("priority", text="Priority", anchor='w')
        self.task_tree.column("priority", width=70, minwidth=60, stretch=tk.NO)

        self.task_tree.heading("due_date", text="Due Date", anchor='w')
        self.task_tree.column("due_date", width=120, minwidth=100, stretch=tk.NO)

        self.task_tree.heading("repetition", text="Repeats", anchor='w')
        self.task_tree.column("repetition", width=80, minwidth=70, stretch=tk.NO)

        self.task_tree.heading("duration_display", text="Work Time", anchor='w')
        self.task_tree.column("duration_display", width=80, minwidth=70, stretch=tk.NO)

        self.task_tree.heading("category", text="Category", anchor='w')
        self.task_tree.column("category", width=100, minwidth=80, stretch=tk.NO)
        # "creation_date" column configuration is removed.

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky='ns')
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.task_tree.xview)
        self.task_tree.configure(xscrollcommand=hsb.set)
        hsb.grid(row=1, column=0, sticky='ew')
        self.task_tree.grid(row=0, column=0, sticky='nsew')

    def clear_form_fields_and_reset_state(self):
        if self.headless_mode:
            self.currently_editing_task_id = None
            logger.info("Form fields state reset (headless mode).")
            return

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
        if self.save_button:
            self.save_button.config(text="Save Task")
        logger.info("Form fields cleared and state reset.")

    def load_selected_task_for_edit(self):
        if self.headless_mode:
            logger.warning("load_selected_task_for_edit called in headless_mode. UI not available.")
            return
        selected_item_iid = self.task_tree.focus()
        if not selected_item_iid:
            try:
                messagebox.showwarning("No Selection", "Please select a task from the list to edit.", parent=self.root)
            except tk.TclError: logger.warning("No task selected for editing (messagebox not available).")
            return
        try:
            task_id = int(selected_item_iid)
        except ValueError:
            try:
                messagebox.showerror("Error", "Invalid task ID selected.", parent=self.root)
            except tk.TclError: logger.error("Invalid task ID selected (messagebox not available).")
            return

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
                except ValueError:
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

        title_value = self.input_widgets['title'].get().strip() # Used in logging
        if not title_value:
            try:
                messagebox.showerror("Validation Error", "Title field cannot be empty.", parent=self.root)
            except tk.TclError: logger.error("Validation Error: Title is empty (messagebox not available).")
            return

        description = self.input_widgets['description'].get("1.0", tk.END).strip()
        current_task_repetition = self.input_widgets['repetition'].get() # Renamed from 'repetition' for clarity in this function
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

        # Due Date Presence Validation (New)
        due_date_str = ""
        # Guard UI widget access for headless mode or if input_widgets is not populated
        if hasattr(self, 'input_widgets') and 'due_date' in self.input_widgets and self.input_widgets['due_date'].entry:
            due_date_str = self.input_widgets['due_date'].entry.get().strip()

        # This validation applies only when UI is present and due_date_str is empty
        if not self.headless_mode and not due_date_str:
            logger.warning("Save Task Aborted: Due Date is required.")
            try:
                messagebox.showerror("Validation Error",
                                     "Due Date is required. Please select a due date for the task.",
                                     parent=self.root)
            except tk.TclError: # Should not happen if not headless, but good practice
                logger.error("Validation Error: Due Date is required (messagebox error).")
            return

        # Due Time Validation (existing, but now only relevant if due_date_str was provided or if headless)
        task_due_datetime_iso = None
        due_hour_str = ""
        due_minute_str = ""

        if hasattr(self, 'input_widgets') and 'due_hour' in self.input_widgets:
            due_hour_str = self.input_widgets['due_hour'].get()
        if hasattr(self, 'input_widgets') and 'due_minute' in self.input_widgets:
            due_minute_str = self.input_widgets['due_minute'].get()

        if due_date_str: # If due_date_str is not empty (it passed the above check or we are headless and it might be something)
            # In UI mode, if date is set, time must be set
            if not self.headless_mode and (not due_hour_str or not due_minute_str):
                logger.warning("Save Task Aborted: Due Time is required when Due Date is set.")
                try:
                    messagebox.showerror("Missing Time",
                                         "If Due Date is set, Due Time (HH:MM) must also be selected.",
                                         parent=self.root)
                except tk.TclError:
                     logger.error("Validation Error: Missing time for due date (messagebox error).")
                return

            # If we are here, either headless or (UI mode with date and time parts present)
            # Attempt to parse if both date and time parts are available (especially for UI path)
            # Headless path might rely on task_due_datetime_iso being set differently if it's pre-validated
            if due_hour_str and due_minute_str: # Ensure time parts are available for parsing
                try:
                    dt_obj = datetime.datetime.strptime(f"{due_date_str} {due_hour_str}:{due_minute_str}", "%Y-%m-%d %H:%M")
                    task_due_datetime_iso = dt_obj.isoformat()
                except ValueError:
                    logger.warning(f"Save Task Aborted: Invalid date/time format for Due Date '{due_date_str}' and Time '{due_hour_str}:{due_minute_str}'.")
                    if not self.headless_mode:
                        try:
                            messagebox.showerror("Invalid Date/Time",
                                                 "Due Date or Time is not valid. Please use YYYY-MM-DD format for date and select HH:MM for time.",
                                                 parent=self.root)
                        except tk.TclError:
                            logger.error("Validation Error: Invalid date/time format (messagebox error).")
                    return
            elif self.headless_mode and not task_due_datetime_iso:
                # This case implies headless mode, due_date_str might be present but time parts were not,
                # and task_due_datetime_iso wasn't pre-set. This might indicate an issue with headless data prep.
                logger.warning("Headless mode: Due date string present but time parts missing, and task_due_datetime_iso not pre-set.")

        # Conflict Check Logic
        # Ensure task_due_datetime_iso is set if duration > 0 for conflict check
        if task_duration_total_minutes > 0 and not task_due_datetime_iso:
            if not self.headless_mode: # In UI mode, this implies due date was set but time was not, which should be caught above.
                                       # Or, due date was not set, but this new validation makes due_date mandatory.
                logger.warning("Conflict check skipped: Due date/time not fully specified for a task with duration.")
                # Given new mandatory due date, this path might change. If due_date is mandatory,
                # and time is mandatory if date is set, then task_due_datetime_iso should always be set here.
                # If it's not, it's an error caught by prior validation.
            else: # Headless mode
                logger.info("Headless mode: Conflict check skipped as due date/time not provided for task with duration.")

        if task_duration_total_minutes > 0 and task_due_datetime_iso:
            perf_start_conflict_check_section = time.perf_counter()
            logger.debug(f"Conflict Check Perf: Entering conflict check section at {perf_start_conflict_check_section:.4f}")
            try:
                ct_start_dt = datetime.datetime.fromisoformat(task_due_datetime_iso) # Renamed for clarity
                ct_end_dt = ct_start_dt + timedelta(minutes=task_duration_total_minutes) # Renamed for clarity
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
                        logger.debug(f"Conflict Check Perf: Fetched all tasks for check at {perf_after_get_all_tasks:.4f}. "
                                     f"DB query time: {perf_after_get_all_tasks - perf_start_conflict_check_section:.4f}s")

                        conflict_found = False # Overall flag for this save operation
                        for existing_task in existing_tasks:
                            if self.currently_editing_task_id and existing_task.id == self.currently_editing_task_id:
                                continue
                            if existing_task.status == 'Completed':
                                continue
                            if not existing_task.due_date or not existing_task.duration or existing_task.duration == 0:
                                continue

                            try:
                                et_start_dt = datetime.datetime.fromisoformat(existing_task.due_date) # Renamed
                                et_end_dt = et_start_dt + timedelta(minutes=existing_task.duration) # Renamed
                            except ValueError:
                                logger.warning(f"Invalid date format for existing task ID {existing_task.id} ('{existing_task.due_date}'). Skipping in conflict check.")
                                continue

                            # Emergency Plan Step 2: Corrected Conflict Check Logic
                            is_potential_conflict = False # Initialize for this pair comparison
                            # current_task_repetition is already defined from form input ('repetition' aliased to current_task_repetition earlier)
                            existing_task_repetition = existing_task.repetition if existing_task.repetition else 'None' # Normalize

                            if current_task_repetition == existing_task_repetition:
                                logger.debug(f"Conflict Check: Same repetition type ('{current_task_repetition}') "
                                             f"for current task '{title_value}' and existing task '{existing_task.title}' (ID: {existing_task.id}). Performing specific check.")
                                if current_task_repetition == 'None': # One-Time vs One-Time
                                    time_overlap_result = database_manager.check_timeslot_overlap(
                                        ct_start_dt, ct_end_dt,
                                        et_start_dt, et_end_dt
                                    )
                                    logger.debug(f"  ONE-TIME_VS_ONE-TIME Check for Current Task '{title_value}' vs Existing '{existing_task.title}':")
                                    logger.debug(f"    Current Task Slot: {ct_start_dt.isoformat()} - {ct_end_dt.isoformat()}")
                                    logger.debug(f"    Existing Task Slot: {et_start_dt.isoformat()} - {et_end_dt.isoformat()}")
                                    logger.debug(f"    check_timeslot_overlap returned: {time_overlap_result}")
                                    if time_overlap_result:
                                        is_potential_conflict = True

                                else: # Handles 'Daily', 'Weekly', 'Monthly', 'Yearly' all using check_time_only_overlap
                                    # Prepare time components for check_time_only_overlap
                                    ct_start_time = ct_start_dt.time()
                                    ct_end_time_val = (ct_start_dt + timedelta(minutes=task_duration_total_minutes)).time()
                                    et_start_time = et_start_dt.time()
                                    et_end_time_val = (et_start_dt + timedelta(minutes=existing_task.duration)).time()

                                    specific_match_criteria = False # Corrected variable name
                                    if current_task_repetition == 'Daily':
                                        specific_match_criteria = True # Always check time for daily
                                    elif current_task_repetition == 'Weekly':
                                        if ct_start_dt.weekday() == et_start_dt.weekday():
                                            specific_match_criteria = True
                                    elif current_task_repetition == 'Monthly':
                                        if ct_start_dt.day == et_start_dt.day:
                                            specific_match_criteria = True
                                    elif current_task_repetition == 'Yearly':
                                        if ct_start_dt.month == et_start_dt.month and ct_start_dt.day == et_start_dt.day:
                                            specific_match_criteria = True

                                    if specific_match_criteria:
                                        logger.debug(f"  {current_task_repetition.upper()}_VS_{current_task_repetition.upper()} Check for Current Task '{title_value}' vs Existing '{existing_task.title}':")
                                        if current_task_repetition != 'Daily': # Log date part match for non-Daily repeating
                                            logger.debug(f"    Date parts match criteria (e.g., weekday, day of month).")
                                        logger.debug(f"    Current Task Time Slot (for check_time_only_overlap): {ct_start_time.isoformat()} - {ct_end_time_val.isoformat()}")
                                        logger.debug(f"    Existing Task Time Slot (for check_time_only_overlap): {et_start_time.isoformat()} - {et_end_time_val.isoformat()}")

                                        time_overlap_result = database_manager.check_time_only_overlap(
                                            ct_start_time, ct_end_time_val,
                                            et_start_time, et_end_time_val
                                        )
                                        logger.debug(f"    check_time_only_overlap returned: {time_overlap_result}")
                                        if time_overlap_result:
                                            is_potential_conflict = True
                                    else:
                                         logger.debug(f"  {current_task_repetition.upper()}_VS_{current_task_repetition.upper()} Check for Current Task '{title_value}' vs Existing '{existing_task.title}': Date parts do not match criteria. No time overlap check needed.")

                                logger.debug(f"  is_potential_conflict after {current_task_repetition} check: {is_potential_conflict}")

                            else: # current_task_repetition != existing_task_repetition
                                logger.debug(f"Conflict Check: Different repetition types ('{current_task_repetition}' for current task '{title_value}' "
                                             f"vs '{existing_task_repetition}' for existing task '{existing_task.title}' ID {existing_task.id}). "
                                             f"No overlap check performed as per rules.")
                                is_potential_conflict = False # Explicitly ensure it's false

                            if is_potential_conflict:
                                logger.warning(f"Task conflict detected: Current task '{title_value}' ({current_task_repetition}) overlaps with existing task '{existing_task.title}' (ID: {existing_task.id}, Rep: {existing_task_repetition}).")
                                conflict_msg = (f"Task '{title_value}' ({ct_start_dt.strftime('%Y-%m-%d %H:%M')}, Rep: {current_task_repetition}) "
                                                f"conflicts with existing task '{existing_task.title}' (ID: {existing_task.id}, Due: {et_start_dt.strftime('%Y-%m-%d %H:%M')}, Rep: {existing_task_repetition}, "
                                                f"duration: {existing_task.duration} min). Please choose a different time, duration, or repetition.")
                                logger.warning(conflict_msg) # Log the specific conflict
                                if not self.headless_mode:
                                    messagebox.showerror("Task Conflict", conflict_msg, parent=self.root)
                                else:
                                    logger.error(f"HEADLESS_SAVE_ERROR: {conflict_msg}")
                                conflict_found = True # Set overall flag for this save operation
                                break # Exit the loop for existing_tasks

                        if conflict_found: # If any pair caused a conflict
                            perf_after_conflict_loop = time.perf_counter() # Log before returning due to conflict
                            logger.debug(f"Conflict Check Perf: Finished conflict processing loop (conflict found) at {perf_after_conflict_loop:.4f}. "
                                         f"Loop processing time: {perf_after_conflict_loop - perf_after_get_all_tasks:.4f}s")
                            if conn_check: conn_check.close()
                            return # Abort save_task_action

                        # This point is reached if loop completed without finding any conflict
                        perf_after_conflict_loop = time.perf_counter()
                        logger.debug(f"Conflict Check Perf: Finished conflict processing loop (no conflict found yet) at {perf_after_conflict_loop:.4f}. "
                                     f"Loop processing time: {perf_after_conflict_loop - perf_after_get_all_tasks:.4f}s")

                except Exception as e_check:
                    logger.error(f"Error during conflict check: {e_check}", exc_info=True)
                    if not self.headless_mode:
                        messagebox.showerror("Conflict Check Error", "An error occurred while checking for task conflicts. Saving aborted.", parent=self.root)
                    else:
                        logger.error("HEADLESS_SAVE_ERROR: Conflict Check Error during save_task_action")
                    if conn_check: conn_check.close() # Ensure close on this path too
                    return
                finally: # This finally block is for the inner try/except that includes get_all_tasks and the loop
                    if conn_check:
                        conn_check.close()
                        logger.debug("Conflict check DB connection closed.")

                # If we reach here, no conflict was found in the loop and no exception in DB connection/query
                perf_end_conflict_check_section = time.perf_counter()
                logger.debug(f"Conflict Check Perf: Exiting conflict check section (no conflict found) at {perf_end_conflict_check_section:.4f}. "
                             f"Total time in conflict check section: {perf_end_conflict_check_section - perf_start_conflict_check_section:.4f}s")

            except ValueError: # This is for the outer try, if fromisoformat fails
                 logger.error(f"Invalid due_date ('{task_due_datetime_iso}') for current task '{title_value}' during conflict check setup. Aborting save.", exc_info=True)
                 if not self.headless_mode:
                     messagebox.showerror("Invalid Date", "The due date for the current task is invalid. Cannot save.", parent=self.root)
                 else:
                     logger.error("HEADLESS_SAVE_ERROR: Invalid Date for current task for conflict check")
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

                # Fetch the original task from the database (Instruction 3.a)
                task_before_edit = None
                # conn_fetch is distinct from conn_save; using conn_save for this fetch
                try:
                    task_before_edit = database_manager.get_task(conn_save, self.currently_editing_task_id)
                except Exception as e_fetch:
                    logger.error(f"Error fetching original task {self.currently_editing_task_id} for status check: {e_fetch}", exc_info=True)
                    # No need to close conn_save here, will be closed in outer finally

                if task_before_edit is None:
                    logger.error(f"Original task (ID: {self.currently_editing_task_id}) not found. Cannot proceed with update or status check.")
                    if not self.headless_mode:
                        messagebox.showerror("Error", "Original task not found. Update failed.", parent=self.root)
                    return # Critical error, cannot proceed

                # Status Reset Logic (Instruction 4.a)
                # Determine the status to be saved
                status_to_save = task_before_edit.status # Default to original status

                # task_due_datetime_iso is the new due date string from the form (or None if cleared/invalid)
                new_due_date_iso_from_form = task_due_datetime_iso

                if task_before_edit.status == 'Completed':
                    original_due_date_iso = task_before_edit.due_date

                    is_due_date_changed = (original_due_date_iso != new_due_date_iso_from_form)

                    if is_due_date_changed:
                        status_to_save = 'Pending'
                        logger.info(f"Task ID {task_before_edit.id} ('{task_before_edit.title}') was 'Completed'. "
                                    f"Due date changed from '{original_due_date_iso}' to '{new_due_date_iso_from_form}'. "
                                    f"Status auto-reverted to 'Pending'.")
                        if not self.headless_mode:
                            try:
                                messagebox.showinfo("Status Changed",
                                                  f"Task '{task_before_edit.title}' status has been reset to 'Pending' "
                                                  "because its due date was changed.",
                                                  parent=self.root)
                            except tk.TclError: # Should not happen if not headless
                                logger.warning("Status Changed messagebox failed in UI mode.")

                # Use task_before_edit for creation_date and last_reset_date
                updated_creation_date = task_before_edit.creation_date
                updated_last_reset_date = task_before_edit.last_reset_date
                # current_status is now status_to_save

                task_data_obj = Task(id=self.currently_editing_task_id, title=title_value, description=description,
                                 duration=task_duration_total_minutes, creation_date=updated_creation_date,
                                 repetition=current_task_repetition, priority=priority, category=category,
                                 due_date=new_due_date_iso_from_form, status=status_to_save, # Use status_to_save and new_due_date
                                 last_reset_date=updated_last_reset_date)
                success = database_manager.update_task(conn_save, task_data_obj)
                if success:
                    try:
                        messagebox.showinfo("Success", "Task updated successfully!", parent=self.root)
                    except tk.TclError: logger.info("Success: Task updated (messagebox not available).")
                    self.clear_form_fields_and_reset_state()
                    self.refresh_task_list()
                    self.request_reschedule_reminders()
                else:
                    try:
                        messagebox.showerror("Error", "Failed to update task.", parent=self.root)
                    except tk.TclError: logger.error("Error: Failed to update task (messagebox not available).")
            else:
                logger.info("Attempting to add new task.")
                creation_date = datetime.datetime.now().isoformat()
                new_task_obj = Task(id=0, title=title_value, description=description, duration=task_duration_total_minutes,
                                creation_date=creation_date, repetition=current_task_repetition, priority=priority, category=category, # Use current_task_repetition
                                due_date=task_due_datetime_iso)
                task_id = database_manager.add_task(conn_save, new_task_obj)
                if task_id:
                    try:
                        messagebox.showinfo("Success", f"Task saved successfully with ID: {task_id}!", parent=self.root)
                    except tk.TclError: logger.info(f"Success: Task saved ID {task_id} (messagebox not available).")
                    self.clear_form_fields_and_reset_state()
                    self.refresh_task_list()
                    self.request_reschedule_reminders()
                else:
                    try:
                        messagebox.showerror("Error", "Failed to save task to database.", parent=self.root)
                    except tk.TclError: logger.error("Error: Failed to save task (messagebox not available).")
        except tk.TclError as e_tk:
             if not self.headless_mode:
                logger.error(f"A TclError occurred: {e_tk}. (Likely messagebox in headless environment)", exc_info=True)
             else:
                logger.warning(f"A TclError was suppressed in headless mode: {e_tk}")

        except Exception as e:
            error_message = f"An unexpected error occurred in save_task_action: {e}"
            logger.error(error_message, exc_info=True)
            if not self.headless_mode:
                try:
                    messagebox.showerror("Error", error_message, parent=self.root)
                except tk.TclError: pass
        finally:
            if conn_save:
                conn_save.close()
                logger.debug("DB Save Op: Connection closed.")


    def delete_selected_task(self):
        if self.headless_mode:
            logger.warning("delete_selected_task called in headless_mode. UI not available.")
            return
        selected_item_iid = self.task_tree.focus()
        if not selected_item_iid:
            try:
                messagebox.showwarning("No Selection", "Please select a task from the list to delete.", parent=self.root)
            except tk.TclError: logger.warning("No task selected for deletion (messagebox not available).")
            return
        try:
            task_id = int(selected_item_iid)
        except ValueError:
            try:
                messagebox.showerror("Error", "Invalid task ID in selection.", parent=self.root)
            except tk.TclError: logger.error("Invalid task ID in selection (messagebox not available).")
            return

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
                try:
                    messagebox.showerror("Database Error", "Could not connect to the database.", parent=self.root)
                except tk.TclError: logger.error("DB Error: Could not connect for deletion (messagebox not available).")
                return
            success = database_manager.delete_task(conn, task_id)
            if success:
                try:
                    messagebox.showinfo("Success", f"Task ID: {task_id} deleted successfully!", parent=self.root)
                except tk.TclError: logger.info(f"Success: Task {task_id} deleted (messagebox not available).")
                self.refresh_task_list()
                if self.currently_editing_task_id == task_id:
                    self.clear_form_fields_and_reset_state()
                self.request_reschedule_reminders()
            else:
                try:
                    messagebox.showerror("Error", f"Failed to delete task ID: {task_id}.", parent=self.root)
                except tk.TclError: logger.error(f"Error: Failed to delete task {task_id} (messagebox not available).")
        except Exception as e:
            error_msg = f"Failed to delete task: {e}"
            try:
                messagebox.showerror("Error", error_msg, parent=self.root)
            except tk.TclError: logger.error(f"Error: {error_msg} (messagebox not available).")
            logger.error(f"Error in delete_selected_task: {e}", exc_info=True)
        finally:
            if conn: conn.close()

    def _format_duration_display(self, total_minutes: int) -> str:
        if total_minutes is None or total_minutes < 0:
            return "-"
        if total_minutes == 0:
            return "-" # Consistent with previous plan to show "-" for 0m

        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        else: # minutes > 0 (total_minutes > 0 implies minutes > 0 if hours == 0)
            return f"{minutes}m"

    def refresh_task_list(self):
        if self.headless_mode:
            logger.debug("refresh_task_list called in headless_mode. Skipping UI Treeview update.")
            return
        if not self.task_tree:
            logger.error("Error: task_tree not initialized. Cannot refresh.")
            return
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        conn = None
        try:
            conn = database_manager.create_connection()
            if conn is None:
                logger.error("Database Error: Could not connect to refresh tasks.")
                if not self.headless_mode:
                    try:
                        messagebox.showerror("Database Error", "Could not connect to the database to refresh tasks.", parent=self.root)
                    except tk.TclError: pass
                return
            database_manager.create_table(conn)
            tasks = database_manager.get_all_tasks(conn)
            for task in tasks:
                priority_display_val = self.priority_map_display.get(task.priority, str(task.priority))
                display_due_date = ""
                if task.due_date:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(task.due_date)
                        display_due_date = dt_obj.strftime("%Y-%m-%d %H:%M")
                    except ValueError:
                        display_due_date = task.due_date # Show raw if format error

                repetition_display = task.repetition if task.repetition and task.repetition.strip().lower() != 'none' and task.repetition.strip() else "One-Time"
                duration_str = self._format_duration_display(task.duration)

                # Order must match self.tree_columns:
                # ("id", "title", "status", "priority", "due_date", "repetition", "duration_display", "category")
                values_to_insert = (
                    task.id,
                    task.title,
                    task.status,
                    priority_display_val,
                    display_due_date,
                    repetition_display,
                    duration_str,
                    task.category
                )
                self.task_tree.insert("", tk.END, iid=str(task.id), values=values_to_insert)
            logger.info(f"Task list refreshed. {len(tasks)} tasks loaded.")
        except Exception as e:
            error_message = f"Error refreshing task list: {e}"
            logger.error(error_message, exc_info=True)
            if not self.headless_mode:
                try:
                    messagebox.showerror("Error", error_message, parent=self.root)
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
                self.scheduler.add_job(
                    scheduler_manager.schedule_task_reminders,
                    trigger='date',
                    run_date=run_time,
                    args=[self.scheduler, self.reminder_queue],
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=60
                )
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
                    app_callbacks = {
                        'reschedule': self.handle_reschedule_task,
                        'complete': self.handle_complete_task,
                        'remove_from_active': self._remove_popup_from_active,
                        'request_wrap_position': self._calculate_next_wrap_position # Add this line
                    }
                    # Default position for the first popup or if stacking resets
                    default_target_x = 1530
                    default_target_y = 200
                    popup_initial_height = 85 # This is ReminderPopupUI's self.initial_height
                    vertical_gap = popup_initial_height + 5 # Make gap full height + 5px margin

                    next_y_position = default_target_y

                    logger.debug(f"POPUP_POS: Initial next_y_position for task {task_id}: {next_y_position}")
                    logger.debug(f"POPUP_POS: Active popups found: {len(self.active_popups)}")

                    current_max_y = default_target_y
                    if self.active_popups:
                        active_popup_log_details = [] # For logging
                        # Create a list of popups that currently exist to avoid issues if a popup is destroyed mid-iteration
                        valid_popups_for_calc = []
                        for p_id, p_inst in self.active_popups.items():
                            if p_inst.winfo_exists():
                                valid_popups_for_calc.append({'id': p_id, 'instance': p_inst})
                            else:
                                active_popup_log_details.append(f"id={p_id}, winfo_exists is False")

                        processed_popup_count = 0
                        for item in valid_popups_for_calc:
                            active_popup_id = item['id']
                            p_instance = item['instance']
                            # Double check winfo_exists() again in case it was destroyed since list creation
                            if p_instance.winfo_exists():
                                try:
                                    p_y = p_instance.winfo_y()
                                    p_height = p_instance.winfo_height()
                                    p_bottom_y = p_y + p_height
                                    active_popup_log_details.append(f"id={active_popup_id}, y={p_y}, h={p_height}, bottom={p_bottom_y}")
                                    current_max_y = max(current_max_y, p_bottom_y)
                                    processed_popup_count +=1
                                except tk.TclError:
                                    logger.warning(f"POPUP_POS: TclError getting geometry for active popup {active_popup_id} (task {task_id}).")
                                    active_popup_log_details.append(f"id={active_popup_id}, error getting geometry")
                            else:
                                # This case should be less common due to pre-filtering, but good to log
                                active_popup_log_details.append(f"id={active_popup_id}, disappeared during processing")

                        logger.debug(f"POPUP_POS: Details of active popups for task {task_id}: [{'; '.join(active_popup_log_details)}]")
                        logger.debug(f"POPUP_POS: current_max_y after iterating {processed_popup_count} active popups for task {task_id}: {current_max_y}")

                        if processed_popup_count == 0: # No popups were actually processed (all might have disappeared or errored)
                             next_y_position = default_target_y
                             logger.debug(f"POPUP_POS: No existing popups could be processed for task {task_id}, next_y set to default: {next_y_position}")
                        elif current_max_y >= default_target_y :
                            next_y_position = current_max_y + vertical_gap
                            logger.debug(f"POPUP_POS: Popups exist for task {task_id}, next_y set to {current_max_y} + {vertical_gap} = {next_y_position}")
                        else: # current_max_y is less than default_target_y (e.g. all are higher)
                             next_y_position = default_target_y # Or default_target_y if logic intends to always start at least at default_y
                             logger.debug(f"POPUP_POS: current_max_y ({current_max_y}) is less than default ({default_target_y}) for task {task_id}. next_y set to default: {next_y_position}")


                    # Screen boundary check
                    try:
                        screen_height = self.root.winfo_screenheight()
                        bottom_margin = 50
                        logger.debug(f"POPUP_POS: Screen height: {screen_height}. Checking boundary for task {task_id} with y={next_y_position}, h={popup_initial_height}, margin={bottom_margin}")
                        if next_y_position + popup_initial_height + bottom_margin > screen_height:
                            logger.info(f"POPUP_POS: Calculated Y position {next_y_position} for task {task_id} too low, resetting to default {default_target_y}.")
                            next_y_position = default_target_y
                        else:
                            logger.debug(f"POPUP_POS: Y position {next_y_position} for task {task_id} is within screen boundary.")
                    except tk.TclError as e:
                        logger.warning(f"POPUP_POS: Could not get screen height for boundary check (task {task_id}): {e}. Using Y={next_y_position} without check.")
                    except AttributeError as e:
                        logger.warning(f"POPUP_POS: self.root not available for screen height check (task {task_id}): {e}. Using Y={next_y_position} without check.")

                    logger.info(f"POPUP_POS: Final calculated new popup position for task {task_id}: X={default_target_x}, Y={next_y_position}")

                    # Instantiate ReminderPopupUI with calculated positions
                    popup = ReminderPopupUI(self.root,
                                              task_details,
                                              app_callbacks,
                                              target_x=default_target_x,
                                              target_y=next_y_position)
                    self.active_popups[task_id] = popup
                    logger.info(f"ReminderPopupUI created for task ID {task_id} at X={default_target_x}, Y={next_y_position} and added to active_popups.")

        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Error processing reminder queue: {e}", exc_info=True)

        if not self.headless_mode and self.root and self.root.winfo_exists():
             self.root.after(250, self._check_reminder_queue)

    def _calculate_next_wrap_position(self, wrapping_popup_id):
        logger.debug(f"POPUP_WRAP_POS: Calculating next wrap position for popup ID: {wrapping_popup_id}")

        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
        except tk.TclError:
            logger.warning("POPUP_WRAP_POS: Could not get screen dimensions, using fallback for base wrap corner.")
            screen_w = 1920
            screen_h = 1080

        # Dimensions and padding for wrapped popups (from reminder_popup_ui.py)
        wrapped_width = 110
        wrapped_height = 40
        edge_padding = 10 # Horizontal padding from screen edge
        bottom_padding = 40 # Vertical padding from screen bottom (for the first popup)
        inter_popup_gap = 5 # Vertical gap between stacked wrapped popups

        base_x = screen_w - wrapped_width - edge_padding
        base_y = screen_h - wrapped_height - bottom_padding

        next_wrap_x = base_x # X position is fixed for vertical stacking from a corner
        next_wrap_y = base_y

        # Find Y positions of already wrapped popups that are at base_x
        occupied_y_at_base_x = []
        for popup_id, p_instance in self.active_popups.items():
            if isinstance(p_instance, ReminderPopupUI) and \
               p_instance.is_in_wrapped_state and \
               p_instance.winfo_exists() and \
               popup_id != wrapping_popup_id: # Exclude the one currently being wrapped
                try:
                    if p_instance.winfo_x() == base_x: # Only consider those in the same column
                        occupied_y_at_base_x.append(p_instance.winfo_y())
                except tk.TclError:
                    logger.warning(f"POPUP_WRAP_POS: TclError getting geometry for wrapped popup {popup_id}")

        if occupied_y_at_base_x:
            occupied_y_at_base_x.sort() # Sorts from smallest Y (top-most) to largest Y (bottom-most)
            # We want to place the new one above the highest (smallest Y value) existing one in the stack
            highest_occupied_y = occupied_y_at_base_x[0] # Smallest Y is the top of the current stack
            next_wrap_y = highest_occupied_y - wrapped_height - inter_popup_gap
            logger.debug(f"POPUP_WRAP_POS: Other wrapped popups found at X={base_x}. Highest Y={highest_occupied_y}. New next_wrap_y={next_wrap_y}")
        else:
            logger.debug(f"POPUP_WRAP_POS: No other wrapped popups at X={base_x}. Using base_y: {next_wrap_y}")

        # Screen top boundary check
        top_margin = 10
        if next_wrap_y < top_margin:
            logger.warning(f"POPUP_WRAP_POS: Calculated wrap Y {next_wrap_y} too high, adjusting to {top_margin}. May cause overlap if many popups.")
            next_wrap_y = top_margin
            # Optional: could implement a horizontal shift here if vertical stack is full
            # e.g., next_wrap_x = base_x - wrapped_width - inter_popup_gap
            # and reset next_wrap_y to base_y, but this makes it more complex.

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
                try:
                    current_due_datetime = datetime.datetime.fromisoformat(task.due_date)
                except ValueError:
                    logger.error(f"Invalid due_date format for task {task_id}: {task.due_date}. Using current time as base for reschedule.")

            new_due_datetime = current_due_datetime + timedelta(minutes=minutes_to_add)
            task.due_date = new_due_datetime.isoformat()

            if database_manager.update_task(conn, task):
                logger.info(f"Task ID: {task_id} rescheduled successfully to {task.due_date}.")
            else:
                logger.error(f"Failed to update task ID: {task_id} in DB for rescheduling.")

        except Exception as e:
            logger.error(f"Error in handle_reschedule_task for task ID {task_id}: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

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

            if database_manager.update_task(conn, task):
                logger.info(f"Task ID: {task_id} marked as 'Completed' successfully.")
            else:
                logger.error(f"Failed to update task ID: {task_id} status to 'Completed' in DB.")

        except Exception as e:
            logger.error(f"Error in handle_complete_task for task ID {task_id}: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

        if not self.headless_mode: self.refresh_task_list()
        self.request_reschedule_reminders()


    def _remove_popup_from_active(self, task_id):
        if task_id in self.active_popups:
            del self.active_popups[task_id]
            logger.debug(f"Popup for task ID {task_id} removed from active list.")

    def toggle_tts_mute(self, event=None):
        if tts_manager:
            try:
                current_mute_state = tts_manager.is_muted
                new_mute_state = not current_mute_state
                tts_manager.set_mute(new_mute_state)
                logger.info(f"TTS Mute toggled via keyboard shortcut. New state: {'Muted' if new_mute_state else 'Unmuted'}")
            except Exception as e:
                logger.error(f"Error toggling TTS mute: {e}", exc_info=True)
        else:
            logger.warning("TTS manager instance (tts_manager) not found. Cannot toggle mute.")


if __name__ == '__main__':
    root = None
    app = None
    try:
        # Set logging level to DEBUG for this test phase
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
                if not app.scheduler or not app.scheduler.running:
                    logger.warning("Scheduler not running in headless mode. Reminders might not be processed.")

                end_time = time.time() + (60 * 5)
                try:
                    while time.time() < end_time:
                        app._check_reminder_queue()
                        time.sleep(0.25)
                    logger.info("HEADLESS test mode finished after 5 minutes.")
                except KeyboardInterrupt:
                    logger.info("HEADLESS test mode interrupted by user (Ctrl+C).")
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
        else:
            logger.critical(f"An unexpected Tkinter TclError occurred on startup (not a display issue): {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"A critical unexpected error occurred at app root level: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if app:
             if not app.headless_mode and app.root and app.root.winfo_exists():
                 pass
             elif app.headless_mode :
                 if hasattr(app, 'scheduler') and app.scheduler and app.scheduler.running:
                     logger.info("Ensuring scheduler shutdown in main finally block (headless).")
                     app.scheduler.shutdown()
        logger.info("Application terminated.")
