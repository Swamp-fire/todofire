import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as bs
import datetime
from task_model import Task
import database_manager as db_manager

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

        self._setup_ui()
        self.refresh_task_list() # Initial data load

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

        # --- Form Action Buttons ---
        button_frame = bs.Frame(form_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=10)
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

        columns = ("id", "title", "priority", "creation_date", "category")
        self.task_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.task_tree.heading("id", text="ID", anchor='w')
        self.task_tree.column("id", width=40, stretch=False)
        self.task_tree.heading("title", text="Title", anchor='w')
        self.task_tree.column("title", width=200, stretch=True)
        self.task_tree.heading("priority", text="Priority", anchor='w')
        self.task_tree.column("priority", width=80, stretch=False)
        self.task_tree.heading("creation_date", text="Created On", anchor='w')
        self.task_tree.column("creation_date", width=150, stretch=False)
        self.task_tree.heading("category", text="Category", anchor='w')
        self.task_tree.column("category", width=100, stretch=False)

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
                                 repetition=repetition, priority=priority, category=category)
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
                                creation_date=creation_date, repetition=repetition, priority=priority, category=category)
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
                values_to_insert = (task.id, task.title, priority_display_val, task.creation_date, task.category)
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
