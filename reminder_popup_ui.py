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

        # Placeholder for image loading - actual image files would be needed
        # Ensure an 'assets' directory exists with these images or adjust paths.
        try:
            self.img_expand = tk.PhotoImage(file="assets/more_info_round.png")
            self.img_wrap = tk.PhotoImage(file="assets/minimize_round.png")
            self.img_start = tk.PhotoImage(file="assets/start_round.png")
            self.img_skip = tk.PhotoImage(file="assets/skip_round.png")
            # self.img_complete = tk.PhotoImage(file="assets/complete_round.png") # Removed
            self.img_reschedule = tk.PhotoImage(file="assets/reschedule_round.png")
            self.img_checkbox_unchecked = tk.PhotoImage(file="assets/checkbox_round_unchecked.png")
            self.img_checkbox_checked = tk.PhotoImage(file="assets/checkbox_round_checked.png")
            # Add hover/pressed images if planned, e.g., self.img_start_hover
        except tk.TclError as e:
            logger.error(f"Error loading placeholder button images: {e}. Ensure 'assets' folder and dummy PNGs exist.")
            # Fallback or default images could be set here if desired
            self.img_expand = None # Or some default tk.PhotoImage
            self.img_wrap = None
            self.img_start = None
            self.img_skip = None
            # self.img_complete = None # Removed
            self.img_reschedule = None
            logger.error(f"Error loading checkbox images: {e}. Using None for checkbox images.")
            self.img_checkbox_unchecked = None
            self.img_checkbox_checked = None

        self.overrideredirect(True)
        self.task = task
        self.app_callbacks = app_callbacks
        self.after_id = None
        self.is_expanded = False # Kept for toggle_expand_popup text change
        self.checkbox_is_checked = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self.is_wrapped = False
        self.wrapped_width = 100
        self.wrapped_height = 40
        self.expanded_state_before_wrap = False
        self._unwrap_binding_id = None
        self.nag_tts_after_id = None # Instruction 1.a

        self.width = 380 # Ensure target width
        self.initial_height = 90  # Target "thinner" value
        self.expanded_height = 215 # Target "thinner" value

        self.remaining_work_seconds = 0
        if self.task and self.task.duration and self.task.duration > 0:
            self.remaining_work_seconds = self.task.duration * 60

        self.geometry(f"{self.width}x{self.initial_height}+100+100")

        self.wm_attributes("-topmost", 1)
        self.resizable(False, False)

        # Store binding IDs - Instruction 1.b
        self._on_mouse_press_binding_id = self.bind("<ButtonPress-1>", self._on_mouse_press)
        self._on_mouse_release_binding_id = self.bind("<ButtonRelease-1>", self._on_mouse_release)
        self._on_mouse_drag_binding_id = self.bind("<B1-Motion>", self._on_mouse_drag)

        # Initialize conditionally created labels - Instruction 1.d (partial, rest in _setup_ui)
        self.countdown_label = None
        self.no_duration_label = None

        self._setup_ui()

        # Automatic countdown start removed. User must click "Start".
        # if self.remaining_work_seconds > 0:
        #     # self._update_countdown() # Countdown now starts manually
        #     pass

        logger.info(f"ReminderPopupUI created for task ID: {self.task.id if self.task else 'N/A'}")
        # Restore TTS calls in __init__
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

        self._schedule_nag_tts() # Instruction 1.b

    def _on_checkbox_click(self, event=None):
        if not self.checkbox_is_checked: # Only proceed if not already checked
            self.checkbox_is_checked = True # Mark as checked

            # Update image to checked state, if images are loaded
            if self.img_checkbox_checked and hasattr(self, 'complete_checkbox_label'):
                self.complete_checkbox_label.config(image=self.img_checkbox_checked)
            elif hasattr(self, 'complete_checkbox_label'): # Fallback text update
                self.complete_checkbox_label.config(text="[X]")


            # Call the original complete_task method
            # complete_task() will handle logging, callbacks, and destroying the popup
            self.complete_task()
            # No need to worry about disabling, as complete_task destroys the window.
        else:
            # Optionally, could allow unchecking if complete_task didn't destroy window
            # For now, once checked and popup closes, it's done.
            logger.debug("Checkbox already considered checked and task completion initiated.")

    def _calculate_tinted_color(self, hex_color, factor=0.5):
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

            # Calculate luminance to decide whether to lighten or darken
            # Using a common luminance formula
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

            if luminance < 0.5: # If dark, lighten
                new_r = int(r + (255 - r) * factor)
                new_g = int(g + (255 - g) * factor)
                new_b = int(b + (255 - b) * factor)
            else: # If light, darken
                new_r = int(r * (1 - factor))
                new_g = int(g * (1 - factor))
                new_b = int(b * (1 - factor))

            return f"#{new_r:02x}{new_g:02x}{new_b:02x}"
        except Exception as e:
            logger.error(f"Error calculating tinted color for {hex_color}: {e}")
            return None # Fallback

    def _setup_ui(self):
        # Ensure these are initialized for Instruction 1.d
        self.countdown_label = None
        self.no_duration_label = None

        self.main_frame = bs.Frame(self, padding=(5,3,5,3)) # Adjusted padding
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2) # Outer padding for main_frame itself

        # Restore top_content_frame
        self.top_content_frame = bs.Frame(self.main_frame)
        self.top_content_frame.pack(side=tk.TOP, fill=tk.X, pady=(0,2), anchor='n')

        # New Round Checkbox for Completing Task (RELOCATED)
        initial_checkbox_image = self.img_checkbox_unchecked # Assuming self.img_checkbox_unchecked is loaded in __init__
        fallback_text = "[ ]"

        if not initial_checkbox_image:
            self.complete_checkbox_label = tk.Label(self.top_content_frame, text=fallback_text, font=("Helvetica", 12))
            # Optionally, use bs.Label with a link style for theme consistency:
            # self.complete_checkbox_label = bs.Label(self.top_content_frame, text=fallback_text, bootstyle="secondary-link")
            logger.info("Fallback text checkbox created in top_content_frame as image failed.")
        else:
            self.complete_checkbox_label = tk.Label(self.top_content_frame, image=initial_checkbox_image)
            try:
                # Attempt to make tk.Label background match its new parent (top_content_frame)
                parent_bg = self.top_content_frame.cget("background")
                self.complete_checkbox_label.config(bg=parent_bg)
            except tk.TclError:
                logger.warning("Could not match checkbox label bg to top_content_frame bg.")

        self.complete_checkbox_label.pack(side=tk.LEFT, padx=(0, 5)) # Pack checkbox to the left first
        self.complete_checkbox_label.bind("<Button-1>", self._on_checkbox_click)
        ToolTip(self.complete_checkbox_label, text="Mark as Complete")

        # Title_label (packed after checkbox)
        self.title_label = bs.Label(self.top_content_frame, text=(self.task.title if self.task and self.task.title else "No Title"),
                               font=("Helvetica", 14, "bold"),
                               wraplength=(self.width - 140), # Adjust wraplength if needed due to checkbox
                               anchor="w", justify=tk.LEFT, padding=(0,0,0,2))
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5)) # Original packing for title

        # Duration_display_frame (remains on the right)
        self.duration_display_frame = bs.Frame(self.top_content_frame)
        self.duration_display_frame.pack(side=tk.RIGHT, fill=tk.NONE, expand=False, padx=(5,0))

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
            self.no_duration_label = bs.Label(self.duration_display_frame, text="No specific work duration.", style="secondary.TLabel") # Assign to self
            self.no_duration_label.pack(side=tk.LEFT)

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

        # Packing remains:
        self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(3,2), ipady=2)

        # Expand Button
        if self.img_expand:
            self.expand_button = bs.Button(self.button_frame_ref,
                                       image=self.img_expand,
                                       command=self.toggle_expand_popup,
                                       bootstyle="info-link")
            self.expand_button.pack(side=tk.LEFT, padx=2)
            ToolTip(self.expand_button, text="More Info")
        else:
            self.expand_button = bs.Button(self.button_frame_ref,
                                       text="▼", # Fallback text
                                       command=self.toggle_expand_popup,
                                       bootstyle="info-link") # Fallback style, now link
            self.expand_button.pack(side=tk.LEFT, padx=2)
            ToolTip(self.expand_button, text="More Info (img err)")

        # Wrap Button
        if self.img_wrap:
            self.wrap_button = bs.Button(self.button_frame_ref,
                                           image=self.img_wrap,
                                           command=self.toggle_wrap_view,
                                           bootstyle="info-link")
            self.wrap_button.pack(side=tk.LEFT, padx=2)
            ToolTip(self.wrap_button, text="Minimize to Corner")
        else:
            self.wrap_button = bs.Button(self.button_frame_ref, text="↘️",
                                           command=self.toggle_wrap_view,
                                           bootstyle="info-link")
            self.wrap_button.pack(side=tk.LEFT, padx=2)
            ToolTip(self.wrap_button, text="Minimize to Corner (img err)")

        # Start Button
        if self.img_start:
            self.start_button = bs.Button(self.button_frame_ref,
                                           image=self.img_start,
                                           command=self.start_countdown_action,
                                           bootstyle="success-link")
            self.start_button.pack(side=tk.LEFT, padx=2)
            ToolTip(self.start_button, text="Start Work Session Timer")
        else:
            self.start_button = bs.Button(self.button_frame_ref, text="▶ Start",
                                           command=self.start_countdown_action,
                                           bootstyle="success-link")
            self.start_button.pack(side=tk.LEFT, padx=2)
            ToolTip(self.start_button, text="Start Work Session Timer (img err)")

        # Action buttons packed to the right (visual order from right to left: skip, complete, reschedule)

        # Skip Button
        if self.img_skip:
            self.skip_button = bs.Button(self.button_frame_ref,
                                       image=self.img_skip,
                                       command=self.skip_reminder,
                                       bootstyle="secondary-link")
            self.skip_button.pack(side=tk.RIGHT, padx=(2,0))
            ToolTip(self.skip_button, text="Skip Reminder")
        else:
            self.skip_button = bs.Button(self.button_frame_ref,
                                       text="⏩",
                                       command=self.skip_reminder,
                                       bootstyle="secondary-link")
            self.skip_button.pack(side=tk.RIGHT, padx=(2,0))
            ToolTip(self.skip_button, text="Skip Reminder (img err)")

        # Reschedule Button
        if self.img_reschedule:
            self.reschedule_button = bs.Button(self.button_frame_ref,
                                           image=self.img_reschedule,
                                           command=self.reschedule_task,
                                           bootstyle="warning-link")
            self.reschedule_button.pack(side=tk.RIGHT, padx=2)
            ToolTip(self.reschedule_button, text="Reschedule (+15m)")
        else:
            self.reschedule_button = bs.Button(self.button_frame_ref,
                                           text="🔄",
                                           command=self.reschedule_task,
                                           bootstyle="warning-link")
            self.reschedule_button.pack(side=tk.RIGHT, padx=2)
            ToolTip(self.reschedule_button, text="Reschedule (+15m) (img err)")

    def _update_countdown(self): # Ensure this method and its logic are intact
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
        self._cancel_nag_tts() # Instruction 4.b
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
        self._cancel_nag_tts() # Instruction 4.c
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
        self._cancel_nag_tts() # Instruction 4.d
        logger.debug(f"POPUP_ACTION: 'skip_reminder' called for task ID: {self.task.id if self.task else 'N/A'}. Closing popup.")
        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        task_id_info = self.task.id if self.task else "N/A" # For logging before task might be None
        logger.debug(f"POPUP_CLEANUP: Cleaning up for task ID {task_id_info}")

        if hasattr(self, 'after_id') and self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

        self._cancel_nag_tts() # Instruction 4.e

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
                # if not self.img_expand: # Only set text if not using image
                #    self.expand_button.config(text="▲")
                ToolTip(self.expand_button, text="Less Info")
        else: # Collapsing
            if hasattr(self, 'desc_frame'):
                self.desc_frame.pack_forget()
            self.geometry(f"{self.width}x{self.initial_height}")
            if hasattr(self, 'expand_button'):
                # if not self.img_expand: # Only set text if not using image
                #    self.expand_button.config(text="▼")
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

    # Instruction 3: Helper methods for corner position
    def _calculate_corner_x(self) -> int:
        screen_width = self.winfo_screenwidth()
        padding = 10 # Distance from the edge
        return screen_width - self.wrapped_width - padding

    def _calculate_corner_y(self) -> int:
        screen_height = self.winfo_screenheight()
        # Approx taskbar height or general padding from bottom
        padding_from_bottom = 40
        return screen_height - self.wrapped_height - padding_from_bottom

    # Instruction 4: Placeholder for toggle_wrap_view
    def toggle_wrap_view(self, event=None): # Added event=None for click binding
        # Entry print
        print(f"DEBUG: toggle_wrap_view ENTRY: current self.is_wrapped={self.is_wrapped}, self.is_expanded={self.is_expanded}, event={event}")
        logger.info(f"toggle_wrap_view called. Current is_wrapped: {self.is_wrapped}. Event: {event}")

        self.is_wrapped = not self.is_wrapped

        if self.is_wrapped:
            # Wrapping
            print(f"DEBUG: WRAPPING branch: self.is_wrapped is now True.")
            logger.debug("Wrapping popup...")
            self.expanded_state_before_wrap = self.is_expanded
            print(f"DEBUG: WRAPPING: Stored self.expanded_state_before_wrap = {self.expanded_state_before_wrap}")

            if self.is_expanded:
                print(f"DEBUG: WRAPPING: Currently expanded, calling self.toggle_expand_popup() to collapse.")
                self.toggle_expand_popup() # Collapse description if open
                print(f"DEBUG: WRAPPING: After toggle_expand_popup, self.is_expanded = {self.is_expanded}")

            # self._cancel_nag_tts() # Instruction 4.f (cancelling on wrap)
            print(f"DEBUG: WRAPPING: Called _cancel_nag_tts().")

            # Hide normal content (button_frame_ref and desc_frame)
            print(f"DEBUG: WRAPPING: Attempting to pack_forget button_frame_ref, desc_frame.")
            if hasattr(self, 'button_frame_ref') and self.button_frame_ref.winfo_ismapped():
                 self.button_frame_ref.pack_forget()
            print(f"DEBUG: WRAPPING: button_frame_ref forgotten. Is mapped: {self.button_frame_ref.winfo_ismapped() if hasattr(self.button_frame_ref, 'winfo_exists') and self.button_frame_ref.winfo_exists() else 'N/A'}")

            if hasattr(self, 'desc_frame') and self.desc_frame.winfo_ismapped():
                 self.desc_frame.pack_forget()
            print(f"DEBUG: WRAPPING: desc_frame forgotten. Is mapped: {self.desc_frame.winfo_ismapped() if hasattr(self.desc_frame, 'winfo_exists') and self.desc_frame.winfo_exists() else 'N/A'}")

            # Modify layout within top_content_frame
            if hasattr(self, 'top_content_frame'):
                print(f"DEBUG: WRAPPING: Modifying layout within top_content_frame.")
                if hasattr(self, 'title_label') and self.title_label.winfo_ismapped():
                    self.title_label.pack_forget()
                print(f"DEBUG: WRAPPING: title_label forgotten. Is mapped: {self.title_label.winfo_ismapped() if hasattr(self.title_label, 'winfo_exists') and self.title_label.winfo_exists() else 'N/A'}")

                if hasattr(self, 'duration_display_frame'):
                    self.duration_display_frame.pack_forget() # Forget current packing
                    self.duration_display_frame.pack(in_=self.top_content_frame, anchor='center', expand=True, fill='both', padx=0, pady=0) # Centered, minimal padding
                    print(f"DEBUG: WRAPPING: duration_display_frame repacked in top_content_frame (centered). Parent: {self.duration_display_frame.winfo_parent() if hasattr(self.duration_display_frame, 'winfo_exists') and self.duration_display_frame.winfo_exists() else 'N/A'}")
                else:
                    print(f"DEBUG: WRAPPING: duration_display_frame not found.")

                # Ensure top_content_frame itself now fills main_frame to control overall size
                self.top_content_frame.pack_forget()
                self.top_content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)
                print(f"DEBUG: WRAPPING: top_content_frame repacked to fill main_frame.")
            else:
                print(f"DEBUG: WRAPPING: top_content_frame not found.")

            new_x = self._calculate_corner_x()
            new_y = self._calculate_corner_y()
            new_geometry = f"{self.wrapped_width}x{self.wrapped_height}+{new_x}+{new_y}"
            print(f"DEBUG: WRAPPING: Setting geometry to: {new_geometry}")
            self.geometry(new_geometry)

            print(f"DEBUG: WRAPPING: Unbinding drag events, binding unwrap click.")
            if hasattr(self, '_on_mouse_press_binding_id') and self._on_mouse_press_binding_id:
                self.unbind("<ButtonPress-1>", self._on_mouse_press_binding_id)
            if hasattr(self, '_on_mouse_release_binding_id') and self._on_mouse_release_binding_id:
                self.unbind("<ButtonRelease-1>", self._on_mouse_release_binding_id)
            if hasattr(self, '_on_mouse_drag_binding_id') and self._on_mouse_drag_binding_id:
                self.unbind("<B1-Motion>", self._on_mouse_drag_binding_id)

            self._unwrap_binding_id = self.bind("<ButtonPress-1>", self.toggle_wrap_view)
            if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_exists():
                 self.duration_display_frame.bind("<ButtonPress-1>", self.toggle_wrap_view)
            if hasattr(self, 'countdown_label') and self.countdown_label and self.countdown_label.winfo_exists():
                 self.countdown_label.bind("<ButtonPress-1>", self.toggle_wrap_view)
            if hasattr(self, 'no_duration_label') and self.no_duration_label and self.no_duration_label.winfo_exists():
                 self.no_duration_label.bind("<ButtonPress-1>", self.toggle_wrap_view)
            print(f"DEBUG: WRAPPING: Unwrap click bound with ID: {self._unwrap_binding_id}")

            if hasattr(self, 'wrap_button'):
                # if not self.img_wrap: # Only set text if not using image
                #    self.wrap_button.config(text="↗️") # Change icon to "unwrap"
                ToolTip(self.wrap_button, text="Restore Full View")
            print(f"DEBUG: WRAPPING: Wrap button updated.")


        else:
            # Unwrapping
            print(f"DEBUG: UNWRAPPING branch: self.is_wrapped is now False.")
            logger.debug("Unwrapping popup...")

            print(f"DEBUG: UNWRAPPING: Unbinding unwrap click events. Current _unwrap_binding_id: {self._unwrap_binding_id}")
            if self._unwrap_binding_id:
                self.unbind("<ButtonPress-1>", self._unwrap_binding_id)
                if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_exists():
                     self.duration_display_frame.unbind("<ButtonPress-1>")
                if hasattr(self, 'countdown_label') and self.countdown_label and self.countdown_label.winfo_exists():
                     self.countdown_label.unbind("<ButtonPress-1>")
                if hasattr(self, 'no_duration_label') and self.no_duration_label and self.no_duration_label.winfo_exists():
                     self.no_duration_label.unbind("<ButtonPress-1>")
                self._unwrap_binding_id = None
            print(f"DEBUG: UNWRAPPING: Unwrap click events unbound. _unwrap_binding_id is now {self._unwrap_binding_id}")

            print(f"DEBUG: UNWRAPPING: Re-binding drag events.")
            self._on_mouse_press_binding_id = self.bind("<ButtonPress-1>", self._on_mouse_press)
            self._on_mouse_release_binding_id = self.bind("<ButtonRelease-1>", self._on_mouse_release)
            self._on_mouse_drag_binding_id = self.bind("<B1-Motion>", self._on_mouse_drag)

            # Restore layout within top_content_frame
            if hasattr(self, 'top_content_frame'):
                print(f"DEBUG: UNWRAPPING: Restoring layout within top_content_frame.")
                if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_ismapped(): # It should be mapped within top_content_frame
                    self.duration_display_frame.pack_forget()
                print(f"DEBUG: UNWRAPPING: duration_display_frame forgotten from top_content_frame.")

                if hasattr(self, 'title_label'): # Add this check for robustness
                    self.title_label.pack(in_=self.top_content_frame, side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
                    print(f"DEBUG: UNWRAPPING: title_label repacked into top_content_frame. Is mapped: {self.title_label.winfo_ismapped()}") # Debug print

                if hasattr(self, 'duration_display_frame'):
                    self.duration_display_frame.pack(in_=self.top_content_frame, side=tk.RIGHT, fill=tk.NONE, expand=False, padx=(5,0)) # Original packing for duration_display_frame
                print(f"DEBUG: UNWRAPPING: duration_display_frame repacked into top_content_frame (original). Parent: {self.duration_display_frame.winfo_parent() if hasattr(self.duration_display_frame, 'winfo_exists') and self.duration_display_frame.winfo_exists() else 'N/A'}")

                # Restore top_content_frame's own packing in main_frame
                self.top_content_frame.pack_forget() # Ensure it's removed from fill=BOTH if it was set
                self.top_content_frame.pack(side=tk.TOP, fill=tk.X, pady=(0,2), anchor='n') # Original packing for top_content_frame in main_frame
                print(f"DEBUG: UNWRAPPING: top_content_frame's own packing restored in main_frame.")
            else:
                print(f"DEBUG: UNWRAPPING: top_content_frame not found.")

            # Re-pack button_frame_ref (desc_frame is handled by toggle_expand_popup)
            if hasattr(self, 'button_frame_ref'):
                 self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(3,2), ipady=2) # Original packing
            print(f"DEBUG: UNWRAPPING: button_frame_ref repacked. Is mapped: {self.button_frame_ref.winfo_ismapped() if hasattr(self.button_frame_ref, 'winfo_exists') and self.button_frame_ref.winfo_exists() else 'N/A'}")

            restored_geometry = f"{self.width}x{self.initial_height}"
            print(f"DEBUG: UNWRAPPING: Setting geometry to: {restored_geometry}")
            self.geometry(restored_geometry)

            print(f"DEBUG: UNWRAPPING: self.expanded_state_before_wrap = {self.expanded_state_before_wrap}")
            if self.expanded_state_before_wrap:
                print(f"DEBUG: UNWRAPPING: Calling self.toggle_expand_popup() to re-expand description.")
                self.toggle_expand_popup() # This will handle geometry for expanded state.
                print(f"DEBUG: UNWRAPPING: After toggle_expand_popup, self.is_expanded = {self.is_expanded}")

            if hasattr(self, 'wrap_button'):
                # if not self.img_wrap: # Only set text if not using image
                #    self.wrap_button.config(text="↘️") # Change icon back to "wrap"
                ToolTip(self.wrap_button, text="Minimize to Corner")
            print(f"DEBUG: UNWRAPPING: Wrap button updated.")

        logger.debug(f"toggle_wrap_view finished. is_wrapped: {self.is_wrapped}")
        print(f"DEBUG: toggle_wrap_view EXIT: self.is_wrapped={self.is_wrapped}, current geometry={self.geometry()}")

    def start_countdown_action(self):
        logger.debug(f"POPUP_ACTION: 'start_countdown_action' called for task ID: {self.task.id if self.task else 'N/A'}.")

        # Call placeholder for cancelling nag TTS (to be implemented in next step)
        self._cancel_nag_tts() # Instruction 4.a

        if self.remaining_work_seconds > 0:
            self._update_countdown()

        if hasattr(self, 'start_button'):
            self.start_button.config(state=tk.DISABLED)
            ToolTip(self.start_button, text="Timer Started") # Update tooltip

        # Potentially hide other buttons or change their state if needed
        # For example, maybe disable reschedule/skip once started? For now, just disable Start.

    def _schedule_nag_tts(self): # Instruction 2
        if not self.winfo_exists(): # Don't reschedule if window is destroyed
            return

        nag_interval_ms = 20000  # 20 seconds
        task_title = self.task.title if self.task and self.task.title else "untitled task"
        tts_message = f"Sir, time for task {task_title}, please start work."

        logger.debug(f"POPUP_NAG: Scheduling TTS nag in {nag_interval_ms}ms: '{tts_message}'")

        # Ensure any previous nag is cancelled before scheduling a new one
        if self.nag_tts_after_id:
            self.after_cancel(self.nag_tts_after_id)
            self.nag_tts_after_id = None

        self.nag_tts_after_id = self.after(nag_interval_ms, lambda: [
            tts_manager.speak(tts_message),
            self._schedule_nag_tts() # Reschedule itself
        ])

    def _cancel_nag_tts(self): # Instruction 3
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
