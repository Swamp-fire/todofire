import pyttsx3
import threading
import logging
import queue # Added for speech queue
import time

# Setup module-level logger for this manager
logger = logging.getLogger(__name__)

class TTSManager:
    def __init__(self):
        self.engine = None
        self.is_muted = False
        self.default_volume = 0.8
        self.tts_lock = threading.Lock() # Lock for critical engine operations
        self._engine_init_error_logged_once = False

        self.speech_queue = queue.Queue()
        self.is_running = True # Control flag for the worker thread

        self._initialize_engine()

        # Start the worker thread that processes the speech queue
        self.worker_thread = threading.Thread(target=self._process_speech_queue, daemon=True)
        self.worker_thread.name = "TTSWorkerThread"
        self.worker_thread.start()
        logger.info("TTSManager initialized and worker thread started.")

    def _initialize_engine(self):
        logger.info("Attempting to initialize TTS engine...")
        try:
            self.engine = pyttsx3.init()
            if self.engine:
                self.engine.setProperty('volume', self.default_volume)
                current_rate = self.engine.getProperty('rate')
                logger.debug(f"TTS Engine properties: Volume={self.default_volume}, Rate={current_rate}")
                try:
                    current_voice_id = self.engine.getProperty('voice')
                    voices = self.engine.getProperty('voices')
                    current_voice_details = "N/A"
                    for v in voices:
                        if v.id == current_voice_id:
                            current_voice_details = f"ID: {v.id}, Name: {v.name}, Langs: {v.languages}"
                            break
                    logger.debug(f"TTS Engine Voice details: {current_voice_details}")
                except Exception as voice_prop_error:
                    logger.warning(f"Could not retrieve detailed voice properties: {voice_prop_error}", exc_info=False) # Reduced noise
                logger.info("TTS Engine Initialized successfully.")
            else:
                logger.error("pyttsx3.init() returned None. TTS engine not available.")
                self.engine = None
        except RuntimeError as r_err:
             logger.error(f"Failed to initialize TTS engine (RuntimeError, possibly missing drivers like espeak): {r_err}", exc_info=False) # Reduced noise
             self.engine = None
        except Exception as e:
            logger.error(f"Generic failure to initialize TTS engine: {e}", exc_info=False) # Reduced noise
            self.engine = None

    def set_mute(self, mute_status: bool):
        self.is_muted = mute_status
        logger.info(f"TTS mute status set to: {self.is_muted}")

    def speak(self, text: str, error_context: bool = False):
        """
        Adds the given text to a queue to be spoken by the TTS worker thread.
        Respects mute status and engine availability.
        """
        # Prepare the text to be spoken, potentially adding "Error: " prefix
        # For this subtask, we'll queue a dictionary or tuple to include error_context
        speech_item = {'text': text, 'is_error': error_context}

        logger.debug(f"Speak request: item='{speech_item}', muted={self.is_muted}, engine_exists={self.engine is not None}")

        if self.engine is None:
            if not self._engine_init_error_logged_once:
                logger.warning("TTS engine not initialized. Cannot queue speech.")
                self._engine_init_error_logged_once = True
            return

        if self.is_muted:
            logger.info(f"TTS is muted. Suppressing speech for: '{speech_item['text']}'")
            return

        try:
            self.speech_queue.put(speech_item)
            logger.info(f"Added to speech queue: '{speech_item['text']}' (Error context: {speech_item['is_error']})")
        except Exception as e:
            logger.error(f"Failed to add item to speech queue: {e}", exc_info=True)


    def _process_speech_queue(self):
        """
        Worker thread method that continuously processes speech requests from a queue.
        """
        logger.info("TTS worker thread started and waiting for speech items.")
        while self.is_running:
            try:
                # Wait for an item from the queue (blocking, with timeout for periodic check of is_running)
                speech_item = self.speech_queue.get(block=True, timeout=1)
            except queue.Empty:
                # Timeout occurred, loop again to check self.is_running
                continue

            if speech_item is None: # Sentinel for shutdown
                logger.info("TTS worker thread received sentinel. Shutting down.")
                self.speech_queue.task_done()
                break

            text_to_say = speech_item['text']
            if speech_item['is_error']:
                text_to_say = f"Error: {text_to_say}"

            logger.debug(f"TTS Worker: Attempting to acquire lock for: '{text_to_say}'")
            # Lock can be blocking here as this is the only thread consuming from queue and using engine
            if self.tts_lock.acquire():
                logger.debug(f"TTS Worker: Lock acquired for '{text_to_say}'.")
                try:
                    if self.engine:
                        logger.info(f"TTS Worker: Saying: '{text_to_say}'")
                        self.engine.say(text_to_say)
                        self.engine.runAndWait()
                        logger.info(f"TTS Worker: Finished saying: '{text_to_say}'")
                    else:
                        logger.warning("TTS Worker: Engine became unavailable before speech could be processed.")
                except Exception as e:
                    logger.error(f"TTS Worker: Engine error during speech for '{text_to_say}': {e}", exc_info=True)
                finally:
                    self.tts_lock.release()
                    logger.debug(f"TTS Worker: Lock released for '{text_to_say}'.")
                    self.speech_queue.task_done()
            else: # Should not happen with a blocking acquire unless timeout specified and failed.
                logger.error(f"TTS Worker: Failed to acquire lock for '{text_to_say}'. This should not happen with blocking acquire.")
                # If it somehow fails, put item back or log as lost. For now, log and task_done.
                self.speech_queue.task_done()


        logger.info("TTS worker thread finished.")

    def shutdown(self):
        """
        Signals the TTS worker thread to shut down gracefully.
        """
        logger.info("TTSManager shutdown requested.")
        self.is_running = False
        try:
            # Put sentinel value to unblock the queue.get()
            self.speech_queue.put(None, block=False, timeout=1)
        except queue.Full:
            logger.warning("Speech queue was full during shutdown signal, worker might take longer to stop if it was already full of items.")

        if self.worker_thread and self.worker_thread.is_alive():
            logger.debug("Waiting for TTS worker thread to join...")
            self.worker_thread.join(timeout=5) # Wait up to 5 seconds
            if self.worker_thread.is_alive():
                logger.warning("TTS worker thread did not join in time.")

        # Attempt to stop the engine if it's busy, though runAndWait should complete.
        # This is more of a fallback.
        if self.engine:
            try:
                # Check if the engine is busy. pyttsx3 doesn't have a standard isBusy().
                # We rely on the lock and runAndWait() completing.
                # self.engine.stop() # This can be abrupt.
                logger.info("TTS engine shutdown actions (if any specific needed by pyttsx3, usually not).")
            except Exception as e:
                logger.error(f"Error during engine stop attempt on shutdown: {e}", exc_info=True)
        logger.info("TTSManager shutdown complete.")


# Global instance of the TTSManager
tts_manager = TTSManager()

# Example usage for testing this module directly (optional)
if __name__ == '__main__':
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)-7s - %(name)-15s - %(threadName)-18s - %(message)s')

    logger.info("Directly testing TTSManager with new queuing system...")

    if tts_manager.engine:
        tts_manager.speak("Hello, this is message one.")
        tts_manager.speak("This is a slightly longer message, number two.")
        tts_manager.speak("And message three, testing the queue.")

        logger.info("Queued initial messages. Waiting a moment for them to process...")
        time.sleep(1) # Short sleep to allow queue processing to start

        tts_manager.speak("Test message four, after a short pause.")

        tts_manager.set_mute(True)
        tts_manager.speak("This message five should NOT be added to queue (muted).")
        tts_manager.set_mute(False)

        tts_manager.speak("Message six, error test.", error_context=True)

        logger.info("Testing rapid speech calls. These should now be queued and spoken sequentially.")
        for i in range(5):
            tts_manager.speak(f"Rapid test {i+1}.")
            # No sleep needed here, queue should handle it.

        logger.info("All test messages queued. Main thread will wait for queue to empty via shutdown...")
        # Wait for all items in queue to be processed before shutting down worker
        # This is not strictly necessary if daemon=True and main thread just exits,
        # but good for ensuring all speech is heard in a direct test.
        # A better way is to join the queue if that's needed.
        # For now, shutdown will handle joining the worker.

    else:
        logger.warning("TTS engine not available. Cannot run direct speech tests.")

    # Gracefully shutdown the TTS manager and its worker thread
    tts_manager.shutdown()
    logger.info("Direct TTSManager test finished.")
```
