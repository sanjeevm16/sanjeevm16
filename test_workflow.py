import asyncio
import logging
import os
from google.genai import types
from memory import runner

# Configure logging to see the routing transitions
logging.basicConfig(level=logging.INFO)

async def test_multi_agent_flow():
    session_id = "test_session_multi_agent_003"
    user_id = "test_user_001"
    app_name = "Demo_App"

    print("\n--- Starting Test: Multi-Agent Workflow ---\n")

    # Explicitly create session first to avoid SessionNotFoundError
    session = await runner.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
    if not session:
        print(f"Creating session: {session_id}")
        await runner.session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)

    def print_events(events):
        pass # Helper moved inside loop

    # Step 1: Initial contact
    print("User: Hi, I'm really upset about my booking.")
    content = types.Content(role="user", parts=[types.Part(text="Hi, I'm really upset about my booking.")])
    
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"DEBUG: Model calling tool: {part.function_call.name}")
        if event.is_final_response() and event.content and event.content.parts:
            print(f"Agent: {event.content.parts[0].text}\n")

    # Step 2: Provide verification details
    print("User: My name is John Doe, booking ID is BK123, and email is john@example.com.")
    content = types.Content(role="user", parts=[types.Part(text="My name is John Doe, booking ID is BK123, and email is john@example.com.")])
    
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"DEBUG: Model calling tool: {part.function_call.name} with {part.function_call.args}")
        if event.is_final_response() and event.content and event.content.parts:
            print(f"Agent: {event.content.parts[0].text}\n")

    # Step 3: Now ask about the complaint
    print("User: My activity was cancelled last minute. What can you do for me?")
    content = types.Content(role="user", parts=[types.Part(text="My activity was cancelled last minute. What can you do for me?")])
    
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"DEBUG: Model calling tool: {part.function_call.name}")
        if event.is_final_response() and event.content and event.content.parts:
            print(f"Agent: {event.content.parts[0].text}\n")

if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY environment variable not set.")
    else:
        asyncio.run(test_multi_agent_flow())
