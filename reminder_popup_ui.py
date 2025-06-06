import tkinter as tk
from tkinter import ttk
import ttkbootstrap as bs
from tts_manager import tts_manager
import logging

logger = logging.getLogger(__name__)

class ReminderPopupUI(bs.Toplevel):
    def __init__(self, parent, task, app_callbacks):
        super().__init__(parent)
        self.task = task
        self.app_callbacks = app_callbacks

        self.title("Reminder!")
        self.geometry("400x300")
        self.wm_attributes("-topmost", 1)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.skip_reminder)

        self.remaining_work_seconds = 0
        if self.task and self.task.duration and self.task.duration > 0:
            self.remaining_work_seconds = self.task.duration * 60

        self.style = ttk.Style()
        self.after_id = None
        self._setup_ui()

        if self.remaining_work_seconds > 0:
            self._update_countdown()

        logger.info(f"ReminderPopupUI created for task ID: {self.task.id if self.task else 'N/A'}, Title: {self.task.title if self.task else 'N/A'}")
        try:
            if self.task and self.task.title:
                speech_text = f"Reminder for task: {self.task.title}"
                logger.info(f"Popup: Requesting TTS for: '{speech_text}'")
                tts_manager.speak(speech_text)
            elif self.task:
                logger.warning(f"Popup: Task ID {self.task.id if self.task else 'N/A'} has no title. Speaking generic reminder.")
                tts_manager.speak("Reminder for task with no title.")
            else:
                logger.error("Popup: Task details are unavailable for TTS. Speaking generic error.")
                tts_manager.speak("Reminder triggered, but task details are unavailable.", error_context=True)
        except Exception as e:
            logger.error(f"CRITICAL: Unexpected error initiating TTS from ReminderPopupUI: {e}", exc_info=True)

    def _setup_ui(self):
        main_frame = bs.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = bs.Label(main_frame, text=self.task.title if self.task else "No Title",
                               font=("Helvetica", 14, "bold"), anchor="center", padding=(0,0,0,10))
        title_label.pack(fill=tk.X)

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
                                            font=("Helvetica", 12, "bold"), style="info.TLabel")
            self.countdown_label.pack(side=tk.LEFT)
        else:
            no_duration_label = bs.Label(duration_display_frame, text="No specific work duration.", style="secondary.TLabel")
            no_duration_label.pack(side=tk.LEFT)

        button_frame = bs.Frame(main_frame)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(5,0))

        self.skip_button = bs.Button(button_frame, text="Skip", command=self.skip_reminder, bootstyle="secondary", width=10)
        self.skip_button.pack(side=tk.RIGHT, padx=(5,0))

        self.complete_button = bs.Button(button_frame, text="Complete", command=self.complete_task, bootstyle="success", width=10)
        self.complete_button.pack(side=tk.RIGHT, padx=(5,0))

        self.reschedule_button = bs.Button(button_frame, text="Reschedule", command=self.reschedule_task, bootstyle="warning", width=10)
        self.reschedule_button.pack(side=tk.RIGHT, padx=(0,0))


    def _update_countdown(self):
        if self.remaining_work_seconds > 0:
            hours = self.remaining_work_seconds // 3600
            minutes = (self.remaining_work_seconds % 3600) // 60
            seconds = self.remaining_work_seconds % 60

            if hours > 0:
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                time_str = f"{minutes:02d}:{seconds:02d}"

            if hasattr(self, 'countdown_label') and self.countdown_label.winfo_exists():
                self.countdown_label.config(text=time_str)

            self.remaining_work_seconds -= 1
            self.after_id = self.after(1000, self._update_countdown)
        elif hasattr(self, 'countdown_label') and self.countdown_label.winfo_exists():
            self.countdown_label.config(text="Time's up!")
            logger.info(f"Work duration timer for task ID: {self.task.id if self.task else 'N/A'} has finished. Auto-triggering completion.")
            self.complete_task()

    def reschedule_task(self):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

        task_id_info = self.task.id if self.task else "N/A"
        logger.info(f"Popup: Reschedule requested for task ID: {task_id_info}")
        if self.app_callbacks and 'reschedule' in self.app_callbacks:
            try:
                self.app_callbacks['reschedule'](self.task.id if self.task else None, 15)
                logger.debug(f"Popup: Reschedule callback called for task ID: {task_id_info}")
            except Exception as e:
                logger.error(f"Popup: Error calling reschedule callback for task ID {task_id_info}: {e}", exc_info=True)
        else:
            logger.warning(f"Popup: 'reschedule' callback not found or app_callbacks not set for task ID: {task_id_info}")

        self._cleanup_and_destroy()

    def complete_task(self):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

        task_id_info = self.task.id if self.task else "N/A"
        logger.info(f"Popup: Complete requested for task ID: {task_id_info}")
        if self.app_callbacks and 'complete' in self.app_callbacks:
            try:
                self.app_callbacks['complete'](self.task.id if self.task else None)
                logger.debug(f"Popup: Complete callback called for task ID: {task_id_info}")
            except Exception as e:
                logger.error(f"Popup: Error calling complete callback for task ID {task_id_info}: {e}", exc_info=True)
        else:
            logger.warning(f"Popup: 'complete' callback not found or app_callbacks not set for task ID: {task_id_info}")

        self._cleanup_and_destroy()

    def skip_reminder(self):
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        task_id_info = self.task.id if self.task else "N/A"
        logger.info(f"Popup: Skip requested for task ID: {task_id_info}")
        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        logger.debug(f"Popup: Cleaning up for task ID {self.task.id if self.task else 'N/A'}")
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

        if self.app_callbacks and 'remove_from_active' in self.app_callbacks:
            try:
                logger.debug(f"Popup: Calling remove_from_active callback for task ID {self.task.id if self.task else 'N/A'}")
                self.app_callbacks['remove_from_active'](self.task.id if self.task else None)
            except Exception as e:
                logger.error(f"Popup: Error calling remove_from_active callback: {e}", exc_info=True)
        self.destroy()

# Example usage
if __name__ == '__main__':
    # ... (main test block remains the same)
    class DummyTask:
        def __init__(self, id, title, description, duration):
            self.id = id
            self.title = title
            self.description = description
            self.duration = duration

    class DummyApp:
        def __init__(self):
            # If running this file directly, ensure basicConfig is called for logger to output
            if not logging.getLogger().hasHandlers():
                 logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

            self.root = bs.Window(themename="litera")
            self.root.title("Main App Window")

            self.sample_task = DummyTask(1, "Test Task Popup", "This is a description for the test task.", 0) # Duration 0 for no countdown

            self.callbacks = {
                'reschedule': lambda task_id, mins: logger.info(f"MAIN APP: Reschedule task {task_id} by {mins} mins."),
                'complete': lambda task_id: logger.info(f"MAIN APP: Complete task {task_id}."),
                'remove_from_active': lambda task_id: logger.info(f"MAIN APP: Popup for task {task_id} closed.")
            }

            show_button = bs.Button(self.root, text="Show Reminder Popup (No Countdown)", command=self.show_dummy_popup)
            show_button.pack(pady=10)

            self.sample_task_with_countdown = DummyTask(2, "Test Countdown Popup", "Description for countdown.", 1) # 1 min duration
            show_button_countdown = bs.Button(self.root, text="Show Reminder Popup (1 Min Countdown)", command=self.show_dummy_popup_countdown)
            show_button_countdown.pack(pady=10)

            self.root.mainloop()

        def show_dummy_popup(self):
            popup = ReminderPopupUI(self.root, self.sample_task, self.callbacks)

        def show_dummy_popup_countdown(self):
            popup = ReminderPopupUI(self.root, self.sample_task_with_countdown, self.callbacks)

    # DummyApp()
