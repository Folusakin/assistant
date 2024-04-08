#wake.py

import asyncio
import os
import numpy as np
import pyaudio
from openwakeword.model import Model
from threading import Thread
from queue import Queue

class AsyncWakeWordDetector:
    def __init__(self, model_path, inference_framework='tflite'):
        self.model_path = model_path
        self.inference_framework = inference_framework
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk_size = 1280
        self.audio_interface = pyaudio.PyAudio()
        self.stream = self.audio_interface.open(format=self.audio_format, channels=self.channels,
                                                rate=self.rate, input=True, frames_per_buffer=self.chunk_size)
        self.owwModel = Model(wakeword_models=[model_path], inference_framework=inference_framework)
        self.audio_queue = Queue()

    def start_listening(self):
        audio_thread = Thread(target=self.capture_audio, daemon=True)
        audio_thread.start()

    def capture_audio(self):
        while True:
            try:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                self.audio_queue.put(data)
            except OSError as e:
                print(f"Stream error encountered: {e}. Attempting to recover.")
                self.handle_stream_error()

    def handle_stream_error(self):
        """
        Attempts to recover from a stream error by restarting the audio stream.
        """
        try:
            # Attempt to close the current stream safely
            if self.stream.is_active():
                self.stream.stop_stream()
            self.stream.close()
        except Exception as e:
            print(f"Error closing stream: {e}")

        # Reinitialize the stream
        try:
            self.stream = self.audio_interface.open(format=self.audio_format, channels=self.channels,
                                                    rate=self.rate, input=True, frames_per_buffer=self.chunk_size)
        except Exception as e:
            print(f"Failed to restart stream: {e}")
            # Consider adding more robust recovery or shutdown logic here

    async def detect_wake_word(self):
        self.start_listening()
        while True:
            if not self.audio_queue.empty():
                audio_data = self.audio_queue.get()
                audio = np.frombuffer(audio_data, dtype=np.int16)
                prediction = self.owwModel.predict(audio)
                for mdl, scores in self.owwModel.prediction_buffer.items():
                    if scores[-1] > 0.7:  # Threshold for wake word detection
                        self.owwModel.reset()
                        return True
            await asyncio.sleep(0.01)  # Non-blocking sleep to yield control

# Example usage
async def main():
    # Replace the model path with an environment variable
    model_path = os.environ.get("WAKE_WORD_MODEL_PATH")
    detector = AsyncWakeWordDetector(model_path=model_path)

    # Continuous detection loop
    try:
        while True:
            detected = await detector.detect_wake_word()
            if detected:
                print("Wake word detected!")
                # Here, you can add any action you want to perform upon detection
                # For example, initiating a conversation, playing a sound, etc.
                # Reset or continue listening as needed
    except KeyboardInterrupt:
        print("Stopping wake word detection...")

if __name__ == "__main__":
    asyncio.run(main())
