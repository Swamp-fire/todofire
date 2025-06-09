import tkinter as tk
from tkinter import ttk, messagebox, BooleanVar
import ttkbootstrap as bs
from ttkbootstrap.widgets import DateEntry
import datetime
from task_model import Task
import database_manager as db_manager


class ReminderPopup(tk.Toplevel):
    def __init__(self, master, task: Task, app_instance):
        super().__init__(master)
        self.task = task
        self.app = app_instance # Reference to the main TaskManagerApp

        self.title("Task Reminder!")
        # self.geometry("350x200") # Adjust as needed
        self.resizable(False, False)
        self.grab_set() # Make modal

        self.remaining_seconds = (self.task.duration or 0) * 60
        self.timer_id = None

        self._setup_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.remaining_seconds > 0 :
            self.update_timer()

        # Attempt to center on master or screen
        self.position_window()

    def _setup_widgets(self):
        main_frame = bs.Frame(self, padding=20)
        main_frame.pack(expand=True, fill=tk.BOTH)

        title_label = bs.Label(main_frame, text=f"Task: {self.task.title}", font=("-size 14 -weight bold"))
        title_label.pack(pady=(0, 10))

        due_date_str = "Not set"
        if self.task.due_date:
            try:
                dt_obj = datetime.datetime.fromisoformat(self.task.due_date)
                due_date_str = dt_obj.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                due_date_str = "Invalid Date"

        due_label = bs.Label(main_frame, text=f"Due: {due_date_str}")
        due_label.pack(pady=(0,5))

        duration_label = bs.Label(main_frame, text=f"Duration: {self.task.duration or 0} minutes")
        duration_label.pack(pady=(0, 10))

        self.timer_label = bs.Label(main_frame, text="Timer: --:--", font=("-size 12"))
        if self.task.duration and self.task.duration > 0:
            initial_minutes = self.task.duration
            self.timer_label.config(text=f"Timer: {initial_minutes:02d}:00")
        else:
            self.timer_label.config(text="Timer: N/A")
        self.timer_label.pack(pady=(0, 15))

        buttons_frame = bs.Frame(main_frame)
        buttons_frame.pack(pady=(10,0))

        self.complete_button = bs.Button(buttons_frame, text="Complete Task", bootstyle="success", command=self._on_complete)
        self.complete_button.pack(side=tk.LEFT, padx=5)

        self.skip_button = bs.Button(buttons_frame, text="Skip Reminder", bootstyle="warning", command=self._on_skip)
        self.skip_button.pack(side=tk.LEFT, padx=5)

        # "More" button could be used for snooze or other options later
        self.more_button = bs.Button(buttons_frame, text="Dismiss", bootstyle="secondary", command=self._on_close)
        self.more_button.pack(side=tk.LEFT, padx=5)

    def _on_complete(self):
        print(f"Popup: Task '{self.task.title}' (ID: {self.task.id}) marked complete.")
        self._process_task_action(new_status="Completed")
        self._on_close() # Centralize cleanup

    def _on_skip(self):
        print(f"Popup: Task '{self.task.title}' (ID: {self.task.id}) reminder skipped.")
        self._process_task_action() # No status change, just unset reminder
        self._on_close() # Centralize cleanup

    def _process_task_action(self, new_status: str = None):
        """Processes task actions like completing or skipping.
        Sets reminder_set to False and optionally updates status.
        """
        conn = None
        try:
            conn = db_manager.create_connection()
            if conn:
                task_to_update = db_manager.get_task(conn, self.task.id)
                if task_to_update:
                    task_to_update.reminder_set = False
                    action_taken = "Reminder unset"
                    if new_status:
                        task_to_update.status = new_status
                        action_taken += f" and status set to '{new_status}'"

                    db_manager.update_task(conn, task_to_update)
                    print(f"Task '{task_to_update.title}' (ID: {task_to_update.id}): {action_taken}.")

                    if self.app: # Refresh the main app's task list
                        self.app.refresh_task_list()
                else:
                    print(f"Could not fetch task ID {self.task.id} to process action.")
            else:
                print("DB connection failed, cannot process task action.")
        except Exception as e:
            print(f"Error processing action for task {self.task.id}: {e}")
        finally:
            if conn:
                conn.close()

    def _on_close(self):
        print(f"Popup: Closing for task '{self.task.title}' (ID: {self.task.id}).")
        if self.timer_id:
            self.after_cancel(self.timer_id)
            self.timer_id = None
            print("Timer cancelled.")

        # Remove from active popups in the main app
        if self.app and hasattr(self.app, '_active_popups') and self.task.id in self.app._active_popups:
            del self.app._active_popups[self.task.id]
            print(f"Popup for task {self.task.id} removed from active list.")

        self.destroy()

    def update_timer(self):
        if not self.winfo_exists(): # Stop if window is destroyed
            if self.timer_id:
                self.after_cancel(self.timer_id)
                self.timer_id = None
            return

        if self.remaining_seconds <= 0:
            self.timer_label.config(text="Time's up!")
            if self.timer_id:
                self.after_cancel(self.timer_id)
                self.timer_id = None
            # Potentially auto-skip or change behavior when time is up
            return

        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        self.timer_label.config(text=f"Timer: {minutes:02d}:{seconds:02d}")

        self.remaining_seconds -= 1
        self.timer_id = self.after(1000, self.update_timer)

    def position_window(self):
        self.update_idletasks() # Ensure window dimensions are calculated
        master_x = self.master.winfo_x()
        master_y = self.master.winfo_y()
        master_width = self.master.winfo_width()
        master_height = self.master.winfo_height()

        popup_width = self.winfo_width()
        popup_height = self.winfo_height()

        x = master_x + (master_width // 2) - (popup_width // 2)
        y = master_y + (master_height // 2) - (popup_height // 2)

        # Ensure it's not off-screen (basic check)
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        if x + popup_width > screen_width: x = screen_width - popup_width
        if y + popup_height > screen_height: y = screen_height - popup_height
        if x < 0: x = 0
        if y < 0: y = 0

        self.geometry(f"+{x}+{y}")


class TaskManagerApp:
    def __init__(self, root_window):
        self.root = root_window
        # Theme is typically set when bs.Window is created, or via root.style if needed later.
        # If root_window is already a bs.Window, it's already themed.
        self.root.title("Task Manager")
        self.root.geometry("700x800")

        self.currently_editing_task_id = None
        self.input_widgets = {}  # To store title_entry, desc_text, etc.
        self.task_tree = None    # To store the Treeview
        self.save_button = None  # To store the main save/update button
        self._active_popups = {} # To track active reminder popups by task ID

        self._setup_ui()
        self.refresh_task_list() # Initial data load
        self.schedule_due_task_check()

    def _setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)  # Form section
        self.root.rowconfigure(1, weight=1)  # Treeview section

        # --- Form Frame ---
        form_frame = bs.Frame(self.root, padding=(20, 10))
        form_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        form_frame.columnconfigure(1, weight=1)

        # Title
        title_label = bs.Label(master=form_frame, text="Title: *")
        title_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['title'] = ttk.Entry(master=form_frame, width=50)
        self.input_widgets['title'].grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Description
        desc_label = bs.Label(master=form_frame, text="Description:")
        desc_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")
        self.input_widgets['description'] = tk.Text(master=form_frame, height=4, width=38)
        self.input_widgets['description'].grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Duration
        duration_label = bs.Label(master=form_frame, text="Duration (min):")
        duration_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['duration'] = ttk.Entry(master=form_frame, width=50)
        self.input_widgets['duration'].grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        # Repetition
        rep_label = bs.Label(master=form_frame, text="Repetition:")
        rep_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['repetition'] = ttk.Combobox(master=form_frame,
                                                        values=['None', 'Daily', 'Weekly', 'Monthly', 'Yearly'],
                                                        width=47, state="readonly")
        self.input_widgets['repetition'].set('None')
        self.input_widgets['repetition'].grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        # Priority
        priority_label = bs.Label(master=form_frame, text="Priority:")
        priority_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['priority'] = ttk.Combobox(master=form_frame,
                                                      values=['Low', 'Medium', 'High'],
                                                      width=47, state="readonly")
        self.input_widgets['priority'].set('Medium')
        self.input_widgets['priority'].grid(row=4, column=1, padx=5, pady=5, sticky="ew")

        # Category
        category_label = bs.Label(master=form_frame, text="Category:")
        category_label.grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['category'] = ttk.Entry(master=form_frame, width=50)
        self.input_widgets['category'].grid(row=5, column=1, padx=5, pady=5, sticky="ew")

        # Due Date
        due_date_label = bs.Label(master=form_frame, text="Due Date:")
        due_date_label.grid(row=6, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['due_date'] = DateEntry(master=form_frame, width=47, dateformat="%Y-%m-%d")
        self.input_widgets['due_date'].grid(row=6, column=1, padx=5, pady=5, sticky="ew")

        # Due Time
        due_time_label = bs.Label(master=form_frame, text="Due Time (HH:MM):")
        due_time_label.grid(row=7, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['due_time'] = ttk.Entry(master=form_frame, width=50)
        self.input_widgets['due_time'].grid(row=7, column=1, padx=5, pady=5, sticky="ew")

        # Set Reminder
        # reminder_label = bs.Label(master=form_frame, text="Reminder:") # Optional Label
        # reminder_label.grid(row=8, column=0, padx=5, pady=5, sticky="w")
        self.input_widgets['reminder_set_var'] = BooleanVar()
        self.input_widgets['reminder_set'] = ttk.Checkbutton(master=form_frame, text="Set Reminder",
                                                             variable=self.input_widgets['reminder_set_var'])
        self.input_widgets['reminder_set'].grid(row=8, column=1, padx=5, pady=5, sticky="w")


        # --- Form Action Buttons ---
        button_frame = bs.Frame(form_frame)
        button_frame.grid(row=9, column=0, columnspan=2, pady=10) # Adjusted row
        self.save_button = bs.Button(master=button_frame, text="Save Task",
                                     command=self.save_task_action, bootstyle="success")
        self.save_button.pack(side=tk.LEFT, padx=(0, 5))
        clear_button = bs.Button(master=button_frame, text="Clear Form",
                                 command=self.clear_form_fields_and_reset_state, bootstyle="warning")
        clear_button.pack(side=tk.LEFT)

        # --- Treeview for Task List ---
        tree_container_frame = bs.Frame(self.root, padding=(0, 10, 0, 0))
        tree_container_frame.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))
        tree_container_frame.columnconfigure(0, weight=1)
        tree_container_frame.rowconfigure(2, weight=1) # Tree_frame itself will be in row 2

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

        tree_frame = ttk.Frame(tree_container_frame)
        tree_frame.grid(row=2, column=0, sticky='nsew', padx=5, pady=0)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = ("id", "title", "priority", "due_date", "status", "creation_date", "category")
        self.task_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.task_tree.heading("id", text="ID", anchor='w')
        self.task_tree.column("id", width=30, stretch=False) # Adjusted
        self.task_tree.heading("title", text="Title", anchor='w')
        self.task_tree.column("title", width=150, stretch=True) # Adjusted
        self.task_tree.heading("priority", text="Priority", anchor='w')
        self.task_tree.column("priority", width=60, stretch=False) # Adjusted
        self.task_tree.heading("due_date", text="Due Date", anchor='w')
        self.task_tree.column("due_date", width=120, stretch=False) # Adjusted
        self.task_tree.heading("status", text="Status", anchor='w')
        self.task_tree.column("status", width=70, stretch=False) # New
        self.task_tree.heading("creation_date", text="Created On", anchor='w')
        self.task_tree.column("creation_date", width=120, stretch=False) # Adjusted
        self.task_tree.heading("category", text="Category", anchor='w')
        self.task_tree.column("category", width=80, stretch=False) # Adjusted

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky='ns')
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.task_tree.xview)
        self.task_tree.configure(xscrollcommand=hsb.set)
        hsb.grid(row=1, column=0, sticky='ew')
        self.task_tree.grid(row=0, column=0, sticky='nsew')

    def clear_form_fields_and_reset_state(self):
        self.input_widgets['title'].delete(0, tk.END)
        self.input_widgets['description'].delete("1.0", tk.END)
        self.input_widgets['duration'].delete(0, tk.END)
        self.input_widgets['repetition'].set('None')
        self.input_widgets['priority'].set('Medium')
        self.input_widgets['category'].delete(0, tk.END)
        # Clear new fields
        if 'due_date' in self.input_widgets and self.input_widgets['due_date'].winfo_exists():
            self.input_widgets['due_date'].entry.delete(0, tk.END) # Clears the entry
            # self.input_widgets['due_date'].button.invoke() # This would set it to today, then clear again if needed
            # self.input_widgets['due_date']._set_date(None) # This is internal, might not be stable.
            # For DateEntry, clearing might mean setting to no specific date or today.
            # If DateEntry requires a date, set to "" or let it default.
            # For now, just clearing the text entry part.
        if 'due_time' in self.input_widgets and self.input_widgets['due_time'].winfo_exists():
            self.input_widgets['due_time'].delete(0, tk.END)
        if 'reminder_set_var' in self.input_widgets: # Check if BooleanVar exists
             self.input_widgets['reminder_set_var'].set(False)

        self.currently_editing_task_id = None
        if self.save_button:
            self.save_button.config(text="Save Task")
        print("Form fields cleared and state reset.")

    def load_selected_task_for_edit(self):
        selected_item_iid = self.task_tree.focus()
        if not selected_item_iid:
            try:
                messagebox.showwarning("No Selection", "Please select a task from the list to edit.", parent=self.root)
            except tk.TclError: print("Warning: Please select a task to edit (messagebox not available).")
            return
        try:
            task_id = int(selected_item_iid)
        except ValueError:
            try:
                messagebox.showerror("Error", "Invalid task ID selected.", parent=self.root)
            except tk.TclError: print("Error: Invalid task ID selected (messagebox not available).")
            return

        conn = None
        try:
            conn = db_manager.create_connection()
            if not conn:
                try:
                    messagebox.showerror("Database Error", "Could not connect to the database.", parent=self.root)
                except tk.TclError: print("DB Error: Could not connect (messagebox not available).")
                return
            task_to_edit = db_manager.get_task(conn, task_id)
            if not task_to_edit:
                try:
                    messagebox.showerror("Error", f"Could not retrieve task with ID: {task_id}", parent=self.root)
                except tk.TclError: print(f"Error: Could not retrieve task ID {task_id} (messagebox not available).")
                return

            self.input_widgets['title'].delete(0, tk.END)
            self.input_widgets['title'].insert(0, task_to_edit.title)
            self.input_widgets['description'].delete("1.0", tk.END)
            self.input_widgets['description'].insert('1.0', task_to_edit.description)
            self.input_widgets['duration'].delete(0, tk.END)
            self.input_widgets['duration'].insert(0, str(task_to_edit.duration))
            self.input_widgets['category'].delete(0, tk.END)
            self.input_widgets['category'].insert(0, task_to_edit.category)
            self.input_widgets['repetition'].set(task_to_edit.repetition if task_to_edit.repetition else 'None')
            priority_map_model_to_display = {1: "Low", 2: "Medium", 3: "High"}
            self.input_widgets['priority'].set(priority_map_model_to_display.get(task_to_edit.priority, "Medium"))

            # Populate due_date, due_time, and reminder_set
            self.input_widgets['due_date'].entry.delete(0, tk.END)
            self.input_widgets['due_time'].delete(0, tk.END)
            if task_to_edit.due_date:
                try:
                    dt_obj = datetime.datetime.fromisoformat(task_to_edit.due_date)
                    self.input_widgets['due_date'].entry.insert(0, dt_obj.strftime("%Y-%m-%d"))
                    self.input_widgets['due_time'].insert(0, dt_obj.strftime("%H:%M"))
                except ValueError:
                    print(f"Error parsing due_date ISO string: {task_to_edit.due_date}")
                    # Leave fields blank if parsing fails

            self.input_widgets['reminder_set_var'].set(task_to_edit.reminder_set)

            self.currently_editing_task_id = task_to_edit.id
            if self.save_button:
                self.save_button.config(text="Update Task")
            print(f"Editing task ID: {self.currently_editing_task_id}")
        except Exception as e:
            error_msg = f"Failed to load task for editing: {e}"
            try:
                messagebox.showerror("Error", error_msg, parent=self.root)
            except tk.TclError: print(f"Error: {error_msg} (messagebox not available).")
            print(f"Error in load_selected_task_for_edit: {e}")
        finally:
            if conn: conn.close()

    def save_task_action(self):
        title_value = self.input_widgets['title'].get().strip()
        if not title_value:
            try:
                messagebox.showerror("Validation Error", "Title field cannot be empty.", parent=self.root)
            except tk.TclError: print("Validation Error: Title is empty (messagebox not available).")
            return

        description = self.input_widgets['description'].get("1.0", tk.END).strip()
        duration_str = self.input_widgets['duration'].get().strip()
        repetition = self.input_widgets['repetition'].get()
        priority_str = self.input_widgets['priority'].get()
        category = self.input_widgets['category'].get().strip()
        try:
            duration = int(duration_str) if duration_str else 0
        except ValueError:
            try:
                messagebox.showerror("Validation Error", "Duration must be a valid number.", parent=self.root)
            except tk.TclError: print("Validation Error: Duration not a number (messagebox not available).")
            return
        priority_display_to_model_map = {"Low": 1, "Medium": 2, "High": 3}
        priority = priority_display_to_model_map.get(priority_str, 2)

        # Get new field values
        due_date_str = self.input_widgets['due_date'].entry.get()
        due_time_str = self.input_widgets['due_time'].get().strip()
        reminder_set_val = self.input_widgets['reminder_set_var'].get()

        task_due_date_iso = None
        if due_date_str and due_time_str:
            try:
                # Validate time format explicitly
                datetime.datetime.strptime(due_time_str, "%H:%M")
                # DateEntry's date_format is %Y-%m-%d, so due_date_str should be in this format
                # If DateEntry is empty, get() returns an empty string.
                task_due_date_iso = datetime.datetime.fromisoformat(f"{due_date_str}T{due_time_str}:00").isoformat()
            except ValueError as ve:
                try:
                    messagebox.showerror("Validation Error", f"Invalid Due Date or Time format. Please use YYYY-MM-DD for date and HH:MM for time. Error: {ve}", parent=self.root)
                except tk.TclError: print(f"Validation Error: Invalid due date/time: {ve} (messagebox not available).")
                return
        elif due_date_str and not due_time_str: # Date provided but no time
             try: # Default time to 00:00:00 if only date is given
                task_due_date_iso = datetime.datetime.fromisoformat(f"{due_date_str}T00:00:00").isoformat()
             except ValueError as ve:
                try:
                    messagebox.showerror("Validation Error", f"Invalid Due Date format. Please use YYYY-MM-DD. Error: {ve}", parent=self.root)
                except tk.TclError: print(f"Validation Error: Invalid due date: {ve} (messagebox not available).")
                return
        elif not due_date_str and due_time_str: # Time provided but no date
            try:
                messagebox.showerror("Validation Error", "Please provide a Due Date if specifying a Due Time.", parent=self.root)
            except tk.TclError: print("Validation Error: Time provided without date (messagebox not available).")
            return


        conn = None
        try:
            conn = db_manager.create_connection()
            if not conn:
                try:
                    messagebox.showerror("Database Error", "Could not connect to the database.", parent=self.root)
                except tk.TclError: print("DB Error: Could not connect (messagebox not available).")
                return
            db_manager.create_table(conn)

            if self.currently_editing_task_id is not None:
                print(f"Attempting to update task ID: {self.currently_editing_task_id}")
                original_task_for_date = db_manager.get_task(conn, self.currently_editing_task_id)
                updated_creation_date = original_task_for_date.creation_date if original_task_for_date else datetime.datetime.now().isoformat()
                task_data = Task(id=self.currently_editing_task_id, title=title_value, description=description,
                                 duration=duration, creation_date=updated_creation_date,
                                 repetition=repetition, priority=priority, category=category,
                                 due_date=task_due_date_iso, reminder_set=reminder_set_val)
                success = db_manager.update_task(conn, task_data)
                if success:
                    try:
                        messagebox.showinfo("Success", "Task updated successfully!", parent=self.root)
                    except tk.TclError: print("Success: Task updated (messagebox not available).")
                    self.clear_form_fields_and_reset_state()
                    self.refresh_task_list()
                else:
                    try:
                        messagebox.showerror("Error", "Failed to update task.", parent=self.root)
                    except tk.TclError: print("Error: Failed to update task (messagebox not available).")
            else:
                print("Attempting to add new task.")
                creation_date = datetime.datetime.now().isoformat()
                new_task = Task(id=0, title=title_value, description=description, duration=duration,
                                creation_date=creation_date, repetition=repetition, priority=priority, category=category,
                                due_date=task_due_date_iso, reminder_set=reminder_set_val)
                task_id = db_manager.add_task(conn, new_task)
                if task_id:
                    try:
                        messagebox.showinfo("Success", f"Task saved successfully with ID: {task_id}!", parent=self.root)
                    except tk.TclError: print(f"Success: Task saved ID {task_id} (messagebox not available).")
                    self.clear_form_fields_and_reset_state()
                    self.refresh_task_list()
                else:
                    try:
                        messagebox.showerror("Error", "Failed to save task to database.", parent=self.root)
                    except tk.TclError: print("Error: Failed to save task (messagebox not available).")
        except tk.TclError as e_tk:
            print(f"A TclError occurred: {e_tk}. (Likely messagebox in headless environment)")
        except Exception as e:
            error_message = f"An unexpected error occurred in save_task_action: {e}"
            print(error_message)
            try:
                messagebox.showerror("Error", error_message, parent=self.root)
            except tk.TclError: pass
        finally:
            if conn:
                conn.close()
                print("Database connection closed (save_task_action).")

    def delete_selected_task(self):
        selected_item_iid = self.task_tree.focus()
        if not selected_item_iid:
            try:
                messagebox.showwarning("No Selection", "Please select a task from the list to delete.", parent=self.root)
            except tk.TclError: print("Warning: No task selected for deletion (messagebox not available).")
            return
        try:
            task_id = int(selected_item_iid)
        except ValueError:
            try:
                messagebox.showerror("Error", "Invalid task ID in selection.", parent=self.root)
            except tk.TclError: print("Error: Invalid task ID in selection (messagebox not available).")
            return
        try:
            confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete task ID: {task_id}?", parent=self.root)
            if not confirm: return
        except tk.TclError:
            print(f"Confirmation for deleting task ID {task_id} skipped (messagebox not available). No deletion performed.")
            return

        conn = None
        try:
            conn = db_manager.create_connection()
            if not conn:
                try:
                    messagebox.showerror("Database Error", "Could not connect to the database.", parent=self.root)
                except tk.TclError: print("DB Error: Could not connect for deletion (messagebox not available).")
                return
            success = db_manager.delete_task(conn, task_id)
            if success:
                try:
                    messagebox.showinfo("Success", f"Task ID: {task_id} deleted successfully!", parent=self.root)
                except tk.TclError: print(f"Success: Task {task_id} deleted (messagebox not available).")
                self.refresh_task_list()
                if self.currently_editing_task_id == task_id:
                    self.clear_form_fields_and_reset_state()
            else:
                try:
                    messagebox.showerror("Error", f"Failed to delete task ID: {task_id}.", parent=self.root)
                except tk.TclError: print(f"Error: Failed to delete task {task_id} (messagebox not available).")
        except Exception as e:
            error_msg = f"Failed to delete task: {e}"
            try:
                messagebox.showerror("Error", error_msg, parent=self.root)
            except tk.TclError: print(f"Error: {error_msg} (messagebox not available).")
            print(f"Error in delete_selected_task: {e}")
        finally:
            if conn: conn.close()

    def refresh_task_list(self):
        if not self.task_tree:
            print("Error: task_tree not initialized. Cannot refresh.")
            return
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        conn = None
        try:
            conn = db_manager.create_connection()
            if conn is None:
                print("Database Error: Could not connect to refresh tasks.")
                try:
                    messagebox.showerror("Database Error", "Could not connect to the database to refresh tasks.", parent=self.root)
                except tk.TclError: pass
                return
            db_manager.create_table(conn)
            tasks = db_manager.get_all_tasks(conn)
            priority_map_display = {1: "Low", 2: "Medium", 3: "High"}
            for task in tasks:
                priority_display_val = priority_map_display.get(task.priority, str(task.priority))

                due_date_display = "Not set"
                if task.due_date:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(task.due_date)
                        due_date_display = dt_obj.strftime("%Y-%m-%d %H:%M")
                    except ValueError:
                        due_date_display = "Invalid Date"

                # New order: ("id", "title", "priority", "due_date", "status", "creation_date", "category")
                values_to_insert = (task.id, task.title, priority_display_val, due_date_display, task.status, task.creation_date, task.category)
                self.task_tree.insert("", tk.END, iid=str(task.id), values=values_to_insert)
            print(f"Task list refreshed. {len(tasks)} tasks loaded.")
        except Exception as e:
            error_message = f"Error refreshing task list: {e}"
            print(error_message)
            try:
                messagebox.showerror("Error", error_message, parent=self.root)
            except tk.TclError: pass
        finally:
            if conn:
                conn.close()
                print("Database connection closed after refreshing task list.")

    def schedule_due_task_check(self):
        """Schedules the next check for due tasks."""
        # print("Scheduling next due task check in 60 seconds.")
        self.root.after(60000, self.check_for_due_tasks) # 60000 ms = 1 minute

    def check_for_due_tasks(self):
        """Checks for tasks that are due and have reminders set."""
        print(f"{datetime.datetime.now()}: Checking for due tasks...")
        conn = None
        try:
            now = datetime.datetime.now()
            conn = db_manager.create_connection()
            if conn is None:
                print("DB Error: Could not connect for due task check.")
                # Potentially show a non-blocking error to the user if this persists
                return # Reschedule will happen in finally

            tasks = db_manager.get_all_tasks(conn)
            for task in tasks:
                if task.reminder_set and task.due_date:
                    try:
                        due_datetime = datetime.datetime.fromisoformat(task.due_date)
                        if due_datetime <= now:
                            popup_was_shown = self.show_reminder_popup(task)
                            if popup_was_shown:
                                # Fetch a fresh copy of the task to avoid potential stale data issues,
                                # though less critical in a single-threaded GUI without other concurrent modifications.
                                task_to_update = db_manager.get_task(conn, task.id)
                                if task_to_update:
                                    task_to_update.reminder_set = False
                                    db_manager.update_task(conn, task_to_update)
                                    print(f"Reminder for task '{task_to_update.title}' (ID: {task_to_update.id}) has been shown and its reminder_set flag is now False.")
                                    # Refreshing the list is good if reminder_set status was visible,
                                    # or if other actions in popup (like status change) require it.
                                    # The popup's own _process_task_action already calls refresh_task_list.
                                    # So, direct refresh here might be redundant if popup handles its own actions.
                                    # However, if a popup is just shown (not actioned) and we want to immediately reflect
                                    # the reminder_set=False change (if it were visible), this would be the place.
                                    # For now, the main visual change (status) is handled by popup, so this refresh is
                                    # mostly for the internal reminder_set flag if we were to display it.
                                    # self.refresh_task_list() # Consider if needed on top of popup's own refresh.
                                else:
                                    print(f"Error: Could not fetch task {task.id} to unset its reminder flag after showing popup.")
                    except ValueError as ve:
                        print(f"  Error parsing due_date for task ID {task.id} ('{task.due_date}'): {ve}")
                    except Exception as e_inner:
                        print(f"  An unexpected error occurred processing task ID {task.id}: {e_inner}")
            # print("Due task check complete.")

        except Exception as e:
            print(f"An error occurred during check_for_due_tasks: {e}")
            # Log to a file or more robust logging system in a real app
        finally:
            if conn:
                conn.close()
                # print("Database connection closed (check_for_due_tasks).")
            # ALWAYS reschedule the next check, even if an error occurred.
            self.schedule_due_task_check()

    def show_reminder_popup(self, task: Task) -> bool:
        """Creates and shows a ReminderPopup for the given task.
        Returns True if a popup was shown/activated, False otherwise.
        """
        if task.id in self._active_popups:
            existing_popup = self._active_popups[task.id]
            if existing_popup.winfo_exists():
                print(f"Reminder popup for task ID {task.id} ('{task.title}') already open. Bringing to front.")
                existing_popup.lift()
                existing_popup.focus_force()
                return True # Popup was already active and focused
            else:
                # Stale entry, remove it
                print(f"Stale popup found for task ID {task.id}. Removing from active list.")
                del self._active_popups[task.id]

        print(f"Showing new reminder popup for task: {task.title} (ID: {task.id})")
        popup = ReminderPopup(self.root, task, self)
        self._active_popups[task.id] = popup
        return True # New popup created


if __name__ == '__main__':
    try:
        root = bs.Window(themename="litera")
        app = TaskManagerApp(root)
        root.mainloop()
    except tk.TclError as e:
        print(f"Tkinter TclError: {e}")
        if "display name" in str(e).lower() or "couldn't connect to display" in str(e).lower():
            print("Application requires a graphical display environment to run.")
            print("If running in a headless environment, this error is expected.")
        else:
            pass
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
