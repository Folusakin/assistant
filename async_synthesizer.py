#async_synthesizer.py

import asyncio
import os
import sys
import re
from google.cloud import texttospeech_v1
import pyaudio
from configure import sentences
import numpy as np

# Set the path to your Google Cloud credentials JSON file using an environment variable
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.environ.get("GOOGLE_CREDENTIALS_PATH")

# Set event loop policy on Windows for Python 3.8+
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class AsyncAudioSynthesizer:
    def __init__(self):
        self.tts_client = texttospeech_v1.TextToSpeechClient()
        self.audio_format = pyaudio.paInt16  # Typical for PCM 16-bit
        self.channels = 1  # Mono audio
        self.rate = 16000  # Sample rate, adjust based on the TTS output
        self.audio_queue = asyncio.Queue()
        self.sentence_queue = asyncio.Queue()  # Queue for sentences to be synthesized
        self.p = pyaudio.PyAudio()
        self.done_flag = True
        
        # Open the stream here and keep it open
        self.stream = self.p.open(format=self.audio_format, channels=self.channels,
                                  rate=self.rate, output=True)
        
        self.playing_task = asyncio.create_task(self.play_from_queue())
        self.synthesizing_task = asyncio.create_task(self.synthesize_from_queue())

    def _prepare_synthesis_input(self, text: str) -> texttospeech_v1.SynthesisInput:
        cleaned_text = self._clean_text(text)
        print(cleaned_text)
        return texttospeech_v1.SynthesisInput(text=cleaned_text)

    def _select_voice(self) -> texttospeech_v1.VoiceSelectionParams:
        # Here we specify the studio voice 'en-GB-Studio-C'
        return texttospeech_v1.VoiceSelectionParams(
            language_code='en-US',  # English (UK)
            name='en-US-Studio-O',  # Studio voice
            ssml_gender=texttospeech_v1.SsmlVoiceGender.FEMALE  # Female voice
        )

    def _configure_audio_settings(self) -> texttospeech_v1.AudioConfig:
        return texttospeech_v1.AudioConfig(
            audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.rate
        )

    


    async def synthesize_speech(self, text: str) -> bytes:
        synthesis_input = self._prepare_synthesis_input(text)
        voice = self._select_voice()
        audio_config = self._configure_audio_settings()

        try:
            response = await asyncio.to_thread(
                self.tts_client.synthesize_speech,
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            audio_content = response.audio_content
            # Apply fade in and fade out effects
            faded_audio_content = self.apply_fade_effects(audio_content)
            await self.audio_queue.put(faded_audio_content)
        except Exception as e:
            print(f"Error synthesizing speech: {e}")

    def apply_fade_effects(self, audio_content: bytes, fade_duration=0.1) -> bytes:
        # Convert bytes to numpy array for manipulation
        # Ensure the array is writable by making a copy
        audio_array = np.frombuffer(audio_content, dtype=np.int16).copy()

        # Calculate fade in and fade out samples count
        fade_in_samples = fade_out_samples = int(self.rate * fade_duration)

        # Apply fade in
        for i in range(fade_in_samples):
            audio_array[i] = int(audio_array[i] * (i / fade_in_samples))

        # Apply fade out
        for i in range(fade_out_samples):
            audio_array[-i - 1] = int(audio_array[-i - 1] * (i / fade_out_samples))

        # Convert numpy array back to bytes
        return audio_array.tobytes()




    async def play_from_queue(self):
        while True:
            audio_content = await self.audio_queue.get()
            try:
                self.stream.write(audio_content)
            except Exception as e:
                print(f"Error playing audio: {e}")
            finally:
                self.audio_queue.task_done()
            

    async def synthesize_from_queue(self):
        while True:
            sentence = await self.sentence_queue.get()
            await self.synthesize_speech(sentence)
            self.sentence_queue.task_done()
    def _clean_text(self, text: str) -> str:
        # Regular expression to match emojis and other non-ASCII characters; you might need to adjust it
        emoji_pattern = re.compile("["
                                   u"\U0001F600-\U0001F64F"  # emoticons
                                   u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                                   u"\U0001F680-\U0001F6FF"  # transport & map symbols
                                   u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                                   u"\U00002702-\U000027B0"
                                   u"\U000024C2-\U0001F251"
                                   "]+", flags=re.UNICODE)
        # Remove emojis and other non-desirable characters
        cleaned_text = emoji_pattern.sub(r'', text)
        
        # Remove asterisks
        cleaned_text = cleaned_text.replace('*', '')
        
        return cleaned_text
        
    def enqueue_sentence(self, sentence: str):
        asyncio.create_task(self.sentence_queue.put(sentence))

    def close(self):
        if self.playing_task:
            self.playing_task.cancel()
        if self.synthesizing_task:
            self.synthesizing_task.cancel()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()

async def main():
    synthesizer = AsyncAudioSynthesizer()

    try:
        for sentence in sentences:
            synthesizer.enqueue_sentence(sentence)
            await asyncio.sleep(1)  # Adjust sleep time as needed

        await synthesizer.sentence_queue.join()
        await asyncio.sleep(5)  # Give time for the last audio to finish playing
    finally:
        synthesizer.close()

if __name__ == "__main__":
    asyncio.run(main())
