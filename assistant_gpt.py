#assistant_gpt.py

import asyncio
from openai import AsyncOpenAI  # Ensure you have an asynchronous OpenAI client
import os
# Ideally your openai_api_key should be stored as an environment variable
# Replace OPENAI_API_KEY with os.environ.get("OPENAI_API_KEY")
from configure import user_name, prompt, tools  # Import your configuration
import sys
import json
import re
import backoff
from openai import OpenAIError, APIError
# Set event loop policy on Windows
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class GPTAssistant:
    def __init__(self, ai_model="gpt-3.5-turbo-0125"):
        self.model = ai_model
        # Replace OPENAI_API_KEY with os.environ.get("OPENAI_API_KEY")
        self.openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY")) 
        self.messages = [prompt,]  # Initialize messages with the starting prompt
        self.assistant_reply = ""
        self.is_tool_called = False
        self.tools_called=None
    async def parse_to_json(self, input_str):
        pattern = re.compile(r'(\w+)\s*({.*?})(?=\w+\s*{|\Z)', re.DOTALL)
        data = [
            {
                'function_name': match[0],
                'parameters': json.loads(match[1])
            }
            for match in pattern.findall(input_str)
        ]
        output = {
            "calls": data,
            "tool_call": True
        }

        return output

    async def append_message(self, role=None, message=None):
        print("We are appending something: ",role )
        if role:
            self.messages.append({"role": role, "content": message})
        else:
            self.messages.append(message)

    async def process_transcript(self, transcript):
        await self.append_message("user", transcript)
        async for response_chunk in self.get_response_from_openai():
            yield response_chunk
    @backoff.on_exception(backoff.expo,
                          (OpenAIError, APIError),  # Retry on general API errors as well
                          max_tries=5,)
    async def get_response_from_openai_with_retry(self):
        try:
            stream = await self.openai_client.chat.completions.create(
                model=self.model,
                tools=tools,
                temperature=0.8,
                messages=self.messages,
                tool_choice="auto",
                max_tokens=3000,
                stream=True,
            )
            return stream
        except APIError as e:
            print(f"API error occurred: {e}")
            raise
        except OpenAIError as e:
            print(f"OpenAI error occurred: {e}")
            raise

    async def get_response_from_openai(self):
        self.is_tool_called=False
        # Replace your existing get_response_from_openai with a call to the new method
        stream = await self.get_response_from_openai_with_retry()

        chunk_content = ""  # Initialize chunk_content outside of the loop for tool_calls handling
        async for chunk in stream:
        
        #Handle regular assistant response
            if chunk.choices[0].delta.content is not None:
                
                chunk_content = chunk.choices[0].delta.content
                #print(chunk_content, end="", flush=True)
                yield chunk_content
                self.assistant_reply += chunk_content
                
            #Handle tool call with no yielding
            elif chunk.choices[0].delta.tool_calls:
                # Handle the tool_calls without yielding
                for tool_call in chunk.choices[0].delta.tool_calls:
                    if tool_call.function.name: 
                        self.is_tool_called=True
                        chunk_content += tool_call.function.name
                    chunk_content += str(tool_call.function.arguments)  # Convert arguments to string for concatenation
            
                    
        #print(chunk_content)
        # Append any accumulated tool call data to assistant reply after processing all chunks
        if self.assistant_reply and not self.is_tool_called:
            await self.append_message("assistant", self.assistant_reply)
        elif chunk_content and self.is_tool_called:
            self.tools_called=await self.parse_to_json(chunk_content)
            #print(self.tools_called["calls"])
        self.assistant_reply=""

# Modified main function to handle multiple transcripts concurrently
async def main():
    gpt_processor = GPTAssistant()  # Instantiate a single GPTProcessor
    transcripts = ["How are you doing?", "What is the weather like?", "Tell me a joke."]  # List of transcripts

    # Create a list of tasks, each processing a different transcript
    tasks = [asyncio.create_task(process_transcript_concurrently(gpt_processor, transcript)) for transcript in transcripts]

    # Wait for all tasks to complete
    await asyncio.gather(*tasks)

async def process_transcript_concurrently(gpt_processor, transcript):
    async for response in gpt_processor.process_transcript(transcript):
        print(f"{response}", end = "", flush=True)

# Run the modified main function in the asyncio event loop
if __name__ == "__main__":
    asyncio.run(main())