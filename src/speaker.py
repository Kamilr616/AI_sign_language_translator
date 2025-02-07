import pyttsx3
import threading


ENGINE = r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_ZIRA_11.0'


class SpeakerApp:
    def __init__(self, rate=150, volume=0.8):
        """Initialize the TextToSpeech engine with the given rate and volume."""
        self.engine = pyttsx3.init()
        self.set_rate(rate)
        self.set_volume(volume)
        self._thread = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._set_default_voice(ENGINE)

    def set_rate(self, rate=150):
        """Set the speech rate."""
        self.engine.setProperty('rate', rate)

    def set_volume(self, volume=0.8):
        """Set the speech volume."""
        self.engine.setProperty('volume', volume)

    def _set_default_voice(self, voice_engine=ENGINE):
        """Set the default voice."""
        self.engine.setProperty('voice', voice_engine)

    def speak(self, text=""):
        """Speak the given text, managing concurrent speech requests."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._stop_event.set()

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._speak, args=(text,))
            self._thread.start()

    def _speak(self, text=""):
        """Internal method to handle the speech synthesis."""

        def on_end():
            if self._stop_event.is_set():
                self.engine.stop()

        self.engine.connect('finished-utterance', on_end)
        self.engine.say(text)
        try:
            self.engine.runAndWait()
        except RuntimeError:
            return

    def stop(self):
        """Stop the speech synthesis."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._stop_event.set()
                self._thread.join()
            self.engine.stop()
