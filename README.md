# Voice-Activated AI Assistant

This project is a voice-activated AI assistant that leverages various technologies and APIs to provide a conversational interface for tasks such as weather information retrieval, music playback control, and general question answering. The assistant utilizes natural language processing, speech recognition, and text-to-speech capabilities to enable seamless interaction with the user.

## Features

- Wake word detection using OpenWakeWord Jarvis for activating the assistant
- Speech recognition for transcribing user queries
- Integration with OpenAI's GPT-4 for natural language understanding and generation
- Tool-based architecture for handling specific tasks (e.g., weather information, music playback)
- Text-to-speech synthesis for audible responses
- Asynchronous processing for improved performance and responsiveness

## Prerequisites

Before running the code, ensure that you have the following:

- Python 3.7 or higher
- Required Python libraries (see the "Requirements" section below)
- API credentials for the following services:
  - OpenAI API (for GPT-4 integration)
  - Azure Cognitive Services Speech API (for speech recognition)
  - Spotify API (for music playback control)
  - Google Cloud Text-to-Speech API (for speech synthesis)
- Environment variables set for API credentials and other configuration
- OpenWakeWord Jarvis model for wake word detection

## Setup

1. Clone the repository:

```
git clone https://github.com/Folusakin/assistant.git
cd assistant
```

2. Install the required Python libraries:

```
pip install -r requirements.txt
```

3. Set up the required environment variables:

```
export OPENAI_API_KEY=your_openai_api_key
export SPEECH_KEY=your_azure_speech_api_key
export SPEECH_REGION=your_azure_speech_api_region
export SPOTIFY_USERNAME=your_spotify_username
export SPOTIFY_CLIENT_ID=your_spotify_client_id
export SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
export GOOGLE_APPLICATION_CREDENTIALS=path/to/your/google/credentials.json
export OPENWAKEWORD_JARVIS_MODEL_PATH=path/to/your/openwakeword_jarvis_model
```

4. Run the main script:

```
python main.py
```

## Requirements

The following Python libraries are required to run the code:

- openai
- azure-cognitiveservices-speech
- spotipy
- google-cloud-texttospeech
- pyaudio
- numpy
- aiohttp
- sqlalchemy
- backoff
- openwakeword

You can install these libraries using pip:

```
pip install openai azure-cognitiveservices-speech spotipy google-cloud-texttospeech pyaudio numpy aiohttp sqlalchemy backoff openwakeword
```

## Common Pitfalls and Considerations

1. **API Credentials**: Ensure that you have valid API credentials for all the required services and that they are properly set as environment variables. Incorrect or missing credentials will cause the corresponding functionality to fail.

2. **OpenWakeWord Jarvis Model**: Make sure you have the OpenWakeWord Jarvis model file and provide the correct path to the model file using the `OPENWAKEWORD_JARVIS_MODEL_PATH` environment variable.

3. **Microphone Access**: The assistant requires access to the microphone for speech recognition. Ensure that your microphone is properly connected and configured, and grant necessary permissions for the script to access the microphone.

4. **Asynchronous Processing**: The code heavily relies on asynchronous processing using the `asyncio` library. Familiarize yourself with the concepts of asynchronous programming and ensure that you are using the appropriate asynchronous functions and syntax.

5. **Error Handling**: The code includes error handling mechanisms, such as the `backoff` library for retrying failed API calls. However, be prepared to handle and log any unexpected errors that may occur during runtime.

6. **Library Versions**: The code has been developed and tested with specific versions of the required libraries. Ensure that you are using compatible versions of the libraries to avoid any compatibility issues.

7. **Database Setup**: The code uses a SQLite database (`uscities.db`) to store the coordinates of US cities. Ensure that the database file is present in the project directory and has the correct schema.

8. **Concurrent Requests**: The assistant can handle multiple user queries concurrently using asynchronous processing. However, be mindful of the rate limits and usage quotas of the APIs you are using to avoid exceeding them.

9. **Customization**: The code provides a foundation for a voice-activated AI assistant, but you may need to customize it further based on your specific requirements. Feel free to modify the code, add new features, or integrate additional APIs as needed.

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgments

- [OpenAI](https://openai.com) for providing the GPT-4 language model
- [Azure Cognitive Services](https://azure.microsoft.com/services/cognitive-services/) for speech recognition capabilities
- [Spotify API](https://developer.spotify.com/) for music playback control
- [Google Cloud Text-to-Speech API](https://cloud.google.com/text-to-speech) for speech synthesis
- [OpenWakeWord](https://github.com/openwakeword/openwakeword) for the Jarvis wake word detection model
- The open-source community for various libraries and tools used in this project