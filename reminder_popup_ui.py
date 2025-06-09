import tkinter as tk
from tkinter import ttk
import ttkbootstrap as bs
from ttkbootstrap.tooltip import ToolTip
from tts_manager import tts_manager
import logging

logger = logging.getLogger(__name__)

class ReminderPopupUI(bs.Toplevel):
    def __init__(self, parent, task, app_callbacks):
        super().__init__(parent)
        self.overrideredirect(True)
        self.task = task
        self.app_callbacks = app_callbacks
        self.after_id = None
        self.is_expanded = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0

        self.width = 380
        self.initial_height = 90  # Restored thinner value
        self.expanded_height = 215 # Restored thinner value

        self.remaining_work_seconds = 0
        if self.task and self.task.duration and self.task.duration > 0:
            self.remaining_work_seconds = self.task.duration * 60

        self.geometry(f"{self.width}x{self.initial_height}") # Use initial height

        self.wm_attributes("-topmost", 1)
        self.resizable(False, False)
        # self.protocol("WM_DELETE_WINDOW", self.skip_reminder) # Ineffective due to overrideredirect

        self.bind("<ButtonPress-1>", self._on_mouse_press)
        self.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.bind("<B1-Motion>", self._on_mouse_drag)

        self._setup_ui()

        if self.remaining_work_seconds > 0: # Call restored
            self._update_countdown()

        logger.info(f"ReminderPopupUI created for task ID: {self.task.id if self.task else 'N/A'}, Title: {self.task.title if self.task else 'N/A'}")
        try: # TTS calls restored
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
        self.main_frame = bs.Frame(self) # Removed debug bootstyle="info"
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Top content frame for title and duration/countdown - Restored
        top_content_frame = bs.Frame(self.main_frame)
        top_content_frame.pack(fill=tk.X, pady=(0, 2))

        # Task Title Label (in top_content_frame, packed left) - Restored
        title_label = bs.Label(top_content_frame, text=self.task.title if self.task else "No Title",
                               font=("Helvetica", 14, "bold"), anchor="w",
                               wraplength=self.width - 80, justify=tk.LEFT, padding=(0,0,0,2))
        title_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))

        # Duration/Countdown Frame (in top_content_frame, packed right) - Restored
        duration_display_frame = bs.Frame(top_content_frame)
        duration_display_frame.pack(side=tk.RIGHT, fill=tk.NONE, expand=False, padx=(5,0))

        if self.task and self.task.duration and self.task.duration > 0:
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

        # Description Frame (Initially not packed, packed by toggle_expand_popup) - Restored
        self.desc_frame = bs.Frame(self.main_frame)

        self.description_text_widget = tk.Text(self.desc_frame, wrap=tk.WORD, height=5, relief=tk.FLAT,
                                                borderwidth=0, highlightthickness=0, font=("Helvetica", 10))
        desc_text_content = self.task.description if self.task and self.task.description else "No description."
        self.description_text_widget.insert(tk.END, desc_text_content)

        try:
            bg_color = self.cget('background')
            self.description_text_widget.config(state=tk.DISABLED, bg=bg_color)
        except tk.TclError:
            self.description_text_widget.config(state=tk.DISABLED, bg="SystemButtonFace")
        self.description_text_widget.pack(fill=tk.BOTH, expand=True)


        # Button Frame Setup (Focus Element)
        self.button_frame_ref = bs.Frame(self.main_frame) # Removed bootstyle="danger"
        self.button_frame_ref.pack_propagate(False) # Keep this if size issues were there
        self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(3,2)) # Ensure it's at bottom, adjust padding

        # Restore ALL Original Buttons with their "round" bootstyles
        self.expand_button = bs.Button(self.button_frame_ref,
                                   text="▼",
                                   command=self.toggle_expand_popup,
                                   bootstyle="info-outline-round")
        self.expand_button.pack(side=tk.LEFT, padx=2)
        ToolTip(self.expand_button, text="More Info")

        self.skip_button = bs.Button(self.button_frame_ref,
                                   text="⏩",
                                   command=self.skip_reminder,
                                   bootstyle="secondary-round")
        self.skip_button.pack(side=tk.RIGHT, padx=(2,0))
        ToolTip(self.skip_button, text="Skip Reminder")

        self.complete_button = bs.Button(self.button_frame_ref,
                                     text="✔️",
                                     command=self.complete_task,
                                     bootstyle="success-round")
        self.complete_button.pack(side=tk.RIGHT, padx=2)
        ToolTip(self.complete_button, text="Mark as Complete")

        self.reschedule_button = bs.Button(self.button_frame_ref,
                                       text="🔄",
                                       command=self.reschedule_task,
                                       bootstyle="warning-round")
        self.reschedule_button.pack(side=tk.RIGHT, padx=2)
        ToolTip(self.reschedule_button, text="Reschedule (+15m)")

    def _update_countdown(self):
        if self.remaining_work_seconds > 0:
            hours = self.remaining_work_seconds // 3600
            minutes = (self.remaining_work_seconds % 3600) // 60
            seconds = self.remaining_work_seconds % 60

            if hours > 0:
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                time_str = f"{minutes:02d}:{seconds:02d}"

            if hasattr(self, 'countdown_label') and self.countdown_label.winfo_exists(): # Restored
                self.countdown_label.config(text=time_str) # Restored

            self.remaining_work_seconds -= 1
            self.after_id = self.after(1000, self._update_countdown)
        elif hasattr(self, 'countdown_label') and self.countdown_label.winfo_exists():
            self.countdown_label.config(text="Time's up!") # Restored
            logger.info(f"Work duration timer for task ID: {self.task.id if self.task else 'N/A'} has finished. Auto-triggering completion.")
            self.complete_task()

    def reschedule_task(self): # Restored body
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

    def complete_task(self): # Restored body
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

    def skip_reminder(self): # Restored body
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        task_id_info = self.task.id if self.task else "N/A"
        logger.info(f"Popup: Skip requested for task ID: {task_id_info}")
        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self): # Restored body
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

    def toggle_expand_popup(self): # Restored body
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            if hasattr(self, 'desc_frame') and hasattr(self, 'button_frame_ref'):
                 self.desc_frame.pack(fill=tk.BOTH, expand=True, pady=(3,3), before=self.button_frame_ref)
            self.geometry(f"{self.width}x{self.expanded_height}")
            if hasattr(self, 'expand_button'):
                self.expand_button.config(text="▲")
                ToolTip(self.expand_button, text="Less Info")
        else:
            if hasattr(self, 'desc_frame'): self.desc_frame.pack_forget()
            self.geometry(f"{self.width}x{self.initial_height}")
            if hasattr(self, 'expand_button'):
                self.expand_button.config(text="▼")
                ToolTip(self.expand_button, text="More Info")

    def _on_mouse_press(self, event):
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y
        # logger.debug(f"Mouse press: x={event.x}, y={event.y}")

    def _on_mouse_release(self, event):
        # logger.debug(f"Mouse release: x={event.x}, y={event.y}")
        pass

    def _on_mouse_drag(self, event):
        new_x = event.x_root - self._drag_offset_x
        new_y = event.y_root - self._drag_offset_y
        self.geometry(f"+{new_x}+{new_y}")
        # logger.debug(f"Dragging to: +{new_x}+{new_y}")

# Example usage (remains for standalone testing if needed)
if __name__ == '__main__':
    class DummyTask:
        def __init__(self, id, title, description, duration):
            self.id = id
            self.title = title
            self.description = description
            self.duration = duration

    class DummyApp:
        def __init__(self):
            if not logging.getLogger().hasHandlers():
                 logging.basicConfig(level=logging.DEBUG)

            self.root = bs.Window(themename="solar")
            self.root.title("Main Test Window (for Popup)")

            self.sample_task = DummyTask(1, "Test Full UI Popup", "This is a description for the full UI test popup.", 30) # 30s duration for test

            self.callbacks = {
                'reschedule': lambda task_id, mins: logger.info(f"MAIN APP: Reschedule task {task_id} by {mins} mins."),
                'complete': lambda task_id: logger.info(f"MAIN APP: Complete task {task_id}."),
                'remove_from_active': lambda task_id: logger.info(f"MAIN APP: Popup for task {task_id} closed.")
            }

            show_button = bs.Button(self.root, text="Show Full UI Popup", command=self.show_dummy_popup)
            show_button.pack(pady=10)

            self.root.geometry("300x200")
            self.root.mainloop()

        def show_dummy_popup(self):
            popup = ReminderPopupUI(self.root, self.sample_task, self.callbacks)

    DummyApp()
