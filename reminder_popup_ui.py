import tkinter as tk
from tkinter import ttk
import tkinter.font
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
        self.is_wrapped = False
        self.wrapped_width = 100
        self.wrapped_height = 40
        self.expanded_state_before_wrap = False
        self._unwrap_binding_id = None
        self.nag_tts_after_id = None

        self.width = 380
        self.initial_height = 90
        self.expanded_height = 215

        # self.remaining_work_seconds = 0 # Still commented out
        # if self.task and self.task.duration and self.task.duration > 0:
        #     self.remaining_work_seconds = self.task.duration * 60

        self.geometry(f"{self.width}x{self.initial_height}+100+100")
        self.wm_attributes("-topmost", 1)
        self.resizable(False, False)

        self._on_mouse_press_binding_id = self.bind("<ButtonPress-1>", self._on_mouse_press)
        self._on_mouse_release_binding_id = self.bind("<ButtonRelease-1>", self._on_mouse_release)
        self._on_mouse_drag_binding_id = self.bind("<B1-Motion>", self._on_mouse_drag)

        # self.countdown_label = None # Still commented out
        # self.no_duration_label = None # Still commented out

        self.complete_var = tk.BooleanVar() # Ensure this is active
        self.complete_var.set(False)

        self._setup_ui()

        # TTS and other logs still commented out for this test
        # logger.info(f"ReminderPopupUI created for task ID: {self.task.id if self.task else 'N/A'}")
        # try: # TTS calls
        # except Exception as e:
        # self._schedule_nag_tts()

    def _handle_complete_toggle(self):
        if self.complete_var.get():
            if hasattr(self, 'complete_checkbutton') and self.complete_checkbutton.winfo_exists():
                self.complete_checkbutton.config(state=tk.DISABLED)
            self.complete_task()

    def _truncate_text_to_fit(self, text, max_width_px, font_details):
        if not text:
            return ""
        try:
            font_obj = tkinter.font.Font(font=font_details)
            current_text = str(text or "").strip()
            text_width = font_obj.measure(current_text)
            if text_width <= max_width_px:
                return current_text
            ellipsis = "..."
            ellipsis_width = font_obj.measure(ellipsis)
            if ellipsis_width > max_width_px:
                if font_obj.measure(current_text) <= max_width_px:
                    return current_text
                return ""
            truncated_text = current_text
            while len(truncated_text) > 0:
                if font_obj.measure(truncated_text + ellipsis) <= max_width_px:
                    return truncated_text + ellipsis
                truncated_text = truncated_text[:-1]
            return ellipsis
        except Exception as e:
            logger.error(f"Error in _truncate_text_to_fit for '{text}': {e}", exc_info=True)
            return str(text or "").strip()

    def _calculate_tinted_color(self, hex_color, factor=0.5):
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            if luminance < 0.5:
                new_r = int(r + (255 - r) * factor)
                new_g = int(g + (255 - g) * factor)
                new_b = int(b + (255 - b) * factor)
            else:
                new_r = int(r * (1 - factor))
                new_g = int(g * (1 - factor))
                new_b = int(b * (1 - factor))
            return f"#{new_r:02x}{new_g:02x}{new_b:02x}"
        except Exception as e:
            logger.error(f"Error calculating tinted color for {hex_color}: {e}")
            return None

    def _setup_ui(self):
        # Create main frame (essential)
        self.main_frame = bs.Frame(self, padding=(5,3,5,3))
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Comment out the test_label from the previous step
        # test_label = bs.Label(self.main_frame, text="TEST VISIBILITY - If you see this, base popup works.")
        # test_label.pack(padx=10, pady=10, expand=True, fill=tk.BOTH)

        self.top_content_frame = bs.Frame(self.main_frame)
        self.top_content_frame.pack(side=tk.TOP, fill=tk.X, pady=(0,2), anchor='n')

        # Re-add complete_checkbutton
        self.complete_checkbutton = bs.Checkbutton(self.top_content_frame,
                                               variable=self.complete_var,
                                               command=self._handle_complete_toggle,
                                               bootstyle="success-round",
                                               text="")
        self.complete_checkbutton.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(self.complete_checkbutton, text="Mark as Complete")

        # Re-add title_label (simplified)
        title_font_details = ("Helvetica", 14, "bold")
        self.title_label = bs.Label(self.top_content_frame,
                               text="Short Test Title", # Hardcoded short text
                               font=title_font_details,
                               # No wraplength for this test
                               anchor="w",
                               justify=tk.LEFT)
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))

        # duration_display_frame and its contents remain commented out for now
        # self.duration_display_frame = bs.Frame(self.top_content_frame)
        # self.duration_display_frame.pack(side=tk.RIGHT, fill=tk.NONE, expand=False, padx=(5,0))
        # ... (countdown_label / no_duration_label) ...

        # desc_frame remains commented out for this test
        # self.desc_frame = bs.Frame(self.main_frame)
        # ... (description_text_widget) ...

        self.button_frame_ref = bs.Frame(self.main_frame)
        self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(3,2), ipady=2)
        # Add a temporary label to see if button_frame_ref is visible
        temp_bottom_label = bs.Label(self.button_frame_ref, text="Bottom Frame Visible")
        temp_bottom_label.pack(padx=5, pady=5)

        logger.info("Simplified _setup_ui: Added complete_checkbutton and simple title_label to top_content_frame.")


    def _update_countdown(self):
        if hasattr(self, 'remaining_work_seconds') and self.remaining_work_seconds > 0: # Added check
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
            logger.info(f"Work duration timer for task ID: {self.task.id if self.task else 'N/A'} has finished.")

    def reschedule_task(self):
        self._cancel_nag_tts()
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
        self._cancel_nag_tts()
        task_id_info = self.task.id if self.task else "N/A"
        logger.debug(f"POPUP_ACTION: Task ID {task_id_info} marked complete.")
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
        self._cancel_nag_tts()
        logger.debug(f"POPUP_ACTION: 'skip_reminder' called for task ID: {self.task.id if self.task else 'N/A'}. Closing popup.")
        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        task_id_info = self.task.id if self.task else "N/A"
        logger.debug(f"POPUP_CLEANUP: Cleaning up for task ID {task_id_info}")
        if hasattr(self, 'after_id') and self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self._cancel_nag_tts()
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

    def toggle_expand_popup(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            # This part will not work as desc_frame and button_frame_ref are not created in simplified _setup_ui
            # if hasattr(self, 'desc_frame') and hasattr(self, 'button_frame_ref'):
            #      self.button_frame_ref.pack_forget()
            #      self.desc_frame.pack(fill=tk.BOTH, expand=True, pady=(3,3))
            #      self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(5,0), ipady=5)
            self.geometry(f"{self.width}x{self.expanded_height}")
            # if hasattr(self, 'expand_button'):
            #     self.expand_button.config(text="▲")
            #     ToolTip(self.expand_button, text="Less Info")
        else:
            # if hasattr(self, 'desc_frame'):
            #     self.desc_frame.pack_forget()
            self.geometry(f"{self.width}x{self.initial_height}")
            # if hasattr(self, 'expand_button'):
            #     self.expand_button.config(text="▼")
            #     ToolTip(self.expand_button, text="More Info")

    def _on_mouse_press(self, event):
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y

    def _on_mouse_release(self, event):
        pass

    def _on_mouse_drag(self, event):
        new_x = event.x_root - self._drag_offset_x
        new_y = event.y_root - self._drag_offset_y
        self.geometry(f"+{new_x}+{new_y}")

    def _calculate_corner_x(self) -> int:
        screen_width = self.winfo_screenwidth()
        padding = 10
        return screen_width - self.wrapped_width - padding

    def _calculate_corner_y(self) -> int:
        screen_height = self.winfo_screenheight()
        padding_from_bottom = 40
        return screen_height - self.wrapped_height - padding_from_bottom

    def toggle_wrap_view(self, event=None):
        print(f"DEBUG: toggle_wrap_view ENTRY: current self.is_wrapped={self.is_wrapped}, self.is_expanded={self.is_expanded}, event={event}")
        logger.info(f"toggle_wrap_view called. Current is_wrapped: {self.is_wrapped}. Event: {event}")
        self.is_wrapped = not self.is_wrapped
        if self.is_wrapped:
            print(f"DEBUG: WRAPPING branch: self.is_wrapped is now True.")
            logger.debug("Wrapping popup...")
            self.expanded_state_before_wrap = self.is_expanded
            print(f"DEBUG: WRAPPING: Stored self.expanded_state_before_wrap = {self.expanded_state_before_wrap}")
            # ... (rest of wrap logic largely commented out due to simplified UI) ...
            new_x = self._calculate_corner_x()
            new_y = self._calculate_corner_y()
            new_geometry = f"{self.wrapped_width}x{self.wrapped_height}+{new_x}+{new_y}"
            print(f"DEBUG: WRAPPING: Setting geometry to: {new_geometry}")
            self.geometry(new_geometry)
            if hasattr(self, '_on_mouse_press_binding_id') and self._on_mouse_press_binding_id:
                self.unbind("<ButtonPress-1>", self._on_mouse_press_binding_id)
            if hasattr(self, '_on_mouse_release_binding_id') and self._on_mouse_release_binding_id:
                self.unbind("<ButtonRelease-1>", self._on_mouse_release_binding_id)
            if hasattr(self, '_on_mouse_drag_binding_id') and self._on_mouse_drag_binding_id:
                self.unbind("<B1-Motion>", self._on_mouse_drag_binding_id)
            self._unwrap_binding_id = self.bind("<ButtonPress-1>", self.toggle_wrap_view)
        else:
            print(f"DEBUG: UNWRAPPING branch: self.is_wrapped is now False.")
            logger.debug("Unwrapping popup...")
            if self._unwrap_binding_id:
                self.unbind("<ButtonPress-1>", self._unwrap_binding_id)
                self._unwrap_binding_id = None
            self._on_mouse_press_binding_id = self.bind("<ButtonPress-1>", self._on_mouse_press)
            self._on_mouse_release_binding_id = self.bind("<ButtonRelease-1>", self._on_mouse_release)
            self._on_mouse_drag_binding_id = self.bind("<B1-Motion>", self._on_mouse_drag)

            self.geometry(f"{self.width}x{self.initial_height}") # Restore initial geometry
            self._setup_ui() # Attempt to restore fuller UI, though some elements are still commented out

        logger.debug(f"toggle_wrap_view finished. is_wrapped: {self.is_wrapped}")
        print(f"DEBUG: toggle_wrap_view EXIT: self.is_wrapped={self.is_wrapped}, current geometry={self.geometry()}")

    def start_countdown_action(self):
        logger.debug(f"POPUP_ACTION: 'start_countdown_action' called for task ID: {self.task.id if self.task else 'N/A'}.")
        self._cancel_nag_tts()
        if hasattr(self, 'remaining_work_seconds') and self.remaining_work_seconds > 0 :
            self._update_countdown()
        # if hasattr(self, 'start_button'): # Start button not in this simplified UI
        #     self.start_button.config(state=tk.DISABLED)
        #     ToolTip(self.start_button, text="Timer Started")

    def _schedule_nag_tts(self):
        if not self.winfo_exists():
            return
        # Nag TTS commented out for this test
        pass

    def _cancel_nag_tts(self):
        if self.nag_tts_after_id:
            logger.debug(f"POPUP_NAG: Cancelling TTS nag ID: {self.nag_tts_after_id}")
            self.after_cancel(self.nag_tts_after_id)
            self.nag_tts_after_id = None
        else:
            logger.debug("POPUP_NAG: No active TTS nag to cancel.")

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

    sample_task = DummyTask(1, "Test Popup with Title/Timer", "This is a test description that won't be seen.", 65)

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
