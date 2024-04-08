#main.py

import asyncio
from typing import Any, Dict
import time
from transcription import AzureSpeechRecognizer
import sys
import re
from assistant_gpt import GPTAssistant  # Ensure correct import based on the actual class name
from weather import WeatherAPI
from async_spotify import AsyncSpotifyClient
from async_synthesizer import AsyncAudioSynthesizer
from wake import AsyncWakeWordDetector
# Set event loop policy for Windows to prevent potential compatibility issues
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
async def tts_simulator(tts_queue: asyncio.Queue):
    """
    Simulates sending text to a TTS module in a non-blocking manner.
    
    Parameters:
    - tts_queue: An asyncio.Queue instance for receiving text.
    """
    while True:
        
        text = await tts_queue.get()
        if text is None:  # Use None as a signal to stop the simulator
            break
        # Simulate sending the text to a TTS module
        print(f"TTS: {text}")
        await asyncio.sleep(0.1)  # Simulate processing time

def split_into_sentences(text: str) -> list:
    """
    Splits the text into sentences based on punctuation.
    
    Parameters:
    - text: The text to split.
    
    Returns:
    - A list of complete sentences.
    """
    sentences = re.split(r'(?<=[.!?]) +', text)
    return sentences

async def enqueue_sentences(tts_queue: asyncio.Queue, text: str):
    """
    Enqueues complete sentences into the TTS queue.
    
    Parameters:
    - tts_queue: An asyncio.Queue instance for the TTS module.
    - text: The text to be split and enqueued.
    """
    sentences = split_into_sentences(text)
    for sentence in sentences:
        await tts_queue.put(sentence)


async def main(weather_api: WeatherAPI, spotify_client: AsyncSpotifyClient):
    await spotify_client.async_init()
    tts_synthesizer = AsyncAudioSynthesizer()
    assistant = GPTAssistant(ai_model="gpt-4-turbo-preview")
    # Replace the model path with an environment variable
    model_path = os.environ.get("WAKE_WORD_MODEL_PATH")
    
    detector = AsyncWakeWordDetector(model_path=model_path)
    speech_recognizer = AzureSpeechRecognizer()

    async def check_and_clear_messages():
        while True:
            initial_length = len(assistant.messages)
            initial_content = assistant.messages.copy() if initial_length > 1 else None
            await asyncio.sleep(120)  # Wait for 2 minutes
            if initial_content and assistant.messages == initial_content:
                # Clear all but the first element if no new messages are added and length > 1
                assistant.messages = [assistant.messages[0]] if len(assistant.messages) > 1 else assistant.messages
                print("Messages cleared due to inactivity.")

    message_check_task = asyncio.create_task(check_and_clear_messages())

    try:
        while True:
            detected = await detector.detect_wake_word()
            if detected:
                print("Wake word detected, action can be initiated.")
                print("Listening for user input...")
                transcript = await asyncio.to_thread(speech_recognizer.recognize_speech_from_microphone)
                
                if transcript:
                    if "exit" in transcript.lower() and len(transcript) <= 5:
                        break

                    print(f"User: {transcript}")
                    print("Assistant: ", end="", flush=True)
                    assistant_response = await process_query_with_assistant(assistant, transcript, tts_synthesizer)
                    
                    if not assistant_response:
                        print("No response or further action required.")
            else:
                await asyncio.sleep(0.1)
                
    finally:
        message_check_task.cancel()
        try:
            await message_check_task
        except asyncio.CancelledError:
            pass
        print("Session ended and resources have been cleaned up.")
        await weather_api.close()
        print(assistant.messages)



async def process_query_with_assistant(assistant: GPTAssistant, query: str, tts_synthesizer: AsyncAudioSynthesizer) -> None:
    """
    Processes a user query with the GPTAssistant and manages tool calls if necessary,
    enqueueing responses to the TTS queue.
    
    Parameters:
    - assistant: The GPTAssistant instance for processing queries.
    - query: The user query string.
    - tts_queue: The asyncio.Queue instance for the TTS module.
    """
    tts_synthesizer.done_flag=False
    response_accumulator = ""
    assistant_response=""
    sentence_accumulator = ""
    start_time = time.perf_counter()

    async for chunk in assistant.process_transcript(query):
        #print(chunk, end="", flush=True)
        response_accumulator += chunk
        sentence_accumulator+=chunk
        if chunk.endswith(('.', '!', '?')):
            sentences = split_into_sentences(sentence_accumulator)
            for sentence in sentences:
                tts_synthesizer.enqueue_sentence(sentence)
            
            sentence_accumulator = ""
            

    if sentence_accumulator:
        sentences = split_into_sentences(sentence_accumulator)
        for sentence in sentences:
            tts_synthesizer.enqueue_sentence(sentence)

    # Determine the next steps based on assistant's response and tool calls
    if not response_accumulator and not assistant.is_tool_called:
        return "No responses received. Please check the query or the assistant's configuration."
    
    if not response_accumulator and assistant.is_tool_called:
        tts_synthesizer.enqueue_sentence("On it!")
        further_processing_required = await handle_tool_calls(
            assistant.tools_called["calls"], query, assistant
        )
        
        if further_processing_required:
            async for response_chunk in assistant.get_response_from_openai():
                #print(response_chunk, end="", flush=True)
                assistant_response += response_chunk
                sentence_accumulator+=response_chunk
                if response_chunk.endswith(('.', '!', '?')):
                    tts_synthesizer.enqueue_sentence(sentence_accumulator)
                    # sentences = split_into_sentences(sentence_accumulator)
                    # for sentence in sentences:
                        # tts_synthesizer.enqueue_sentence(sentence)
                    
                    sentence_accumulator = ""

            if sentence_accumulator:
                
                sentences = split_into_sentences(sentence_accumulator)
                for sentence in sentences:
                    tts_synthesizer.enqueue_sentence(sentence)
        else:
            #print(assistant.messages[-1]['content'])
            # sentences = split_into_sentences(assistant.messages[-1]['content'])
            # for sentence in sentences:
            tts_synthesizer.enqueue_sentence(assistant.messages[-1]['content'])
            tts_synthesizer.done_flag=False
                
    print(f"--- Processed in {time.perf_counter() - start_time} seconds ---")
    tts_synthesizer.done_flag=True
    return assistant_response

async def handle_tool_calls(tool_calls: Dict[str, Any], query: str, assistant: GPTAssistant) -> bool:
    """
    Handles asynchronous calls to external tools based on the assistant's requirements.
    
    Parameters:
    - tool_calls: A dictionary of the tool calls to be processed.
    - query: The original query string for context.
    - assistant: The GPTAssistant instance.
    
    Returns:
    - A boolean indicating if further processing is required after handling tool calls.
    """
    if len(tool_calls) == 1 and tool_calls[0]['function_name'] == "get_weather_information":
        # Process a single tool call, specifically for weather information
        await process_single_tool_call(tool_calls[0], query, assistant)
        return False
    else:
        # Process multiple tool calls concurrently
        await process_multiple_tool_calls(tool_calls, assistant)
        return True

async def process_single_tool_call(tool_call: Dict[str, Any], query: str, assistant: GPTAssistant):
    """
    Specialized handling for a single tool call, appending the result directly to the assistant's messages.
    
    Parameters:
    - tool_call: The specific tool call to process.
    - query: The original query string for context.
    - assistant: The GPTAssistant instance.
    """
    result = await run_function_async(tool_call['function_name'], tool_call['parameters'], query)
    await assistant.append_message("assistant", result["weather_tool_response_needing_interpretation"])

async def process_multiple_tool_calls(tool_calls: Dict[str, Any], assistant: GPTAssistant):
    """
    Handles multiple tool calls concurrently, appending their results to the assistant's messages.
    
    Parameters:
    - tool_calls: A list of tool calls to process.
    - assistant: The GPTAssistant instance.
    """
    tasks = [run_function_async(call['function_name'], call['parameters'], "") for call in tool_calls]
    responses = await asyncio.gather(*tasks)

    for idx, response in enumerate(responses, start=1):
        assistant.messages.append({
            "tool_call_id": str(idx),
            "role": "function",
            "name": tool_calls[idx-1]["function_name"],
            "content": f"Tool Response: {response}",
        })

async def run_function_async(function_name: str, arguments: Dict[str, Any], query: str) -> Any:
    """
    Dispatches asynchronous function calls based on the provided function name and arguments.
    
    Parameters:
    - function_name: The name of the function to call.
    - arguments: The arguments to pass to the function.
    - query: The original query string for context, if applicable.
    
    Returns:
    - The result of the function call.
    """
    function_map = {
        "get_weather_information": weather_api.process_weather_query,
        "search_and_play_song": spotify_client.search_and_play_song,
        "pause_playback": spotify_client.pause_playback,
        "start_playback": spotify_client.start_playback,
    }

    if function_name not in function_map:
        raise ValueError(f"Function {function_name} is not supported.")
    
    # For functions that do not require arguments
    if function_name in ["pause_playback", "start_playback"]:
        return await function_map[function_name]()
    elif function_name == "get_weather_information":
        return await function_map[function_name](query=query, **arguments)
    else:
        return await function_map[function_name](**arguments)


if __name__ == "__main__":
    weather_api = WeatherAPI()
    spotify_client = AsyncSpotifyClient()
    
    asyncio.run(main(weather_api, spotify_client))