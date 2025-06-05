import pyttsx3
import threading
import logging
import time # Added for testing rapid calls

# Setup module-level logger for this manager
logger = logging.getLogger(__name__)
# Note: Basic logging configuration (basicConfig) should ideally be done once
# in the main application entry point (e.g., main_app.py).
# If scheduler_manager or main_app already configure it, this line might be redundant
# or could conflict if configurations are different.
# For a library module like this, it's often better to assume the application will configure logging.
# However, for standalone testing or if this module might be used independently,
# a fallback basicConfig can be useful, often guarded by `if not logging.getLogger().hasHandlers():`
# For this project, main_app.py already calls basicConfig.

class TTSManager:
    def __init__(self):
        self.engine = None
        self.is_muted = False
        self.default_volume = 0.8  # Volume is a float between 0.0 and 1.0
        self.tts_lock = threading.Lock() # Lock to ensure thread-safe access to engine operations
        self._engine_init_error_logged_once = False # To avoid spamming logs if engine fails
        self._initialize_engine()

    def _initialize_engine(self):
        logger.info("Attempting to initialize TTS engine...")
        try:
            self.engine = pyttsx3.init()
            if self.engine:
                self.engine.setProperty('volume', self.default_volume)
                # Optional: Log details about the selected engine/voice
                try:
                    current_voice = self.engine.getProperty('voice')
                    voices = self.engine.getProperty('voices')
                    logger.debug(f"TTS Engine initialized. Current Voice ID: {current_voice}")
                    # for i, voice in enumerate(voices):
                    #     logger.debug(f"Voice {i}: ID: {voice.id}, Name: {voice.name}, Lang: {voice.languages}")
                except Exception as voice_prop_error:
                    logger.warning(f"Could not retrieve voice properties: {voice_prop_error}")
                logger.info("TTS Engine Initialized successfully.")
            else:
                logger.error("pyttsx3.init() returned None. TTS engine not available.")
                self.engine = None # Ensure it's None
        except Exception as e:
            logger.error(f"Failed to initialize TTS engine: {e}", exc_info=True)
            self.engine = None

    def set_mute(self, mute_status: bool):
        """Sets the mute status for TTS."""
        self.is_muted = mute_status
        logger.info(f"TTS mute status set to: {self.is_muted}")

    def speak(self, text: str, error_context: bool = False):
        """
        Speaks the given text using TTS if the engine is available and not muted.
        Runs the speech in a separate thread to avoid blocking the main UI.
        """
        if self.engine is None:
            if not self._engine_init_error_logged_once:
                logger.warning("TTS engine not initialized or failed to initialize. Cannot speak.")
                self._engine_init_error_logged_once = True
            return

        if self.is_muted:
            logger.info(f"TTS is muted. Suppressing speech for: '{text}'")
            return

        speech_text = text
        if error_context:
            speech_text = f"Error: {text}"

        logger.info(f"Queueing speech: '{speech_text}'")
        # Run TTS in a separate thread to avoid blocking UI
        thread = threading.Thread(target=self._run_tts, args=(speech_text,), daemon=True)
        thread.start()

    def _run_tts(self, text: str):
        """
        Internal method to run the TTS engine's say and runAndWait.
        This method is executed in a separate thread and uses a lock.
        """
        # Try to acquire lock without blocking. If busy, skip this speech request.
        acquired_lock = self.tts_lock.acquire(blocking=False)
        if not acquired_lock:
            logger.warning(f"TTS engine busy, speech for '{text}' skipped.")
            return

        try:
            if self.engine: # Re-check engine status within the thread
                logger.debug(f"TTS attempting to say: '{text}'")
                self.engine.say(text)
                self.engine.runAndWait() # This blocks within this thread, not the main thread
                logger.debug(f"TTS finished saying: '{text}'")
            else:
                logger.warning("TTS engine became unavailable before speech could occur in thread.")
        except Exception as e:
            logger.error(f"TTS engine error during speech for '{text}': {e}", exc_info=True)
        finally:
            self.tts_lock.release() # Always release the lock

# Global instance of the TTSManager
# This instance can be imported by other modules (e.g., main_app.py, scheduler_manager.py).
tts_manager = TTSManager()

# Example usage for testing this module directly (optional)
if __name__ == '__main__':
    # Ensure logs are visible for direct testing
    if not logging.getLogger().hasHandlers(): # Setup basic config if no handlers are present
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(threadName)s - %(message)s')

    logger.info("Testing TTSManager directly...")
    if tts_manager.engine:
        tts_manager.speak("Hello, this is a test of the Text to Speech manager.")
        # Wait for the first speech to likely complete before the next one
        # This helps in demonstrating sequential speech if the engine supports it well
        # and also to see the effect of the lock more clearly.
        time.sleep(3)

        tts_manager.speak("This is a second test, to check threading and locking.")
        time.sleep(3)

        tts_manager.set_mute(True)
        tts_manager.speak("This message should not be spoken because TTS is muted.")
        time.sleep(1) # Give time for the muted log to appear if any processing happens

        tts_manager.set_mute(False)
        tts_manager.speak("Mute is off. This should be spoken.")
        time.sleep(3)

        tts_manager.speak("Error test.", error_context=True)
        time.sleep(3)

        logger.info("Testing rapid speech calls (expecting some to be skipped if engine is busy due to non-blocking lock)...")
        for i in range(5):
            tts_manager.speak(f"Rapid test number {i+1}")
            time.sleep(0.1) # Very short delay, likely not enough for full speech, tests lock

        logger.info("Waiting a bit for any queued speech to finish (if any)...")
        time.sleep(5) # Wait for final speech attempts
    else:
        logger.warning("TTS engine not available. Cannot run direct speech tests.")

    logger.info("Direct TTSManager test finished.")
