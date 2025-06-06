import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as bs
import datetime
from datetime import timedelta # Ensure timedelta is imported
import queue
from task_model import Task
import database_manager
from database_manager import check_timeslot_overlap # Added specific import
import scheduler_manager
import logging
from reminder_popup_ui import ReminderPopupUI
from tts_manager import tts_manager
import time
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(name)-25s - %(message)s')
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

        columns = ("id", "title", "status", "priority", "due_date", "category", "creation_date")
        self.task_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.task_tree.heading("id", text="ID", anchor='w')
        self.task_tree.column("id", width=30, stretch=False)
        self.task_tree.heading("title", text="Title", anchor='w')
        self.task_tree.column("title", width=150, stretch=True)
        self.task_tree.heading("status", text="Status", anchor='w')
        self.task_tree.column("status", width=80, stretch=False)
        self.task_tree.heading("priority", text="Priority", anchor='w')
        self.task_tree.column("priority", width=70, stretch=False)
        self.task_tree.heading("due_date", text="Due Date", anchor='w')
        self.task_tree.column("due_date", width=130, stretch=False)
        self.task_tree.heading("category", text="Category", anchor='w')
        self.task_tree.column("category", width=90, stretch=False)
        self.task_tree.heading("creation_date", text="Created On", anchor='w')
        self.task_tree.column("creation_date", width=130, stretch=False)

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

        title_value = self.input_widgets['title'].get().strip()
        if not title_value:
            try:
                messagebox.showerror("Validation Error", "Title field cannot be empty.", parent=self.root)
            except tk.TclError: logger.error("Validation Error: Title is empty (messagebox not available).")
            return

        description = self.input_widgets['description'].get("1.0", tk.END).strip()
        repetition = self.input_widgets['repetition'].get()
        priority_str = self.input_widgets['priority'].get()
        category = self.input_widgets['category'].get().strip()

        try:
            hours_str = self.input_widgets['duration_hours'].get()
            minutes_str = self.input_widgets['duration_minutes'].get()
            hours = int(hours_str) if hours_str else 0
            minutes = int(minutes_str) if minutes_str else 0
            if not (0 <= hours <= 99):
                messagebox.showerror("Invalid Duration", "Hours must be between 0 and 99.", parent=self.root)
                return
            if not (0 <= minutes <= 59):
                messagebox.showerror("Invalid Duration", "Minutes must be between 0 and 59.", parent=self.root)
                return
            task_duration_total_minutes = (hours * 60) + minutes
        except ValueError:
            try:
                messagebox.showerror("Invalid Duration", "Duration hours and minutes must be numbers.", parent=self.root)
            except tk.TclError: logger.error("Validation Error: Duration hrs/min not numbers (messagebox not available).")
            return
        except tk.TclError:
            logger.error("Validation Error: Duration hrs/min not numbers (messagebox not available / TclError).")
            return

        due_date_str = self.input_widgets['due_date'].entry.get()
        due_hour_str = self.input_widgets['due_hour'].get()
        due_minute_str = self.input_widgets['due_minute'].get()
        task_due_datetime_iso = None

        if due_date_str:
            if not due_hour_str or not due_minute_str:
                try:
                    messagebox.showerror("Missing Time", "If Due Date is set, Due Time (HH:MM) must also be selected.", parent=self.root)
                except tk.TclError: logger.error("Validation Error: Missing time for due date (messagebox not available).")
                return
            try:
                dt_obj = datetime.datetime.strptime(f"{due_date_str} {due_hour_str}:{due_minute_str}", "%Y-%m-%d %H:%M")
                task_due_datetime_iso = dt_obj.isoformat()
            except ValueError:
                try:
                    messagebox.showerror("Invalid Date/Time", "Due Date or Time is not valid. Please use YYYY-MM-DD format for date and select HH:MM for time.", parent=self.root)
                except tk.TclError: logger.error("Validation Error: Invalid date/time format (messagebox not available).")
                return

        # Conflict Check Logic
        if task_duration_total_minutes > 0 and task_due_datetime_iso:
            try:
                current_task_start_dt = datetime.datetime.fromisoformat(task_due_datetime_iso)
                current_task_end_dt = current_task_start_dt + datetime.timedelta(minutes=task_duration_total_minutes)
                logger.info(f"Conflict Check initiated for '{title_value}' slot: {current_task_start_dt} to {current_task_end_dt}")

                conn_check = None
                try:
                    conn_check = database_manager.create_connection()
                    if not conn_check:
                        if not self.headless_mode:
                            messagebox.showerror("DB Error", "Cannot check for task conflicts: DB connection failed.", parent=self.root)
                        else:
                            logger.error("DB Error: Cannot check for task conflicts: DB connection failed.")
                        return

                    existing_tasks = database_manager.get_all_tasks(conn_check)
                    conflict_found = False
                    for existing_task in existing_tasks:
                        if self.currently_editing_task_id and existing_task.id == self.currently_editing_task_id:
                            continue
                        if existing_task.status == 'Completed':
                            continue
                        if not existing_task.due_date or not existing_task.duration or existing_task.duration == 0:
                            continue

                        try:
                            existing_task_start_dt = datetime.datetime.fromisoformat(existing_task.due_date)
                            existing_task_end_dt = existing_task_start_dt + datetime.timedelta(minutes=existing_task.duration)
                        except ValueError:
                            logger.warning(f"Invalid date format for existing task ID {existing_task.id} ('{existing_task.due_date}'). Skipping in conflict check.")
                            continue

                        if database_manager.check_timeslot_overlap(current_task_start_dt, current_task_end_dt,
                                                               existing_task_start_dt, existing_task_end_dt):
                            logger.warning(f"Task conflict: '{title_value}' overlaps with '{existing_task.title}' (ID: {existing_task.id})")
                            if not self.headless_mode:
                                messagebox.showerror("Task Conflict",
                                                 f"Task '{title_value}' ({current_task_start_dt.strftime('%H:%M')} - {current_task_end_dt.strftime('%H:%M')}) "
                                                 f"conflicts with '{existing_task.title}' (due: {existing_task_start_dt.strftime('%Y-%m-%d %H:%M')}, "
                                                 f"duration: {existing_task.duration} min). Please choose a different time or duration.",
                                                 parent=self.root)
                            else:
                                logger.error(f"HEADLESS_ERROR: Task Conflict with {existing_task.title}")
                            conflict_found = True
                            break

                    if conflict_found:
                        return

                except Exception as e_check:
                    logger.error(f"Error during conflict check: {e_check}", exc_info=True)
                    if not self.headless_mode:
                        messagebox.showerror("Conflict Check Error", "An error occurred while checking for task conflicts. Saving aborted.", parent=self.root)
                    else:
                        logger.error("HEADLESS_ERROR: Conflict Check Error")
                    return
                finally:
                    if conn_check:
                        conn_check.close()
            except ValueError:
                 logger.error(f"Invalid due_date ('{task_due_datetime_iso}') for current task '{title_value}' during conflict check setup. Aborting save.", exc_info=True)
                 if not self.headless_mode:
                     messagebox.showerror("Invalid Date", "The due date for the current task is invalid. Cannot save.", parent=self.root)
                 else:
                     logger.error("HEADLESS_ERROR: Invalid Date for current task")
                 return


        priority_display_to_model_map = {"Low": 1, "Medium": 2, "High": 3}
        priority = priority_display_to_model_map.get(priority_str, 2)

        # conn = None # Already defined above
        try:
            # conn = database_manager.create_connection() # Connection should be established before conflict check or use the same
            if not conn or conn.total_changes == -1: # Check if conn was closed or is invalid, then reopen
                 conn = database_manager.create_connection()
                 if not conn:
                    messagebox.showerror("Database Error", "Could not connect to the database.", parent=self.root)
                    return

            database_manager.create_table(conn) # Ensure table exists

            if self.currently_editing_task_id is not None:
                logger.info(f"Attempting to update task ID: {self.currently_editing_task_id}")
                original_task_for_date = database_manager.get_task(conn, self.currently_editing_task_id)
                updated_creation_date = original_task_for_date.creation_date if original_task_for_date else datetime.datetime.now().isoformat()
                updated_last_reset_date = original_task_for_date.last_reset_date if original_task_for_date else datetime.date.today().isoformat()
                original_status = original_task_for_date.status if original_task_for_date else "Pending"

                task_data_obj = Task(id=self.currently_editing_task_id, title=title_value, description=description,
                                 duration=task_duration_total_minutes, creation_date=updated_creation_date,
                                 repetition=repetition, priority=priority, category=category,
                                 due_date=task_due_datetime_iso, status=original_status,
                                 last_reset_date=updated_last_reset_date)
                success = database_manager.update_task(conn, task_data_obj)
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
                                creation_date=creation_date, repetition=repetition, priority=priority, category=category,
                                due_date=task_due_datetime_iso)
                task_id = database_manager.add_task(conn, new_task_obj)
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
            if conn:
                conn.close()
                logger.debug("Database connection closed (save_task_action).")


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
                        display_due_date = task.due_date
                values_to_insert = (
                    task.id, task.title, task.status, priority_display_val,
                    display_due_date, task.category, task.creation_date
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
                run_time = datetime.datetime.now() + datetime.timedelta(seconds=3)
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
                        'remove_from_active': self._remove_popup_from_active
                    }
                    popup = ReminderPopupUI(self.root, task_details, app_callbacks)
                    self.active_popups[task_id] = popup
                    logger.info(f"ReminderPopupUI created and added to active_popups for task ID {task_id}.")

        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Error processing reminder queue: {e}", exc_info=True)

        if not self.headless_mode and self.root and self.root.winfo_exists():
             self.root.after(250, self._check_reminder_queue)

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

            new_due_datetime = current_due_datetime + datetime.timedelta(minutes=minutes_to_add)
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
        logger.info("Application starting...")
        root = bs.Window(themename="litera")
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
