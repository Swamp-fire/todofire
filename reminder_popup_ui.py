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
        self.wrapped_width = 100
        self.wrapped_height = 40
        self.expanded_state_before_wrap = False
        self._unwrap_binding_id = None
        self.nag_tts_after_id = None

        self.width = 380
        self.initial_height = 85
        self.expanded_height = 215

        self.anim_target_x = 1530
        self.anim_target_y = 200
        self.anim_start_x_offset = self.width
        self.anim_start_y_offset = 0

        self.anim_total_steps = 20
        self.anim_current_step = 0
        self.anim_delay_ms = 15
        self.animation_after_id = None
        self.use_fade_effect = False

        self.last_normal_geometry_before_wrap = ""

        self.remaining_work_seconds = 0
        if self.task and self.task.duration and self.task.duration > 0:
            self.remaining_work_seconds = self.task.duration * 60

        self.wm_attributes("-topmost", 1)
        self.resizable(False, False)

        self._on_mouse_press_binding_id = self.bind("<ButtonPress-1>", self._on_mouse_press)
        self._on_mouse_release_binding_id = self.bind("<ButtonRelease-1>", self._on_mouse_release)
        self._on_mouse_drag_binding_id = self.bind("<B1-Motion>", self._on_mouse_drag)

        self.countdown_label = None
        self.no_duration_label = None

        self.withdraw()
        if self.use_fade_effect:
            self.attributes("-alpha", 0.0)
        else:
            self.attributes("-alpha", 1.0)

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

        self.anim_current_step = 0
        self._animate_slide_in()

    def _animate_slide_in(self):
        if self.animation_after_id:
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None

        if self.anim_current_step == 0:
            self.actual_anim_start_x = self.winfo_screenwidth()
            self.deiconify()
            if not self.use_fade_effect:
                self.attributes("-alpha", 1.0)
            else:
                 self.attributes("-alpha", 0.0)

        if self.anim_current_step <= self.anim_total_steps:
            progress = (self.anim_current_step / self.anim_total_steps)

            current_x = int(self.actual_anim_start_x - ( (self.actual_anim_start_x - self.anim_target_x) * progress) )
            current_y = self.anim_target_y

            self.geometry(f"{self.width}x{self.initial_height}+{current_x}+{current_y}")

            if self.use_fade_effect:
                current_alpha = progress
                self.attributes("-alpha", current_alpha)

            self.anim_current_step += 1
            self.animation_after_id = self.after(self.anim_delay_ms, self._animate_slide_in)
        else:
            self.geometry(f"{self.width}x{self.initial_height}+{self.anim_target_x}+{self.anim_target_y}")
            if not self.use_fade_effect:
                self.attributes("-alpha", 1.0)
            else:
                self.attributes("-alpha", 1.0)

            self.anim_current_step = 0
            logger.info("Linear slide-in animation complete.")
            if self.state() == 'withdrawn':
                 self.deiconify()

    def _animate_slide_out(self):
        if self.animation_after_id:
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None

        if self.anim_current_step == 0:
            self.actual_anim_end_x = self.winfo_screenwidth()
            self.current_on_screen_x_at_slideout_start = self.winfo_x()

        if self.anim_current_step <= self.anim_total_steps:
            progress = (self.anim_current_step / self.anim_total_steps)

            current_x = int(self.anim_target_x + ( (self.actual_anim_end_x - self.anim_target_x) * progress) )
            current_y = self.anim_target_y

            self.geometry(f"{self.width}x{self.initial_height}+{current_x}+{current_y}")

            if self.use_fade_effect:
                alpha_val = 1.0 - progress
                self.attributes("-alpha", max(0.0, alpha_val))

            self.anim_current_step += 1
            self.animation_after_id = self.after(self.anim_delay_ms, self._animate_slide_out)
        else:
            logger.info("Linear slide-out animation complete. Destroying window.")
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

        if hasattr(self, 'wrap_button'):
            self.wrap_button.config(text="↗️")
            ToolTip(self.wrap_button, text="Restore Full View")

    def _setup_unwrap_bindings_and_ui(self):
        logger.debug("Unwrap animation complete. Setting up unwrap bindings and UI.")
        if self._unwrap_binding_id:
            self.unbind("<ButtonPress-1>", self._unwrap_binding_id)
            if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_exists():
                 self.duration_display_frame.unbind("<ButtonPress-1>")
            if hasattr(self, 'countdown_label') and self.countdown_label and self.countdown_label.winfo_exists():
                 self.countdown_label.unbind("<ButtonPress-1>")
            if hasattr(self, 'no_duration_label') and self.no_duration_label and self.no_duration_label.winfo_exists():
                 self.no_duration_label.unbind("<ButtonPress-1>")
            self._unwrap_binding_id = None

        self._on_mouse_press_binding_id = self.bind("<ButtonPress-1>", self._on_mouse_press)
        self._on_mouse_release_binding_id = self.bind("<ButtonRelease-1>", self._on_mouse_release)
        self._on_mouse_drag_binding_id = self.bind("<B1-Motion>", self._on_mouse_drag)

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
            # If duration_display_frame was centered, forget it.
            if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_ismapped():
                 # Check if it's centered (its parent is top_content_frame and it's filling)
                 # This check is a bit heuristic. A more robust way is to store its original pack_info.
                 if self.duration_display_frame.cget('anchor') == 'center':
                      self.duration_display_frame.pack_forget()

            self.anim_current_step = 0
            self._animate_unwrap(on_complete=self._setup_unwrap_bindings_and_ui)

        logger.debug(f"toggle_wrap_view finished initiating {'wrap' if self.is_wrapped else 'unwrap'} animation.")
=======
    def toggle_wrap_view(self, event=None):
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
            # If duration_display_frame was centered, forget it.
            if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_ismapped():
                 # Check if it's centered (its parent is top_content_frame and it's filling)
                 # This check is a bit heuristic. A more robust way is to store its original pack_info.
                 if self.duration_display_frame.cget('anchor') == 'center':
                      self.duration_display_frame.pack_forget()

            self.anim_current_step = 0
            self._animate_unwrap(on_complete=self._setup_unwrap_bindings_and_ui)

        logger.debug(f"toggle_wrap_view finished initiating {'wrap' if self.is_wrapped else 'unwrap'} animation.")
>>>>>>> REPLACE
patch
--- a/reminder_popup_ui.py
+++ b/reminder_popup_ui.py
@@ -358,92 +358,42 @@
         padding_from_bottom = 40
         return screen_height - self.wrapped_height - padding_from_bottom

-    def toggle_wrap_view(self, event=None):
-        print(f"DEBUG: toggle_wrap_view ENTRY: current self.is_wrapped={self.is_wrapped}, self.is_expanded={self.is_expanded}, event={event}")
+    def toggle_wrap_view(self, event=None):
         logger.info(f"toggle_wrap_view called. Current is_wrapped: {self.is_wrapped}. Event: {event}")
+        # Prevent re-triggering if animation is already in progress (optional, good practice)
+        # if self.anim_current_step > 0 and self.anim_current_step <= self.anim_total_steps:
+        #     logger.debug("Animation already in progress, ignoring toggle request.")
+        #     return
+
         self.is_wrapped = not self.is_wrapped
-        if self.is_wrapped:
-            print(f"DEBUG: WRAPPING branch: self.is_wrapped is now True.")
+
+        if self.is_wrapped: # Start wrapping process
             logger.debug("Wrapping popup...")
+            # Store current geometry (full string: "widthxheight+x+y")
+            self.last_normal_geometry_before_wrap = self.geometry()
             self.expanded_state_before_wrap = self.is_expanded
-            print(f"DEBUG: WRAPPING: Stored self.expanded_state_before_wrap = {self.expanded_state_before_wrap}")
+
             if self.is_expanded:
-                print(f"DEBUG: WRAPPING: Currently expanded, calling self.toggle_expand_popup() to collapse.")
-                self.toggle_expand_popup()
-                print(f"DEBUG: WRAPPING: After toggle_expand_popup, self.is_expanded = {self.is_expanded}")
-            # self._cancel_nag_tts() # This was previously commented out to keep TTS nagging
-            print(f"DEBUG: WRAPPING: Called _cancel_nag_tts().")
-            print(f"DEBUG: WRAPPING: Attempting to pack_forget button_frame_ref, desc_frame.")
+                self.toggle_expand_popup() # Collapse description if open, before animation
+
+            # Hide normal content (elements that are part of the full view)
             if hasattr(self, 'button_frame_ref') and self.button_frame_ref.winfo_ismapped():
                  self.button_frame_ref.pack_forget()
-            print(f"DEBUG: WRAPPING: button_frame_ref forgotten. Is mapped: {self.button_frame_ref.winfo_ismapped() if hasattr(self.button_frame_ref, 'winfo_exists') and self.button_frame_ref.winfo_exists() else 'N/A'}")
-            if hasattr(self, 'desc_frame') and self.desc_frame.winfo_ismapped():
+            if hasattr(self, 'desc_frame') and self.desc_frame.winfo_ismapped(): # Though desc_frame is usually handled by toggle_expand
                  self.desc_frame.pack_forget()
-            print(f"DEBUG: WRAPPING: desc_frame forgotten. Is mapped: {self.desc_frame.winfo_ismapped() if hasattr(self.desc_frame, 'winfo_exists') and self.desc_frame.winfo_exists() else 'N/A'}")
+
+            # Modify layout within top_content_frame for wrapped view
             if hasattr(self, 'top_content_frame'):
-                print(f"DEBUG: WRAPPING: Modifying layout within top_content_frame.")
-                if hasattr(self, 'complete_button') and self.complete_button.winfo_ismapped(): # Check for new label name
+                if hasattr(self, 'complete_button') and self.complete_button.winfo_ismapped():
                     self.complete_button.pack_forget()
                 if hasattr(self, 'title_label') and hasattr(self.title_label, 'master') and self.title_label.master.winfo_ismapped(): # title_label.master is the clipper
                     self.title_label.master.pack_forget() # Forget the clipper frame
-                print(f"DEBUG: WRAPPING: title_label's clipper and complete_button forgotten.")
-                if hasattr(self, 'duration_display_frame'):
+
+                if hasattr(self, 'duration_display_frame'): # Center duration display
                     self.duration_display_frame.pack_forget()
                     self.duration_display_frame.pack(in_=self.top_content_frame, anchor='center', expand=True, fill='both', padx=0, pady=0)
-                    print(f"DEBUG: WRAPPING: duration_display_frame repacked in top_content_frame (centered). Parent: {self.duration_display_frame.winfo_parent() if hasattr(self.duration_display_frame, 'winfo_exists') and self.duration_display_frame.winfo_exists() else 'N/A'}")
-                else:
-                    print(f"DEBUG: WRAPPING: duration_display_frame not found.")
-                self.top_content_frame.pack_forget()
-                self.top_content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)
-                print(f"DEBUG: WRAPPING: top_content_frame repacked to fill main_frame.")
-            else:
-                print(f"DEBUG: WRAPPING: top_content_frame not found.")
-            new_x = self._calculate_corner_x()
-            new_y = self._calculate_corner_y()
-            new_geometry = f"{self.wrapped_width}x{self.wrapped_height}+{new_x}+{new_y}"
-            print(f"DEBUG: WRAPPING: Setting geometry to: {new_geometry}")
-            self.geometry(new_geometry)
-            print(f"DEBUG: WRAPPING: Unbinding drag events, binding unwrap click.")
-            if hasattr(self, '_on_mouse_press_binding_id') and self._on_mouse_press_binding_id:
-                self.unbind("<ButtonPress-1>", self._on_mouse_press_binding_id)
-            if hasattr(self, '_on_mouse_release_binding_id') and self._on_mouse_release_binding_id:
-                self.unbind("<ButtonRelease-1>", self._on_mouse_release_binding_id)
-            if hasattr(self, '_on_mouse_drag_binding_id') and self._on_mouse_drag_binding_id:
-                self.unbind("<B1-Motion>", self._on_mouse_drag_binding_id)
-            self._unwrap_binding_id = self.bind("<ButtonPress-1>", self.toggle_wrap_view)
-            if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_exists():
-                 self.duration_display_frame.bind("<ButtonPress-1>", self.toggle_wrap_view)
-            if hasattr(self, 'countdown_label') and self.countdown_label and self.countdown_label.winfo_exists():
-                 self.countdown_label.bind("<ButtonPress-1>", self.toggle_wrap_view)
-            if hasattr(self, 'no_duration_label') and self.no_duration_label and self.no_duration_label.winfo_exists():
-                 self.no_duration_label.bind("<ButtonPress-1>", self.toggle_wrap_view)
-            print(f"DEBUG: WRAPPING: Unwrap click bound with ID: {self._unwrap_binding_id}")
-            if hasattr(self, 'wrap_button'):
-                self.wrap_button.config(text="↗️")
-                ToolTip(self.wrap_button, text="Restore Full View")
-            print(f"DEBUG: WRAPPING: Wrap button updated.")
-        else:
-            print(f"DEBUG: UNWRAPPING branch: self.is_wrapped is now False.")
+
+            # Start animation
+            self.anim_current_step = 0
+            self._animate_wrap(on_complete=self._setup_wrap_bindings_and_ui)
+
+        else: # Start unwrapping process
             logger.debug("Unwrapping popup...")
-            print(f"DEBUG: UNWRAPPING: Unbinding unwrap click events. Current _unwrap_binding_id: {self._unwrap_binding_id}")
-            if self._unwrap_binding_id:
-                self.unbind("<ButtonPress-1>", self._unwrap_binding_id)
-                if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_exists():
-                     self.duration_display_frame.unbind("<ButtonPress-1>")
-                if hasattr(self, 'countdown_label') and self.countdown_label and self.countdown_label.winfo_exists():
-                     self.countdown_label.unbind("<ButtonPress-1>")
-                if hasattr(self, 'no_duration_label') and self.no_duration_label and self.no_duration_label.winfo_exists():
-                     self.no_duration_label.unbind("<ButtonPress-1>")
-                self._unwrap_binding_id = None
-            print(f"DEBUG: UNWRAPPING: Unwrap click events unbound. _unwrap_binding_id is now {self._unwrap_binding_id}")
-            print(f"DEBUG: UNWRAPPING: Re-binding drag events.")
-            self._on_mouse_press_binding_id = self.bind("<ButtonPress-1>", self._on_mouse_press)
-            self._on_mouse_release_binding_id = self.bind("<ButtonRelease-1>", self._on_mouse_release)
-            self._on_mouse_drag_binding_id = self.bind("<B1-Motion>", self._on_mouse_drag)
-            if hasattr(self, 'top_content_frame'):
-                print(f"DEBUG: UNWRAPPING: Restoring layout within top_content_frame.")
-                if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_ismapped():
-                    self.duration_display_frame.pack_forget()
-                print(f"DEBUG: UNWRAPPING: duration_display_frame forgotten from top_content_frame.")
-                if hasattr(self, 'complete_button'):
-                    self.complete_button.pack(side=tk.LEFT, padx=(0,5))
-                if hasattr(self, 'title_label') and hasattr(self.title_label, 'master') and self.title_label.master != self.top_content_frame: # master is clipper
-                    clipper = self.title_label.master
-                    clipper.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
-                elif hasattr(self, 'title_label'):
-                     self.title_label.pack(in_=self.top_content_frame, side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
-                print(f"DEBUG: UNWRAPPING: title_label repacked. Is mapped: {self.title_label.winfo_ismapped() if hasattr(self, 'title_label') and self.title_label.winfo_exists() else 'N/A'}")
-                if hasattr(self, 'duration_display_frame'):
-                    self.duration_display_frame.pack(in_=self.top_content_frame, side=tk.RIGHT, fill=tk.NONE, expand=False, padx=(5,0))
-                print(f"DEBUG: UNWRAPPING: duration_display_frame repacked into top_content_frame (original). Parent: {self.duration_display_frame.winfo_parent() if hasattr(self.duration_display_frame, 'winfo_exists') and self.duration_display_frame.winfo_exists() else 'N/A'}")
-                self.top_content_frame.pack_forget()
-                self.top_content_frame.pack(side=tk.TOP, fill=tk.X, pady=(0,2), anchor='n')
-                print(f"DEBUG: UNWRAPPING: top_content_frame's own packing restored in main_frame.")
-            else:
-                print(f"DEBUG: UNWRAPPING: top_content_frame not found.")
-            if hasattr(self, 'button_frame_ref'):
-                 self.button_frame_ref.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(3,2), ipady=2)
-            print(f"DEBUG: UNWRAPPING: button_frame_ref repacked. Is mapped: {self.button_frame_ref.winfo_ismapped() if hasattr(self.button_frame_ref, 'winfo_exists') and self.button_frame_ref.winfo_exists() else 'N/A'}")
-            restored_geometry = f"{self.width}x{self.initial_height}"
-            print(f"DEBUG: UNWRAPPING: Setting geometry to: {restored_geometry}")
-            self.geometry(restored_geometry)
-            print(f"DEBUG: UNWRAPPING: self.expanded_state_before_wrap = {self.expanded_state_before_wrap}")
-            if self.expanded_state_before_wrap:
-                print(f"DEBUG: UNWRAPPING: Calling self.toggle_expand_popup() to re-expand description.")
-                self.toggle_expand_popup()
-                print(f"DEBUG: UNWRAPPING: After toggle_expand_popup, self.is_expanded = {self.is_expanded}")
-            if hasattr(self, 'wrap_button'):
-                self.wrap_button.config(text="💊") # User changed icon
-                ToolTip(self.wrap_button, text="Minimize to Corner")
-            print(f"DEBUG: UNWRAPPING: Wrap button updated.")
-        logger.debug(f"toggle_wrap_view finished. is_wrapped: {self.is_wrapped}")
-        print(f"DEBUG: toggle_wrap_view EXIT: self.is_wrapped={self.is_wrapped}, current geometry={self.geometry()}")
+            # UI elements (complete_button, title_clipper, duration_display_frame in normal layout, button_frame_ref)
+            # will be re-packed by _setup_unwrap_bindings_and_ui after animation.
+            # For now, ensure top_content_frame is ready for its children to be repacked correctly.
+            # If duration_display_frame was centered, forget it.
+            if hasattr(self, 'duration_display_frame') and self.duration_display_frame.winfo_ismapped():
+                 # Check if it's centered (its parent is top_content_frame and it's filling)
+                 # This check is a bit heuristic. A more robust way is to store its original pack_info.
+                 if self.duration_display_frame.cget('anchor') == 'center':
+                      self.duration_display_frame.pack_forget()
+
+            self.anim_current_step = 0
+            self._animate_unwrap(on_complete=self._setup_unwrap_bindings_and_ui)
+
+        logger.debug(f"toggle_wrap_view finished initiating {'wrap' if self.is_wrapped else 'unwrap'} animation.")

     def start_countdown_action(self):
         logger.debug(f"POPUP_ACTION: 'start_countdown_action' called for task ID: {self.task.id if self.task else 'N/A'}.")
