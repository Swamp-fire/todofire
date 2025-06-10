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
        self.is_expanded = False # Kept for toggle_expand_popup text change
        self._drag_offset_x = 0
        self._drag_offset_y = 0

        self.width = 380 # Ensure target width
        self.initial_height = 90  # Target "thinner" value
        self.expanded_height = 215 # Target "thinner" value

        self.remaining_work_seconds = 0
        if self.task and self.task.duration and self.task.duration > 0:
            self.remaining_work_seconds = self.task.duration * 60

        self.geometry(f"{self.width}x{self.initial_height}+100+100")

        self.wm_attributes("-topmost", 1)
        self.resizable(False, False)

        self.bind("<ButtonPress-1>", self._on_mouse_press)
        self.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.bind("<B1-Motion>", self._on_mouse_drag)

        self._setup_ui()

        # CRITICAL: Call to _update_countdown() REMAINS COMMENTED OUT for this step
        # if self.remaining_work_seconds > 0:
        #     self._update_countdown()

        logger.info(f"ReminderPopupUI (Thinner Geometry Test) created for task ID: {self.task.id if self.task else 'N/A'}")
        # CRITICAL: TTS calls in __init__ REMAINS COMMENTED OUT for this step
        # try:
        #     if self.task and self.task.title:
        #         speech_text = f"Reminder for task: {self.task.title}"
        #         logger.info(f"Popup: Requesting TTS for: '{speech_text}'")
        #         tts_manager.speak(speech_text)
        #     elif self.task:
        #         logger.warning(f"Popup: Task ID {self.task.id if self.task else 'N/A'} has no title. Speaking generic reminder.")
        #         tts_manager.speak("Reminder for task with no title.")
        #     else:
        #         logger.error("Popup: Task details are unavailable for TTS. Speaking generic error.")
        #         tts_manager.speak("Reminder triggered, but task details are unavailable.", error_context=True)
        # except Exception as e:
        #     logger.error(f"CRITICAL: Unexpected error initiating TTS from ReminderPopupUI: {e}", exc_info=True)

    def _setup_ui(self):
        self.main_frame = bs.Frame(self, padding=(5,3,5,3)) # Adjusted padding
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2) # Outer padding for main_frame itself

        # Restore top_content_frame
        self.top_content_frame = bs.Frame(self.main_frame)
        self.top_content_frame.pack(side=tk.TOP, fill=tk.X, pady=(0,2), anchor='n') # Adjusted pady

        # Restore title_label
        self.title_label = bs.Label(self.top_content_frame, text=(self.task.title if self.task and self.task.title else "No Title"),
                               font=("Helvetica", 14, "bold"),
                               wraplength=(self.width - 100),
                               anchor="w", justify=tk.LEFT, padding=(0,0,0,2)) # Adjusted padding
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))

        # Restore duration_display_frame (contains countdown or no_duration message)
        self.duration_display_frame = bs.Frame(self.top_content_frame)
        self.duration_display_frame.pack(side=tk.RIGHT, fill=tk.NONE, expand=False, padx=(5,0)) # This should be correct

        if self.task and self.task.duration and self.task.duration > 0:
            hours = self.remaining_work_seconds // 3600
            minutes = (self.remaining_work_seconds % 3600) // 60
            seconds = self.remaining_work_seconds % 60

            if hours > 0:
                initial_duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                initial_duration_str = f"{minutes:02d}:{seconds:02d}"

            self.countdown_label = bs.Label(self.duration_display_frame, text=initial_duration_str,
                                            font=("Helvetica", 12, "bold"), style="info.TLabel")
            self.countdown_label.pack(side=tk.LEFT)
        else:
            no_duration_label = bs.Label(self.duration_display_frame, text="No specific work duration.", style="secondary.TLabel")
            no_duration_label.pack(side=tk.LEFT)

        # Description Frame - Restored
        self.desc_frame = bs.Frame(self.main_frame)
        # Not packed here; packed by toggle_expand_popup

        self.description_text_widget = tk.Text(self.desc_frame, wrap=tk.WORD, height=5, relief=tk.FLAT,
                                                borderwidth=0, highlightthickness=0, font=("Helvetica", 10))
        desc_text_content = self.task.description if self.task and self.task.description else "No description."
        self.description_text_widget.insert(tk.END, desc_text_content)

        try:
            bg_color = self.cget('background')
            self.description_text_widget.config(state=tk.DISABLED, bg=bg_color)
        except tk.TclError:
            self.description_text_widget.config(state=tk.DISABLED, bg="SystemButtonFace")
        self.description_text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


        # Button Frame Setup
        self.button_frame_ref = bs.Frame(self.main_frame)
        self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(3,2), ipady=2) # Adjusted pady and ipady

        # Buttons use default styles (no explicit bootstyle or style)
        self.expand_button = bs.Button(self.button_frame_ref,
                                   text="▼",
                                   command=self.toggle_expand_popup,
                                   bootstyle="info-outline-round") # Apply round style
        self.expand_button.pack(side=tk.LEFT, padx=2)
        ToolTip(self.expand_button, text="More Info")

        # Action buttons packed to the right (visual order from right to left: skip, complete, reschedule)
        self.skip_button = bs.Button(self.button_frame_ref,
                                   text="⏩",
                                   command=self.skip_reminder,
                                   bootstyle="secondary-round") # Apply round style
        self.skip_button.pack(side=tk.RIGHT, padx=(2,0)) # Adjusted padx
        ToolTip(self.skip_button, text="Skip Reminder")

        self.complete_button = bs.Button(self.button_frame_ref,
                                     text="✔️",
                                     command=self.complete_task,
                                     bootstyle="success-round") # Apply round style
        self.complete_button.pack(side=tk.RIGHT, padx=2) # Adjusted padx
        ToolTip(self.complete_button, text="Mark as Complete")

        self.reschedule_button = bs.Button(self.button_frame_ref,
                                       text="🔄",
                                       command=self.reschedule_task,
                                       bootstyle="warning-round") # Apply round style
        self.reschedule_button.pack(side=tk.RIGHT, padx=2) # Adjusted padx
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

            if hasattr(self, 'countdown_label') and self.countdown_label.winfo_exists():
                self.countdown_label.config(text=time_str)

            self.remaining_work_seconds -= 1
            self.after_id = self.after(1000, self._update_countdown)
        elif hasattr(self, 'countdown_label') and self.countdown_label.winfo_exists():
            self.countdown_label.config(text="Time's up!")
            logger.info(f"Work duration timer for task ID: {self.task.id if self.task else 'N/A'} has finished. Auto-triggering completion.")
            # self.complete_task() # Auto-completion might be too aggressive for some users
        # pass

    def reschedule_task(self):
        task_id_info = self.task.id if self.task else "N/A"
        logger.debug(f"POPUP_ACTION: Attempting 'reschedule' callback for task ID: {task_id_info}.")
        if self.app_callbacks and 'reschedule' in self.app_callbacks:
            try:
                self.app_callbacks['reschedule'](self.task.id if self.task else None, 15)
                logger.debug(f"POPUP_ACTION: 'reschedule' callback attempted for task ID: {task_id_info}.")
            except Exception as e:
                logger.error(f"Popup: Error calling reschedule callback for task ID {task_id_info}: {e}", exc_info=True)
        else:
            logger.warning(f"Popup: 'reschedule' callback not found or app_callbacks not set for task ID: {task_id_info}")
        self._cleanup_and_destroy()

    def complete_task(self):
        task_id_info = self.task.id if self.task else "N/A"
        logger.debug(f"POPUP_ACTION: Attempting 'complete' callback for task ID: {task_id_info}.")
        if self.app_callbacks and 'complete' in self.app_callbacks:
            try:
                self.app_callbacks['complete'](self.task.id if self.task else None)
                logger.debug(f"POPUP_ACTION: 'complete' callback attempted for task ID: {task_id_info}.")
            except Exception as e:
                logger.error(f"Popup: Error calling complete callback for task ID {task_id_info}: {e}", exc_info=True)
        else:
            logger.warning(f"Popup: 'complete' callback not found or app_callbacks not set for task ID: {task_id_info}")
        self._cleanup_and_destroy()

    def skip_reminder(self):
        logger.debug(f"POPUP_ACTION: 'skip_reminder' called for task ID: {self.task.id if self.task else 'N/A'}. Closing popup.")
        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        task_id_info = self.task.id if self.task else "N/A" # For logging before task might be None
        logger.debug(f"POPUP_CLEANUP: Cleaning up for task ID {task_id_info}")
        if hasattr(self, 'after_id') and self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

        if hasattr(self, 'app_callbacks') and self.app_callbacks and 'remove_from_active' in self.app_callbacks:
            try:
                logger.debug(f"POPUP_CLEANUP: Attempting 'remove_from_active' callback for task ID: {task_id_info}.")
                self.app_callbacks['remove_from_active'](self.task.id if self.task else None)
                logger.debug(f"POPUP_CLEANUP: 'remove_from_active' callback attempted for task ID: {task_id_info}.")
            except Exception as e:
                logger.error(f"Popup: Error calling remove_from_active callback: {e}", exc_info=True)

        logger.debug(f"POPUP_CLEANUP: Destroying window for task ID: {task_id_info}.")
        if hasattr(self, 'destroy'):
             self.destroy()

    def toggle_expand_popup(self): # Restored full logic
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            if hasattr(self, 'desc_frame') and hasattr(self, 'button_frame_ref'):
                 # Pack desc_frame before button_frame_ref by repacking button_frame_ref after desc_frame
                 self.button_frame_ref.pack_forget() # Temporarily unmap
                 self.desc_frame.pack(fill=tk.BOTH, expand=True, pady=(3,3)) # Pack description
                 self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(5,0), ipady=5) # Re-pack buttons at bottom

            self.geometry(f"{self.width}x{self.expanded_height}")
            if hasattr(self, 'expand_button'):
                self.expand_button.config(text="▲")
                ToolTip(self.expand_button, text="Less Info")
        else: # Collapsing
            if hasattr(self, 'desc_frame'):
                self.desc_frame.pack_forget()
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

    sample_task = DummyTask(1, "Test Popup with Title/Timer", "This is a test description that won't be seen.", 65) # 1 min 5 sec duration

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

    tk.Button(root, text="Show Title/Timer Popup", command=lambda: show_popup(sample_task)).pack(pady=10)

    root.geometry("300x200")
    root.mainloop()
