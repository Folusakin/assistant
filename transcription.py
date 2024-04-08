from typing import Optional
import os
import azure.cognitiveservices.speech as speechsdk

class AzureSpeechRecognizer:
    """
    A class to interface with Azure's Cognitive Speech Services for speech recognition.
    This class initializes the speech service configuration using environment variables,
    creates a speech recognizer, and provides a method to recognize speech from the microphone.
    """
    
    def __init__(self) -> None:
        """
        Initializes the AzureSpeechRecognizer instance by setting up the speech service configuration
        and creating a speech recognizer with the default microphone as the audio source.
        
        Raises:
            EnvironmentError: If either the SPEECH_KEY or SPEECH_REGION environment variables are not set.
        """
        # Retrieve Azure speech service credentials from environment variables
        self.speech_key: str = os.getenv('SPEECH_KEY')
        self.speech_region: str = os.getenv('SPEECH_REGION')
        
        # Validate the presence of necessary environment variables
        if not self.speech_key or not self.speech_region:
            raise EnvironmentError("SPEECH_KEY and/or SPEECH_REGION environment variables are not set.")
        
        # Initialize speech configuration with the provided credentials
        self.speech_config: speechsdk.SpeechConfig = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.speech_region)
        
        # Set additional service properties if needed
        self.speech_config.set_service_property(
            "speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs",
            "2000",  # Increase the segmentation silence timeout to 2000ms
            speechsdk.ServicePropertyChannel.UriQueryParameter)
        
        # Setup the audio configuration to use the default microphone
        self.audio_config: speechsdk.audio.AudioConfig = speechsdk.audio.AudioConfig(use_default_microphone=True)
        
        # Create the speech recognizer with the configured settings
        self.speech_recognizer: speechsdk.SpeechRecognizer = self.create_speech_recognizer()

    def create_speech_recognizer(self) -> speechsdk.SpeechRecognizer:
        """
        Creates a SpeechRecognizer object with the configured speech and audio settings.
        
        Returns:
            SpeechRecognizer: An instance of SpeechRecognizer configured for the instance.
        """
        return speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=self.audio_config)

    def recognize_speech_from_microphone(self) -> Optional[str]:
        """
        Listens for a single utterance from the default microphone and attempts to recognize speech.
        
        Prints the recognition result to the console and returns the recognized text if speech is recognized.
        
        Returns:
            Optional[str]: The recognized text if speech was recognized, otherwise None.
        """
        print("Listening...")

        # Perform speech recognition
        result = self.speech_recognizer.recognize_once_async().get()

        # Handle the recognition result based on its reason
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            #print(f"Recognized: {result.text}")
            return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            print("No speech could be recognized")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"Speech Recognition canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {cancellation_details.error_details}")

        return None


# Usage example with loop
if __name__ == "__main__":
    recognizer = AzureSpeechRecognizer()
    for _ in range(3):  # Run the speech recognition 3 times
        print("\nStarting new speech recognition...")
        transcript = recognizer.recognize_speech_from_microphone()
        print(f"Transcript: {transcript}")
        print("Speech recognition cycle completed.\n")




