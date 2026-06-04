import os
import logging
from typing import Annotated, List, Optional, TypedDict, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
import numpy as np

logger = logging.getLogger(__name__)

# --- Configuration & Models ---
API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash" 

llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=API_KEY)
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2", google_api_key=API_KEY)

# --- Data & Tools (Ported from memory.py) ---

POLICIES = [
    {
        "title": "Guest Verification Policy",
        "content": "To verify a guest's identity, the guest must provide their full name, booking confirmation number, and email address. Once provided, check database/records and retrieve any open case details."
    },
    {
        "title": "Complaint Tier 0: Minor Preference",
        "content": "Tier 0 is for minor preferences. Definition: Small disruptions based on personal guest preference with minimal overall impact. Compensation: Sincere apology, logging the preference for future bookings, and no financial compensation."
    },
    {
        "title": "Complaint Tier 1: Minor Inconvenience",
        "content": "Tier 1 is for minor inconveniences. Definition: Small disruptions such as delayed activity start time. Compensation: A complimentary beverage, $10 service credit, or simple free amenity."
    },
    {
        "title": "Complaint Tier 2: Moderate Disruption",
        "content": "Tier 2 is for moderate disruptions. Definition: Booking errors or noticeable service dissatisfaction. Compensation: A 20% partial refund or a free meal/local activity voucher."
    },
    {
        "title": "Complaint Tier 3: Major Disruption",
        "content": "Tier 3 is for major disruptions. Definition: Activity cancellations or situations with significant guest impact. Compensation: Full refund, or a rescheduled activity plus a 50% discount voucher on their next booking."
    }
]

# Pre-calculate embeddings for policies
POLICY_EMBEDDINGS = []
try:
    for p in POLICIES:
        emb = np.array(embeddings.embed_query(p["content"]))
        POLICY_EMBEDDINGS.append(emb)
    logger.info("Policy embeddings pre-calculated.")
except Exception as e:
    logger.warning(f"Failed to pre-calculate embeddings: {e}. Fallback to runtime embedding.")

@tool
def search_policies(query: str) -> str:
    """Searches the company knowledge base for refund policies and compensation tiers."""
    try:
        query_emb = np.array(embeddings.embed_query(query))
        scored = []
        for i, p in enumerate(POLICIES):
            if i < len(POLICY_EMBEDDINGS):
                p_emb = POLICY_EMBEDDINGS[i]
            else:
                p_emb = np.array(embeddings.embed_query(p["content"]))
            
            dot = np.dot(query_emb, p_emb)
            similarity = dot / (np.linalg.norm(query_emb) * np.linalg.norm(p_emb))
            scored.append((similarity, p))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [f"Title: {item['title']}\nContent: {item['content']}" for sim, item in scored if sim >= 0.3]
        return "\n\n".join(results[:3]) if results else "No matching policies found."
    except Exception as e:
        logger.error(f"Error in search_policies: {e}")
        return "Error searching policies."

@tool
def send_email(to_address: str, subject: str, body: str) -> str:
    """Sends an empathetic email to the guest. Required for Tier 3 resolutions."""
    # Simulated email
    print(f"--- LANGGRAPH EMAIL SENT TO {to_address} ---")
    print(f"Subject: {subject}\nBody: {body}\n--------------------------------")
    return f"Email successfully sent to {to_address}."

@tool
def get_weather(location: str) -> str:
    """Get the current weather conditions for a specific location."""
    return f"The weather in {location} is currently sunny, 22°C."

tools = [search_policies, send_email, get_weather]
tool_node = ToolNode(tools)
llm_with_tools = llm.bind_tools(tools)

# --- State Definition ---

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    industry: str
    is_verified: bool
    user_info: Dict[str, str]
    complaint_tier: Optional[int]
    policy_context: str

# --- Node Functions ---

def get_text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
    return str(content)

async def gatekeeper(state: AgentState):
    """Checks for verification and extracts user info."""
    messages = state["messages"]
    
    # System prompt to check verification status
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a verification specialist. 
        Look at the conversation history and identify if the user has provided:
        1. Full Name
        2. Booking Confirmation Number
        3. Email Address
        
        If they have, respond with 'VERIFIED' and then the extracted details in JSON format.
        If any are missing, respond with 'UNVERIFIED' and list what is missing.
        """),
        ("placeholder", "{messages}")
    ])
    
    chain = prompt | llm
    response = await chain.ainvoke({"messages": messages})
    
    # Robust text extraction
    text = get_text_content(response.content).upper()
    is_verified = "VERIFIED" in text and "UNVERIFIED" not in text
    
    return {
        "is_verified": is_verified,
        "messages": [AIMessage(content=f"[System Note: Verification check result: {text}]")] if not is_verified else []
    }

async def policy_expert(state: AgentState):
    """Uses tools to find the correct policy tier."""
    if not state.get("is_verified"):
        return {"messages": [AIMessage(content="I need to verify your details before checking policies.")]}
    
    # Use LLM to decide what to search for
    messages = state["messages"]
    last_human_message = [m for m in messages if isinstance(m, HumanMessage)][-1].content
    
    search_query = f"Policy for: {last_human_message}"
    policy_info = search_policies.invoke(search_query)
    
    # Try to extract tier
    tier = None
    for t in range(4):
        if f"Tier {t}" in policy_info:
            tier = t
            break
            
    return {
        "complaint_tier": tier,
        "policy_context": policy_info
    }

async def responder(state: AgentState):
    """Generates the final warm response to the guest."""
    industry = state.get("industry", "Hospitality")
    is_verified = state.get("is_verified", False)
    tier = state.get("complaint_tier")
    policy = state.get("policy_context", "")
    
    system_instruction = f"""You are the AI Companion in {industry} mode.
    Follow these steps:
    1. If not verified, warmly ask for their Full Name, Booking ID, and Email.
    2. If verified but no tier found, ask for more details about their complaint.
    3. If tier found ({tier}), offer the resolution from the policy: {policy}.
    4. For Tier 3, mention that an email will be sent for confirmation.
    
    Tone: Warm, empathetic, and professional.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        ("placeholder", "{messages}")
    ])
    
    chain = prompt | llm_with_tools
    response = await chain.ainvoke({"messages": state["messages"]})
    
    return {"messages": [response]}

# --- Graph Definition ---

def should_continue(state: AgentState):
    """Determines the next node based on verification status."""
    if not state.get("is_verified"):
        return "responder"
    if state.get("complaint_tier") is None:
        return "policy_expert"
    return "responder"

workflow = StateGraph(AgentState)

workflow.add_node("gatekeeper", gatekeeper)
workflow.add_node("policy_expert", policy_expert)
workflow.add_node("responder", responder)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "gatekeeper")
workflow.add_conditional_edges("gatekeeper", should_continue)
workflow.add_edge("policy_expert", "responder")

# Responder might call tools (like send_email)
def route_tools(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow.add_conditional_edges("responder", route_tools)
workflow.add_edge("tools", "responder")

# Compile
graph_checkpointer = MemorySaver()
langgraph_app = workflow.compile(checkpointer=graph_checkpointer)

logger.info("LangGraph agent compiled successfully.")
