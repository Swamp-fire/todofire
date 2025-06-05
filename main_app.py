import tkinter as tk
from tkinter import ttk, messagebox # Added messagebox
import ttkbootstrap as bs
from datetime import datetime # Added datetime

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as bs
import datetime # Corrected import for datetime
from task_model import Task # Actual import
import database_manager as db_manager # Actual import


# Renamed from placeholder_save_task and will need access to input_widgets
def save_task_action(window_ref): # Pass the window reference to access input_widgets
    """Handles task validation and saving."""
    input_widgets = window_ref.input_widgets

    title_value = input_widgets['title'].get().strip()

    if not title_value:
        try:
            messagebox.showerror("Validation Error", "Title field cannot be empty.")
        except tk.TclError:
            print("Validation Error: Title field cannot be empty (messagebox not available).")
        return

    # Retrieve other values
    description = input_widgets['description'].get("1.0", tk.END).strip()
    duration_str = input_widgets['duration'].get().strip()
    repetition = input_widgets['repetition'].get()
    priority_str = input_widgets['priority'].get()
    category = input_widgets['category'].get().strip()

    # Data Conversion & Preparation
    creation_date = datetime.datetime.now().isoformat()

    try:
        duration = int(duration_str) if duration_str else 0
    except ValueError:
        try:
            messagebox.showerror("Validation Error", "Duration must be a valid number.")
        except tk.TclError:
            print("Validation Error: Duration must be a valid number (messagebox not available).")
        return

    priority_mapping = {'Low': 1, 'Medium': 2, 'High': 3}
    priority = priority_mapping.get(priority_str, 2) # Default to Medium (2)

    # Create Task Object (id is None for new tasks, will be autoincremented)
    # The Task model's __init__ expects an id. We pass 0 or None.
    # If task_model.py's Task expects a non-None id, this might need adjustment there
    # or how add_task in db_manager handles it (usually it ignores passed ID for INSERT)
    new_task = Task(id=0, title=title_value, description=description, duration=duration,
                    creation_date=creation_date, repetition=repetition, priority=priority, category=category)

    # Database Interaction
    conn = None # Initialize conn
    try:
        conn = db_manager.create_connection() # Uses default "tasks.db"
        if conn is None:
            messagebox.showerror("Database Error", "Could not connect to the database.")
            print("Database Error: Could not connect to the database.")
            return

        # Ensure table exists (idempotent call)
        db_manager.create_table(conn)

        task_id = db_manager.add_task(conn, new_task)

        if task_id:
            messagebox.showinfo("Success", f"Task saved successfully with ID: {task_id}!")
            print(f"Task saved successfully with ID: {task_id}")
            # Clear Input Fields
            input_widgets['title'].delete(0, tk.END)
            input_widgets['description'].delete("1.0", tk.END)
            input_widgets['duration'].delete(0, tk.END)
            input_widgets['repetition'].set('None') # Reset to default
            input_widgets['priority'].set('Medium') # Reset to default
            input_widgets['category'].delete(0, tk.END)
        else:
            messagebox.showerror("Error", "Failed to save task to database.")
            print("Error: Failed to save task to database.")

    except tk.TclError: # Catch TclError if messagebox fails in headless
        print("A TclError occurred, likely trying to show a messagebox in a headless environment.")
    except Exception as e: # Catch any other unexpected errors during DB interaction
        try:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
        except tk.TclError:
            pass # Already handled above
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


def setup_main_window():
    """Sets up the main application window with task creation UI."""
    try:
        window = bs.Window(themename="litera")
        window.title("Task Manager")
        window.geometry("700x550") # Adjusted size for more fields
    except tk.TclError as e:
        print(f"Error creating Tkinter window: {e}")
        print("This might be due to running in an environment without a display server.")
        try:
            window = tk.Tk() # Basic fallback
            window.title("Task Manager (Basic Fallback)")
            window.geometry("700x550")
            print("Basic Tk window created as a fallback.")
        except tk.TclError as fallback_e:
            print(f"Failed to create basic Tk window as well: {fallback_e}")
            return None
        # If basic window is created, we might not have bs.Frame, so return early or use tk.Frame
        # For this iteration, let's assume if ttkbootstrap.Window fails, we might not proceed with bs widgets.
        # However, the problem statement implies the UI elements should be attempted.
        # The primary check for `bs` should be at the top level of the try.

    # Main frame for content organization
    main_frame = bs.Frame(window, padding=(20, 20))
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Configure grid weights for responsiveness
    main_frame.columnconfigure(1, weight=1) # Allow column 1 (inputs) to expand

    # --- Input Fields and Labels ---
    input_widgets = {} # To store references to input widgets

    # Title
    title_label = bs.Label(master=main_frame, text="Title: *")
    title_label.grid(row=0, column=0, padx=5, pady=10, sticky="w")
    input_widgets['title'] = ttk.Entry(master=main_frame, width=50)
    input_widgets['title'].grid(row=0, column=1, padx=5, pady=10, sticky="ew")

    # Description
    desc_label = bs.Label(master=main_frame, text="Description:")
    desc_label.grid(row=1, column=0, padx=5, pady=10, sticky="nw") # north-west for multi-line
    input_widgets['description'] = tk.Text(master=main_frame, height=5, width=38) # width in chars
    input_widgets['description'].grid(row=1, column=1, padx=5, pady=10, sticky="ew")

    # Duration
    duration_label = bs.Label(master=main_frame, text="Duration (min):")
    duration_label.grid(row=2, column=0, padx=5, pady=10, sticky="w")
    input_widgets['duration'] = ttk.Entry(master=main_frame, width=50)
    input_widgets['duration'].grid(row=2, column=1, padx=5, pady=10, sticky="ew")

    # Repetition
    rep_label = bs.Label(master=main_frame, text="Repetition:")
    rep_label.grid(row=3, column=0, padx=5, pady=10, sticky="w")
    input_widgets['repetition'] = ttk.Combobox(master=main_frame,
                                             values=['None', 'Daily', 'Weekly', 'Monthly', 'Yearly'],
                                             width=47)
    input_widgets['repetition'].set('None') # Default value
    input_widgets['repetition'].grid(row=3, column=1, padx=5, pady=10, sticky="ew")

    # Priority
    priority_label = bs.Label(master=main_frame, text="Priority:")
    priority_label.grid(row=4, column=0, padx=5, pady=10, sticky="w")
    input_widgets['priority'] = ttk.Combobox(master=main_frame,
                                           values=['Low', 'Medium', 'High'],
                                           width=47)
    input_widgets['priority'].set('Medium') # Default value
    input_widgets['priority'].grid(row=4, column=1, padx=5, pady=10, sticky="ew")

    # Category
    category_label = bs.Label(master=main_frame, text="Category:")
    category_label.grid(row=5, column=0, padx=5, pady=10, sticky="w")
    input_widgets['category'] = ttk.Entry(master=main_frame, width=50)
    input_widgets['category'].grid(row=5, column=1, padx=5, pady=10, sticky="ew")

    # --- Save Button ---
    # Using a sub-frame for the button to center it or group multiple buttons
    button_frame = bs.Frame(main_frame)
    button_frame.grid(row=6, column=0, columnspan=2, pady=20)

    # Update button command to call save_task_action, passing the window
    save_button = bs.Button(master=button_frame, text="Save Task", command=lambda: save_task_action(window), bootstyle="success")
    save_button.pack() # pack within the button_frame

    # Store widgets for later access if not using a class structure immediately
    window.input_widgets = input_widgets

    return window

if __name__ == '__main__':
    main_window = setup_main_window()
    if main_window:
        try:
            main_window.mainloop()
        except Exception as e:
            print(f"Error during mainloop: {e}")
            if "display name" in str(e).lower() or "no display" in str(e).lower() or "application has been destroyed" in str(e).lower():
                 print("Mainloop failed or window closed, likely due to no display or script completion in headless environment. Application would run in a GUI environment.")
            else:
                 raise
    else:
        print("Failed to create the main window. Application will not run.")
