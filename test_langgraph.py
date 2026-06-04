import asyncio
import os
from langgraph_agent import langgraph_app
from langchain_core.messages import HumanMessage

def print_content(content):
    if isinstance(content, str):
        print(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and "text" in part:
                print(part["text"], end="")
            else:
                print(part, end="")
        print()
    else:
        print(content)

async def main():
    print("--- Starting LangGraph Agent Test ---")
    
    # Configuration for the session
    config = {"configurable": {"thread_id": "test_session_123"}}
    
    # Initial state
    initial_state = {
        "messages": [HumanMessage(content="Hi, I have a complaint about my room. It was very noisy.")],
        "industry": "Hospitality",
        "is_verified": False,
        "user_info": {},
        "complaint_tier": None,
        "policy_context": ""
    }
    
    print("\n[User]: Hi, I have a complaint about my room. It was very noisy.")
    
    # Run the graph
    async for event in langgraph_app.astream(initial_state, config, stream_mode="values"):
        pass
             
    final_state = await langgraph_app.aget_state(config)
    print("\n[Agent]: ", end="")
    print_content(final_state.values['messages'][-1].content)
    
    # Simulate verification
    verification_message = HumanMessage(content="My name is John Doe, booking ID 98765, email john@example.com")
    print(f"\n[User]: {verification_message.content}")
    
    async for event in langgraph_app.astream({"messages": [verification_message]}, config, stream_mode="values"):
        pass
        
    final_state = await langgraph_app.aget_state(config)
    print("\n[Agent]: ", end="")
    print_content(final_state.values['messages'][-1].content)
    print(f"\nVerified: {final_state.values.get('is_verified')}")
    print(f"Tier: {final_state.values.get('complaint_tier')}")

if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY not set.")
    else:
        asyncio.run(main())
