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
        self.is_wrapped = False
        self.wrapped_width = 110 # User changed
        self.wrapped_height = 40
        self.expanded_state_before_wrap = False
        self._unwrap_binding_id = None
        self.nag_tts_after_id = None

        self.width = 380
        self.initial_height = 85
        self.expanded_height = 215

        self.anim_target_x = 1530
        self.anim_target_y = 200
        # For horizontal slide from right:
        # We'll calculate the actual starting X in _animate_slide_in based on screen width.
        # These offsets will now primarily be used for the wrap/unwrap animation targets if needed,
        # or can be re-purposed. For main slide-out, it will slide out to width of screen.
        # Let's keep anim_start_x_offset for now, it might be useful for wrap, or as a general magnitude.
        self.anim_start_x_offset = self.width # Start fully off-screen to the right relative to its own width
        self.anim_start_y_offset = 0         # No vertical offset for main slide

        self.anim_total_steps = 20
        self.anim_current_step = 0
        self.anim_delay_ms = 15    # e.g. 15ms for ~300ms total animation (20*15)
        self.animation_after_id = None
        self.use_fade_effect = False # New flag to disable fade

        # New parameters for wrap/unwrap animation state
        self.last_normal_geometry_before_wrap = "" # Stores "widthxheight+x+y" string
        self.is_animating_wrap_unwrap = False # New animation guard flag


        self.remaining_work_seconds = 0
        if self.task and self.task.duration and self.task.duration > 0:
            self.remaining_work_seconds = self.task.duration * 60

        # self.geometry(f"{self.width}x{self.initial_height}+1530+200") # Replaced by initial off-screen and animation
        self.wm_attributes("-topmost", 1)
        self.resizable(False, False)

        self._on_mouse_press_binding_id = self.bind("<ButtonPress-1>", self._on_mouse_press)
        self._on_mouse_release_binding_id = self.bind("<ButtonRelease-1>", self._on_mouse_release)
        self._on_mouse_drag_binding_id = self.bind("<B1-Motion>", self._on_mouse_drag)

        self.countdown_label = None
        self.no_duration_label = None

        # In __init__, just before self._setup_ui()
        # Initial placement for slide-in from right:
        # Place it far right, actual start X will be screen width, set in _animate_slide_in
        # Y is target Y. Set alpha to 0 if fade is used, otherwise it will be set to 1 in animation.
        # For now, to prevent flashing, place it at an estimated off-screen X based on screenwidth if possible,
        # or a very large X. Or, simply withdraw it and let _animate_slide_in handle deiconify and first geometry.
        # Let's use withdraw() for clean start, then deiconify() in animation.
        self.withdraw() # Hide window initially
        if self.use_fade_effect: # This will be false based on current settings
            self.attributes("-alpha", 0.0)
        else:
            self.attributes("-alpha", 1.0) # Should be opaque if not fading

        # The self.geometry() call that sets the final position (e.g., +1530+200)
        # should remain commented out or removed from earlier in __init__, as animation handles it.

        self._setup_ui()

        logger.info(f"ReminderPopupUI created for task ID: {self.task.id if self.task else 'N/A'}")
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

        self._schedule_nag_tts()

        self.anim_current_step = 0 # Ensure it starts from step 0
        self._animate_slide_in()

    def _animate_slide_in(self):
        if self.animation_after_id: # Cancel any pending animation frame
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None

        # Calculate actual starting X position (from the right edge of the screen)
        # This is done on the first step of this animation instance.
        if self.anim_current_step == 0:
            self.actual_anim_start_x = self.winfo_screenwidth()
            # Ensure window is deiconified and alpha is set if not using fade
            self.deiconify()
            if not self.use_fade_effect:
                self.attributes("-alpha", 1.0) # Make fully opaque if no fade
            else: # Still start transparent if fade was to be used (though flag is false now)
                 self.attributes("-alpha", 0.0)


        if self.anim_current_step <= self.anim_total_steps:
            progress = (self.anim_current_step / self.anim_total_steps) # Linear progress

            # Interpolate X position linearly
            # Moves from self.actual_anim_start_x (screenwidth) to self.anim_target_x
            current_x = int(self.actual_anim_start_x - ( (self.actual_anim_start_x - self.anim_target_x) * progress) )
            current_y = self.anim_target_y # Y position is constant

            self.geometry(f"{self.width}x{self.initial_height}+{current_x}+{current_y}")

            if self.use_fade_effect: # This block will be skipped if use_fade_effect is False
                current_alpha = progress
                self.attributes("-alpha", current_alpha)

            self.anim_current_step += 1
            self.animation_after_id = self.after(self.anim_delay_ms, self._animate_slide_in)
        else:
            # Ensure final position and opacity
            self.geometry(f"{self.width}x{self.initial_height}+{self.anim_target_x}+{self.anim_target_y}")
            if not self.use_fade_effect:
                self.attributes("-alpha", 1.0) # Ensure fully opaque
            else: # If somehow fade was on, ensure it ends at 1.0
                self.attributes("-alpha", 1.0)

            self.anim_current_step = 0 # Reset for potential future use
            logger.info("Linear slide-in animation complete.")
            if self.state() == 'withdrawn': # Should not be withdrawn if deiconify worked.
                 self.deiconify()

    def _animate_slide_out(self):
        if self.animation_after_id: # Cancel any pending animation frame
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None

        # Calculate target off-screen X position (the right edge of the screen)
        # This is done on the first step of this animation instance.
        if self.anim_current_step == 0:
            self.actual_anim_end_x = self.winfo_screenwidth()
            # Ensure current on-screen X is captured if needed, though target_x should be current
            # self.current_on_screen_x_at_slideout_start = self.winfo_x() # Not strictly needed


        if self.anim_current_step <= self.anim_total_steps:
            progress = (self.anim_current_step / self.anim_total_steps) # Linear progress

            # Interpolate X position linearly
            # Moves from self.anim_target_x to self.actual_anim_end_x (screenwidth)
            current_x = int(self.anim_target_x + ( (self.actual_anim_end_x - self.anim_target_x) * progress) )
            current_y = self.anim_target_y # Y position is constant

            self.geometry(f"{self.width}x{self.initial_height}+{current_x}+{current_y}")

            if self.use_fade_effect: # This block will be skipped if use_fade_effect is False
                # For fade-out, alpha progress is reversed
                alpha_val = 1.0 - progress
                self.attributes("-alpha", max(0.0, alpha_val)) # Ensure alpha doesn't go below 0
            # If not using fade effect, alpha remains 1.0 until it's gone or destroyed.

            self.anim_current_step += 1
            self.animation_after_id = self.after(self.anim_delay_ms, self._animate_slide_out)
        else:
            # Animation finished, now destroy the window
            logger.info("Linear slide-out animation complete. Destroying window.")
            # Optionally hide it completely before destroy if there's any flicker
            self.withdraw()
            if hasattr(self, 'destroy'):
                 self.destroy()

    def _animate_wrap(self, on_complete=None):
        if self.animation_after_id:
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None

        try:
            parts = self.last_normal_geometry_before_wrap.split('x')
            start_w = int(parts[0])
            parts = parts[1].split('+')
            start_h = int(parts[0])
            start_x = int(parts[1])
            start_y = int(parts[2])
        except Exception as e:
            logger.error(f"Could not parse last_normal_geometry_before_wrap: '{self.last_normal_geometry_before_wrap}'. Error: {e}. Halting wrap animation.")
            self.geometry(f"{self.wrapped_width}x{self.wrapped_height}+{self._calculate_corner_x()}+{self._calculate_corner_y()}")
            if on_complete:
                on_complete()
            return

        target_w = self.wrapped_width
        target_h = self.wrapped_height
        target_x = self._calculate_corner_x()
        target_y = self._calculate_corner_y()

        if self.anim_current_step <= self.anim_total_steps:
            progress = self.anim_current_step / self.anim_total_steps

            current_w = int(start_w - (start_w - target_w) * progress)
            current_h = int(start_h - (start_h - target_h) * progress)
            current_x = int(start_x - (start_x - target_x) * progress)
            current_y = int(start_y - (start_y - target_y) * progress)

            self.geometry(f"{current_w}x{current_h}+{current_x}+{current_y}")

            self.anim_current_step += 1
            self.animation_after_id = self.after(self.anim_delay_ms, lambda: self._animate_wrap(on_complete))
        else:
            self.geometry(f"{target_w}x{target_h}+{target_x}+{target_y}")
            self.anim_current_step = 0
            logger.info("Wrap animation complete.")
            if on_complete:
                on_complete()

    def _animate_unwrap(self, on_complete=None):
        if self.animation_after_id:
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None

        start_w = self.wrapped_width
        start_h = self.wrapped_height
        start_x = self._calculate_corner_x()
        start_y = self._calculate_corner_y()

        try:
            parts = self.last_normal_geometry_before_wrap.split('x')
            target_w = int(parts[0])
            parts = parts[1].split('+')
            target_h = int(parts[0])
            target_x = int(parts[1])
            target_y = int(parts[2])
        except Exception as e:
            logger.error(f"Could not parse last_normal_geometry_before_wrap: '{self.last_normal_geometry_before_wrap}'. Error: {e}. Halting unwrap animation.")
            if hasattr(self, 'width') and hasattr(self, 'initial_height') and hasattr(self, 'anim_target_x') and hasattr(self, 'anim_target_y'):
                 self.geometry(f"{self.width}x{self.initial_height}+{self.anim_target_x}+{self.anim_target_y}")
            if on_complete:
                on_complete()
            return

        if self.anim_current_step <= self.anim_total_steps:
            progress = self.anim_current_step / self.anim_total_steps

            current_w = int(start_w + (target_w - start_w) * progress)
            current_h = int(start_h + (target_h - start_h) * progress)
            current_x = int(start_x + (target_x - start_x) * progress)
            current_y = int(start_y + (target_y - start_y) * progress)

            self.geometry(f"{current_w}x{current_h}+{current_x}+{current_y}")

            self.anim_current_step += 1
            self.animation_after_id = self.after(self.anim_delay_ms, lambda: self._animate_unwrap(on_complete))
        else:
            self.geometry(self.last_normal_geometry_before_wrap)
            self.anim_current_step = 0
            logger.info("Unwrap animation complete.")
            if on_complete:
                on_complete()

    def _setup_wrap_bindings_and_ui(self):
        logger.debug("Wrap animation complete. Setting up wrap bindings and UI.")

        if hasattr(self, '_on_mouse_press_binding_id'):
            if self._on_mouse_press_binding_id:
                self.unbind("<ButtonPress-1>", self._on_mouse_press_binding_id)
        # Fallback unbind (more robust)
        self.unbind("<ButtonPress-1>")

        if hasattr(self, '_on_mouse_release_binding_id'):
            if self._on_mouse_release_binding_id:
                self.unbind("<ButtonRelease-1>", self._on_mouse_release_binding_id)
        self.unbind("<ButtonRelease-1>")

        if hasattr(self, '_on_mouse_drag_binding_id'):
            if self._on_mouse_drag_binding_id:
                self.unbind("<B1-Motion>", self._on_mouse_drag_binding_id)
        self.unbind("<B1-Motion>")
        logger.debug("Unbound general mouse drag/press events from Toplevel for wrapped state.")

        self._unwrap_binding_id = self.bind("<ButtonPress-1>", self.toggle_wrap_view)

        if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_exists():
            self.duration_display_frame.bind("<ButtonPress-1>", self.toggle_wrap_view)
        if hasattr(self, 'countdown_label') and self.countdown_label and self.countdown_label.winfo_exists():
            self.countdown_label.bind("<ButtonPress-1>", self.toggle_wrap_view)
        if hasattr(self, 'no_duration_label') and self.no_duration_label and self.no_duration_label.winfo_exists():
            self.no_duration_label.bind("<ButtonPress-1>", self.toggle_wrap_view)

        if hasattr(self, 'wrap_button'):
            self.wrap_button.config(text="↗️")
            ToolTip(self.wrap_button, text="Restore Full View")

        self.is_animating_wrap_unwrap = False # Reset flag after all setup is done
        logger.debug("Wrap setup complete, animation guard released.")

    def _setup_unwrap_bindings_and_ui(self):
        logger.debug("Unwrap animation complete. Setting up unwrap bindings and UI.")

        if hasattr(self, '_unwrap_binding_id') and self._unwrap_binding_id:
            self.unbind("<ButtonPress-1>", self._unwrap_binding_id)
        # Fallback unbind
        self.unbind("<ButtonPress-1>")
        logger.debug("Unbound <ButtonPress-1> (for unwrap click) from Toplevel.")
        self._unwrap_binding_id = None

        if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_exists():
            self.duration_display_frame.unbind("<ButtonPress-1>")
        if hasattr(self, 'countdown_label') and self.countdown_label and self.countdown_label.winfo_exists():
            self.countdown_label.unbind("<ButtonPress-1>")
        if hasattr(self, 'no_duration_label') and self.no_duration_label and self.no_duration_label.winfo_exists():
            self.no_duration_label.unbind("<ButtonPress-1>")

        self._on_mouse_press_binding_id = self.bind("<ButtonPress-1>", self._on_mouse_press)
        self._on_mouse_release_binding_id = self.bind("<ButtonRelease-1>", self._on_mouse_release)
        self._on_mouse_drag_binding_id = self.bind("<B1-Motion>", self._on_mouse_drag)
        logger.debug("Re-bound mouse drag events to Toplevel for normal state.")

        if hasattr(self, 'top_content_frame'):
            if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_ismapped():
                self.duration_display_frame.pack_forget()

            if hasattr(self, 'complete_button'):
                self.complete_button.pack(side=tk.LEFT, padx=(3, 3))

            if hasattr(self, 'title_label') and hasattr(self.title_label, 'master') and self.title_label.master != self.top_content_frame :
                clipper = self.title_label.master
                clipper.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
            elif hasattr(self, 'title_label'):
                self.title_label.pack(in_=self.top_content_frame, side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))

            if hasattr(self, 'duration_display_frame'):
                self.duration_display_frame.pack(in_=self.top_content_frame, side=tk.RIGHT, fill=tk.NONE, expand=False, padx=(5,0))

        if hasattr(self, 'button_frame_ref'):
             self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(3,2), ipady=2)

        if hasattr(self, 'wrap_button'):
            self.wrap_button.config(text="💊")
            ToolTip(self.wrap_button, text="Minimize to Corner")

        if self.expanded_state_before_wrap:
            self.is_expanded = False
            self.toggle_expand_popup()

        self.is_animating_wrap_unwrap = False # Reset flag after all setup is done
        logger.debug("Unwrap setup complete, animation guard released.")

    def _on_complete_button_enter(self, event):
        if hasattr(self, 'complete_button') and self.complete_button.winfo_exists():
            try:
                self.complete_button.config(text="✔️")
            except tk.TclError as e:
                logger.error(f"Error applying hover text to complete_button: {e}")

    def _on_complete_button_leave(self, event):
        if hasattr(self, 'complete_button') and self.complete_button.winfo_exists():
            try:
                self.complete_button.config(text="")
            except tk.TclError as e:
                logger.error(f"Error reverting hover text for complete_button: {e}")

    def _setup_ui(self):
        self.countdown_label = None
        self.no_duration_label = None

        self.main_frame = bs.Frame(self, padding=(5,2,5,2))
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        self.top_content_frame = bs.Frame(self.main_frame)
        self.top_content_frame.pack(side=tk.TOP, fill=tk.X, pady=(0,2), anchor='n')

        self.complete_button = bs.Button(self.top_content_frame,
                                         text="",
                                         command=self.complete_task,
                                         bootstyle="light-outline-round",
                                         width=2,
                                         padding=(2, 2))
        self.complete_button.pack(side=tk.LEFT, padx=(3, 3))
        ToolTip(self.complete_button, text="Mark as Complete")
        self.complete_button.bind("<Enter>", self._on_complete_button_enter)
        self.complete_button.bind("<Leave>", self._on_complete_button_leave)

        title_text_clipper_frame = bs.Frame(self.top_content_frame)
        title_font = ("Helvetica", 12, "bold")

        try:
            import tkinter.font
            font_obj = tkinter.font.Font(font=title_font)
            linespace = font_obj.metrics('linespace')
            clipper_height = linespace + 2
        except Exception:
            clipper_height = 26
            logger.warning("Could not get precise font metrics for title, using estimated clipper height.")

        title_text_clipper_frame.configure(height=clipper_height)
        title_text_clipper_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        title_text_clipper_frame.pack_propagate(False)

        effective_wraplength = self.width - 140

        self.title_label = bs.Label(title_text_clipper_frame,
                               text=(self.task.title if self.task and self.task.title else "No Title"),
                               font=title_font,
                               wraplength=effective_wraplength,
                               anchor="nw",
                               justify=tk.LEFT)
        self.title_label.pack(side=tk.LEFT, padx=0, pady=0, fill=tk.X, expand=True)

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
                                            font=("courier new", 14, "bold"), style="info.TLabel, inverse")
            self.countdown_label.pack(side=tk.LEFT)
        else:
            self.no_duration_label = bs.Label(self.duration_display_frame, text="No specific work duration.", style="secondary.TLabel")
            self.no_duration_label.pack(side=tk.LEFT)

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
        self.description_text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.button_frame_ref = bs.Frame(self.main_frame)
        self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(3,2), ipady=2)

        self.expand_button = bs.Button(self.button_frame_ref,
                                   text="🔽",
                                   command=self.toggle_expand_popup,
                                   bootstyle="light-outline-round")
        self.expand_button.pack(side=tk.LEFT, padx=2)
        ToolTip(self.expand_button, text="More Info")

        self.wrap_button = bs.Button(self.button_frame_ref, text="💊",
                                       command=self.toggle_wrap_view,
                                       bootstyle="light-outline-round")
        self.wrap_button.pack(side=tk.LEFT, padx=2)
        ToolTip(self.wrap_button, text="Minimize to Corner")

        self.start_button = bs.Button(self.button_frame_ref, text="Start",
                                       command=self.start_countdown_action,
                                       bootstyle="light-outline-round")
        self.start_button.pack(side=tk.LEFT, padx=2)
        ToolTip(self.start_button, text="Start Work Session Timer")

        self.skip_button = bs.Button(self.button_frame_ref,
                                   text="⏩",
                                   command=self.skip_reminder,
                                   bootstyle="secondary")
        self.skip_button.pack(side=tk.RIGHT, padx=(2,0))
        ToolTip(self.skip_button, text="Skip Reminder")

        self.reschedule_button = bs.Button(self.button_frame_ref,
                                       text="🔄",
                                       command=self.reschedule_task,
                                       bootstyle="secondary")
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
        if self.app_callbacks and 'reschedule' in self.app_callbacks:
            try:
                self.app_callbacks['reschedule'](self.task.id if self.task else None, 15)
            except Exception as e:
                logger.error(f"Popup: Error calling reschedule callback for task ID {task_id_info}: {e}", exc_info=True)
        else:
            logger.warning(f"Popup: 'reschedule' callback not found or app_callbacks not set for task ID: {task_id_info}")
        self._cleanup_and_destroy()

    def complete_task(self):
        self._cancel_nag_tts()
        task_id_info = self.task.id if self.task else "N/A"
        if self.app_callbacks and 'complete' in self.app_callbacks:
            try:
                self.app_callbacks['complete'](self.task.id if self.task else None)
            except Exception as e:
                logger.error(f"Popup: Error calling complete callback for task ID {task_id_info}: {e}", exc_info=True)
        else:
            logger.warning(f"Popup: 'complete' callback not found or app_callbacks not set for task ID: {task_id_info}")
        self._cleanup_and_destroy()

    def skip_reminder(self):
        self._cancel_nag_tts()
        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        task_id_info = self.task.id if self.task else "N/A"
        logger.debug(f"POPUP_CLEANUP: Initiating cleanup for task ID {task_id_info}")

        if hasattr(self, 'after_id') and self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
            logger.debug(f"POPUP_CLEANUP: Work countdown timer cancelled for task ID {task_id_info}.")

        self._cancel_nag_tts()

        if hasattr(self, 'animation_after_id') and self.animation_after_id:
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None
            logger.debug(f"POPUP_CLEANUP: Ongoing animation cancelled for task ID {task_id_info}.")

        if hasattr(self, 'app_callbacks') and self.app_callbacks and 'remove_from_active' in self.app_callbacks:
            try:
                logger.debug(f"POPUP_CLEANUP: Attempting 'remove_from_active' callback for task ID: {task_id_info}.")
                self.app_callbacks['remove_from_active'](self.task.id if self.task else None)
                logger.debug(f"POPUP_CLEANUP: 'remove_from_active' callback attempted for task ID: {task_id_info}.")
            except Exception as e:
                logger.error(f"Popup: Error calling remove_from_active callback: {e}", exc_info=True)

        logger.debug(f"POPUP_CLEANUP: Starting slide-out animation for task ID: {task_id_info}.")
        self.anim_current_step = 0

        if hasattr(self, '_animate_slide_out'):
            self._animate_slide_out()
        else:
            logger.warning("POPUP_CLEANUP: _animate_slide_out method not found. Destroying window directly.")
            if hasattr(self, 'destroy'):
                 self.destroy()

    def toggle_expand_popup(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            if hasattr(self, 'desc_frame') and hasattr(self, 'button_frame_ref'):
                 self.button_frame_ref.pack_forget()
                 self.desc_frame.pack(fill=tk.BOTH, expand=True, pady=(3,3))
                 self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(5,0), ipady=5)
            self.geometry(f"{self.width}x{self.expanded_height}")
            if hasattr(self, 'expand_button'):
                self.expand_button.config(text="🔼")
                ToolTip(self.expand_button, text="Less Info")
        else:
            if hasattr(self, 'desc_frame'):
                self.desc_frame.pack_forget()
            self.geometry(f"{self.width}x{self.initial_height}")
            if hasattr(self, 'expand_button'):
                self.expand_button.config(text="🔽")
                ToolTip(self.expand_button, text="More Info")

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
        if self.is_animating_wrap_unwrap:
            logger.debug("Wrap/unwrap animation already in progress. Ignoring toggle request.")
            return
        self.is_animating_wrap_unwrap = True # Set flag

        logger.info(f"toggle_wrap_view called. Current is_wrapped: {self.is_wrapped}. Event: {event}")
        # Prevent re-triggering if animation is already in progress (optional, good practice)
        # if self.anim_current_step > 0 and self.anim_current_step <= self.anim_total_steps:
        #     logger.debug("Animation already in progress, ignoring toggle request.")
        #     return

        self.is_wrapped = not self.is_wrapped

        if self.is_wrapped: # Start wrapping process
            logger.debug("Wrapping popup...")
            # Store current geometry (full string: "widthxheight+x+y")
            self.last_normal_geometry_before_wrap = self.geometry()
            self.expanded_state_before_wrap = self.is_expanded # Store expanded state

            if self.is_expanded:
                self.toggle_expand_popup() # Collapse description if open, before animation

            # Hide normal content (elements that are part of the full view)
            if hasattr(self, 'button_frame_ref') and self.button_frame_ref.winfo_ismapped():
                 self.button_frame_ref.pack_forget()
            if hasattr(self, 'desc_frame') and self.desc_frame.winfo_ismapped(): # Though desc_frame is usually handled by toggle_expand
                 self.desc_frame.pack_forget()

            # Modify layout within top_content_frame for wrapped view
            if hasattr(self, 'top_content_frame'):
                if hasattr(self, 'complete_button') and self.complete_button.winfo_ismapped():
                    self.complete_button.pack_forget()
                if hasattr(self, 'title_label') and hasattr(self.title_label, 'master') and self.title_label.master.winfo_ismapped(): # title_label.master is the clipper
                    self.title_label.master.pack_forget() # Forget the clipper frame

                if hasattr(self, 'duration_display_frame'): # Center duration display
                    self.duration_display_frame.pack_forget()
                    self.duration_display_frame.pack(in_=self.top_content_frame, anchor='center', expand=True, fill='both', padx=0, pady=0)

            # Start animation
            self.anim_current_step = 0
            self._animate_wrap(on_complete=self._setup_wrap_bindings_and_ui)

        else: # Start unwrapping process
            logger.debug("Unwrapping popup...")
            # UI elements (complete_button, title_clipper, duration_display_frame in normal layout, button_frame_ref)
            # will be re-packed by _setup_unwrap_bindings_and_ui after animation.
            # For now, ensure top_content_frame is ready for its children to be repacked correctly.
            # If duration_display_frame exists and is mapped, forget it to prepare for re-packing.
            if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_ismapped():
                 self.duration_display_frame.pack_forget()
                 logger.debug("Unwrap: duration_display_frame pack_forget done before animation.")

            self.anim_current_step = 0
            self._animate_unwrap(on_complete=self._setup_unwrap_bindings_and_ui)

        logger.debug(f"toggle_wrap_view finished initiating {'wrap' if self.is_wrapped else 'unwrap'} animation.")

    def start_countdown_action(self):
        logger.debug(f"POPUP_ACTION: 'start_countdown_action' called for task ID: {self.task.id if self.task else 'N/A'}.")
        self._cancel_nag_tts()
        if self.remaining_work_seconds > 0:
            self._update_countdown()
        if hasattr(self, 'start_button'):
            self.start_button.config(state=tk.DISABLED)
            ToolTip(self.start_button, text="Timer Started")

    def _schedule_nag_tts(self):
        if not self.winfo_exists():
            return
        nag_interval_ms = 20000
        task_title = self.task.title if self.task and self.task.title else "untitled task"
        tts_message = f"Sir, it's time for task {task_title}, please press start button." # User changed message
        logger.debug(f"POPUP_NAG: Scheduling TTS nag in {nag_interval_ms}ms: '{tts_message}'")
        if self.nag_tts_after_id:
            self.after_cancel(self.nag_tts_after_id)
            self.nag_tts_after_id = None
        self.nag_tts_after_id = self.after(nag_interval_ms, lambda: [
            tts_manager.speak(tts_message),
            self._schedule_nag_tts()
        ])

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
        root = bs.Window(themename="darkly") # User changed theme
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
```
