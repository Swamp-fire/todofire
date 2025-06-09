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
        self.is_expanded = False # For toggle_expand_popup text logic
        self._drag_offset_x = 0
        self._drag_offset_y = 0

        # self.width = 380 # Not used for this fixed geometry
        self.remaining_work_seconds = 0
        if self.task and self.task.duration and self.task.duration > 0:
            self.remaining_work_seconds = self.task.duration * 60

        # Set fixed large geometry for this debug step
        self.geometry("500x500+100+100")

        self.wm_attributes("-topmost", 1)
        self.resizable(False, False)

        self.bind("<ButtonPress-1>", self._on_mouse_press)
        self.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.bind("<B1-Motion>", self._on_mouse_drag)

        self._setup_ui()

        # CRITICAL: Call to _update_countdown() REMAINS COMMENTED OUT
        # if self.remaining_work_seconds > 0:
        #     self._update_countdown()

        logger.info(f"ReminderPopupUI (Debug Step: Large Popup, Default bs.Button) created for task ID: {self.task.id if self.task else 'N/A'}")
        # CRITICAL: TTS calls in __init__ REMAINS COMMENTED OUT
        # try:
        #     # ... TTS logic ...
        # except Exception as e:
        #     logger.error(f"CRITICAL: Unexpected error initiating TTS from ReminderPopupUI: {e}", exc_info=True)

    def _setup_ui(self):
        self.main_frame = bs.Frame(self, bootstyle="light")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- top_content_frame and desc_frame remain COMMENTED OUT ---
        # # Top content frame (title/timer)
        # # ...
        # # Description Frame
        # # ...

        # Button Frame Setup
        self.button_frame_ref = bs.Frame(self.main_frame, bootstyle="secondary") # Debug style
        self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5, ipady=5)

        # Add ALL FOUR bs.Button instances with NO bootstyle/style (absolute default)
        # NO fixed width. All packed side=tk.LEFT for this test.

        self.expand_button = bs.Button(self.button_frame_ref,
                                   text="▼",
                                   command=self.toggle_expand_popup)
        self.expand_button.pack(side=tk.LEFT, padx=5, pady=5)
        ToolTip(self.expand_button, text="More Info")

        self.reschedule_button = bs.Button(self.button_frame_ref,
                                       text="🔄",
                                       command=self.reschedule_task)
        self.reschedule_button.pack(side=tk.LEFT, padx=5, pady=5)
        ToolTip(self.reschedule_button, text="Reschedule (+15m)")

        self.complete_button = bs.Button(self.button_frame_ref,
                                     text="✔️",
                                     command=self.complete_task)
        self.complete_button.pack(side=tk.LEFT, padx=5, pady=5)
        ToolTip(self.complete_button, text="Mark as Complete")

        self.skip_button = bs.Button(self.button_frame_ref,
                                   text="⏩",
                                   command=self.skip_reminder)
        self.skip_button.pack(side=tk.LEFT, padx=5, pady=5)
        ToolTip(self.skip_button, text="Skip Reminder")

    def _update_countdown(self):
        pass # Keep disabled

    def reschedule_task(self):
        logger.info("DEBUG: Reschedule button clicked")
        self._cleanup_and_destroy()

    def complete_task(self):
        logger.info("DEBUG: Complete button clicked")
        self._cleanup_and_destroy()

    def skip_reminder(self):
        logger.info("DEBUG: Skip button clicked")
        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        logger.debug(f"Popup: Cleaning up for task ID {self.task.id if self.task else 'N/A'}")
        if hasattr(self, 'after_id') and self.after_id: # Check if after_id exists
            self.after_cancel(self.after_id)
            self.after_id = None

        # Callbacks might not exist if app_callbacks was None
        if hasattr(self, 'app_callbacks') and self.app_callbacks and 'remove_from_active' in self.app_callbacks:
            try:
                self.app_callbacks['remove_from_active'](self.task.id if self.task else None)
            except Exception as e:
                logger.error(f"Popup: Error calling remove_from_active callback: {e}", exc_info=True)
        self.destroy()

    def toggle_expand_popup(self):
        self.is_expanded = not self.is_expanded
        # self.desc_frame.pack(...) # Commented out
        # self.geometry(...) # Commented out
        if hasattr(self, 'expand_button'): # Check if button exists
            if self.is_expanded:
                self.expand_button.config(text="▲")
                ToolTip(self.expand_button, text="Less Info")
            else:
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

if __name__ == '__main__':
    try:
        import ttkbootstrap as bs
        root = bs.Window(themename="solar")
        root.title("Main Test Window (for Popup)")
    except ImportError:
        root = tk.Tk()
        root.title("Main Test Window (Tkinter fallback)")

    logging.basicConfig(level=logging.DEBUG)

    class DummyTask:
        def __init__(self, id, title, description=None, duration=0):
            self.id = id
            self.title = title
            self.description = description
            self.duration = duration

    sample_task = DummyTask(1, "Default bs.Button Test")

    def show_popup(task_obj):
        logger.info(f"Attempting to show popup for task: {task_obj.title if task_obj else 'N/A'}")
        try:
            dummy_callbacks = {
                'reschedule': lambda tid, mins: logger.info(f"Dummy Reschedule: {tid} by {mins}"),
                'complete': lambda tid: logger.info(f"Dummy Complete: {tid}"),
                'remove_from_active': lambda tid: logger.info(f"Dummy Remove From Active: {tid}")
            }
            popup = ReminderPopupUI(root, task_obj, dummy_callbacks)
        except Exception as e:
            logger.error(f"Error creating ReminderPopupUI in direct test: {e}", exc_info=True)

    tk.Button(root, text="Show Default bs.Button Popup", command=lambda: show_popup(sample_task)).pack(pady=10)

    root.geometry("300x200")
    root.mainloop()
