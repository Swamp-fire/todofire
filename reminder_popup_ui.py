import tkinter as tk
from tkinter import ttk # ttk will be needed for styling if not using bs buttons directly
import ttkbootstrap as bs # ttkbootstrap.Toplevel is a good base

class ReminderPopupUI(bs.Toplevel):
    def __init__(self, parent, task, app_callbacks):
        super().__init__(parent)
        self.task = task
        self.app_callbacks = app_callbacks # For 'reschedule', 'complete'

        self.title("Reminder!")
        self.geometry("350x250") # Initial size, can be adjusted
        self.wm_attributes("-topmost", 1) # Make it stay on top
        self.resizable(False, False)
        self.geometry("400x300") # Adjusted geometry

        # Handle window close button (X) like a "skip"
        self.protocol("WM_DELETE_WINDOW", self.skip_reminder)

        # Placeholder for countdown logic variables
        self.remaining_work_seconds = 0
        if self.task and self.task.duration and self.task.duration > 0:
            self.remaining_work_seconds = self.task.duration * 60

        # ttk style object for custom configurations if needed
        self.style = ttk.Style()

        self.after_id = None # Initialize for managing the 'after' job

        self._setup_ui() # Create UI elements first

        # Start countdown if applicable, after UI is set up
        if self.remaining_work_seconds > 0:
            self._update_countdown()


    def _setup_ui(self):
        main_frame = bs.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Task Title
        title_label = bs.Label(main_frame, text=self.task.title if self.task else "No Title",
                               font=("Helvetica", 14, "bold"), anchor="center", padding=(0,0,0,10))
        title_label.pack(fill=tk.X)

        # Task Description (using a Text widget for potential scrollability and fixed height)
        desc_frame = bs.Frame(main_frame)
        desc_frame.pack(fill=tk.X, pady=(0,10))

        description_text_widget = tk.Text(desc_frame, wrap=tk.WORD, height=4, relief=tk.FLAT,
                                   borderwidth=0, highlightthickness=0, font=("Helvetica", 10))
        desc_text_content = self.task.description if self.task and self.task.description else "No description."
        description_text_widget.insert(tk.END, desc_text_content)

        try:
            bg_color = self.cget('background')
            description_text_widget.config(state=tk.DISABLED, bg=bg_color)
        except tk.TclError:
            description_text_widget.config(state=tk.DISABLED, bg="SystemButtonFace")

        description_text_widget.pack(fill=tk.X, expand=False)

        # Work Duration / Countdown Display Area
        duration_display_frame = bs.Frame(main_frame)
        duration_display_frame.pack(fill=tk.X, pady=(0, 15))

        if self.task and self.task.duration and self.task.duration > 0:
            static_duration_text_label = bs.Label(duration_display_frame, text="Work Session:", font=("Helvetica", 10))
            static_duration_text_label.pack(side=tk.LEFT, padx=(0,5))

            hours = self.remaining_work_seconds // 3600
            minutes = (self.remaining_work_seconds % 3600) // 60
            seconds = self.remaining_work_seconds % 60

            if hours > 0:
                initial_duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                initial_duration_str = f"{minutes:02d}:{seconds:02d}"

            self.countdown_label = bs.Label(duration_display_frame, text=initial_duration_str,
                                            font=("Helvetica", 12, "bold"), style="info.TLabel") # Using ttkbootstrap style
            self.countdown_label.pack(side=tk.LEFT)
        else:
            no_duration_label = bs.Label(duration_display_frame, text="No specific work duration.", style="secondary.TLabel")
            no_duration_label.pack(side=tk.LEFT)

        # Buttons Frame
        button_frame = bs.Frame(main_frame)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(5,0))

        self.skip_button = bs.Button(button_frame, text="Skip", command=self.skip_reminder, bootstyle="secondary", width=10) # ttkbootstrap style
        self.skip_button.pack(side=tk.RIGHT, padx=(5,0))

        self.complete_button = bs.Button(button_frame, text="Complete", command=self.complete_task, bootstyle="success", width=10)
        self.complete_button.pack(side=tk.RIGHT, padx=(5,0))

        self.reschedule_button = bs.Button(button_frame, text="Reschedule", command=self.reschedule_task, bootstyle="warning", width=10)
        self.reschedule_button.pack(side=tk.RIGHT, padx=(0,0)) # No right pad for the leftmost button in this group


    def _update_countdown(self):
        if self.remaining_work_seconds > 0:
            hours = self.remaining_work_seconds // 3600
            minutes = (self.remaining_work_seconds % 3600) // 60
            seconds = self.remaining_work_seconds % 60

            if hours > 0:
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                time_str = f"{minutes:02d}:{seconds:02d}"

            # Ensure countdown_label exists and the window hasn't been closed
            if hasattr(self, 'countdown_label') and self.countdown_label.winfo_exists():
                self.countdown_label.config(text=time_str)

            self.remaining_work_seconds -= 1
            # Schedule next update, store job ID to allow cancellation
            self.after_id = self.after(1000, self._update_countdown)
        elif hasattr(self, 'countdown_label') and self.countdown_label.winfo_exists():
            self.countdown_label.config(text="Time's up!")
            # Optionally, change style or trigger another action (e.g., sound)
            # self.countdown_label.config(bootstyle="danger") # ttkbootstrap alternative for style change
            # self.countdown_label.config(bootstyle="danger") # ttkbootstrap alternative for style change
            # self.countdown_label.configure(style="danger.TLabel") # if using specific ttkbootstrap styles

    def reschedule_task(self):
        if self.after_id: # Cancel countdown
            self.after_cancel(self.after_id)
            self.after_id = None

        task_id_info = self.task.id if self.task else "N/A" # Safe access for logging
        if self.app_callbacks and 'reschedule' in self.app_callbacks:
            try:
                # Assuming reschedule callback will handle None task.id if self.task is None (though unlikely for a popup)
                self.app_callbacks['reschedule'](self.task.id if self.task else None, 15) # Postpone by 15 minutes
                print(f"Popup: Reschedule callback called for task ID: {task_id_info}")
            except Exception as e:
                print(f"Popup: Error calling reschedule callback for task ID {task_id_info}: {e}")
        else:
            print(f"Popup: 'reschedule' callback not found or app_callbacks not set for task ID: {task_id_info}")

        self._cleanup_and_destroy()

    def complete_task(self):
        if self.after_id: # Cancel countdown
            self.after_cancel(self.after_id)
            self.after_id = None

        task_id_info = self.task.id if self.task else "N/A" # Safe access for logging
        if self.app_callbacks and 'complete' in self.app_callbacks:
            try:
                self.app_callbacks['complete'](self.task.id if self.task else None)
                print(f"Popup: Complete callback called for task ID: {task_id_info}")
            except Exception as e:
                print(f"Popup: Error calling complete callback for task ID {task_id_info}: {e}")
        else:
            print(f"Popup: 'complete' callback not found or app_callbacks not set for task ID: {task_id_info}")

        self._cleanup_and_destroy()

    def skip_reminder(self):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        task_id_info = self.task.id if self.task else "N/A" # Safe access for logging
        print(f"Popup: Skip requested for task ID: {task_id_info}")
        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        """Handles cleanup and then destroys the window."""
        if self.after_id: # Ensure countdown is cancelled if somehow still running
            self.after_cancel(self.after_id)
            self.after_id = None

        if self.app_callbacks and 'remove_from_active' in self.app_callbacks:
            try:
                self.app_callbacks['remove_from_active'](self.task.id if self.task else None)
            except Exception as e:
                # Use logging here if available, or print for now
                print(f"Popup: Error calling remove_from_active callback: {e}")
        self.destroy()

# Example usage (for testing this file directly, if needed)
if __name__ == '__main__':
    # This requires a dummy Task object and a root window.
    # This part is more for quick isolated testing if you run this file.
    class DummyTask:
        def __init__(self, id, title, description, duration):
            self.id = id
            self.title = title
            self.description = description
            self.duration = duration # minutes

    class DummyApp:
        def __init__(self):
            self.root = bs.Window(themename="litera") # Or your app's theme
            self.root.title("Main App Window")

            # Create a dummy task
            self.sample_task = DummyTask(1, "Test Task Popup", "This is a description for the test task.", 1) # 1 min duration

            # Dummy callbacks
            self.callbacks = {
                'reschedule': lambda task_id, mins: print(f"MAIN APP: Reschedule task {task_id} by {mins} mins."),
                'complete': lambda task_id: print(f"MAIN APP: Complete task {task_id}.")
            }

            # Button to show popup
            show_button = bs.Button(self.root, text="Show Reminder Popup", command=self.show_dummy_popup)
            show_button.pack(pady=20)

            self.root.mainloop()

        def show_dummy_popup(self):
            popup = ReminderPopupUI(self.root, self.sample_task, self.callbacks)
            # popup.grab_set() # Optional: makes the popup modal

    # DummyApp() # Uncomment to run the test part
