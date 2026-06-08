import os
import pickle
import numpy as np
import logging
from typing import AsyncGenerator, Optional
from typing_extensions import override
from google import genai
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents import BaseAgent
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.adk.memory.base_memory_service import BaseMemoryService, SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.sessions import Session, InMemorySessionService
from google.adk.runners import Runner
from google.adk.tools import preload_memory
from google.adk.events import Event

logger = logging.getLogger(__name__)

# Global set for verified sessions (Reliable fallback for demo)
VERIFIED_SESSIONS = set()

# Prepopulated knowledge database policy articles
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

# Global cache for policy embeddings and client
_POLICY_EMBEDDINGS = None
_GENAI_CLIENT = None

def _get_genai_client():
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        _GENAI_CLIENT = genai.Client(api_key=api_key)
    return _GENAI_CLIENT

def _get_policy_embeddings():
    global _POLICY_EMBEDDINGS
    if _POLICY_EMBEDDINGS is not None:
        return _POLICY_EMBEDDINGS
    
    client = _get_genai_client()
    embeddings = []
    logger.info("Generating embeddings for knowledge base policies...")
    for p in POLICIES:
        try:
            response = client.models.embed_content(
                model="text-embedding-004",
                contents=p["content"]
            )
            embeddings.append(np.array(response.embeddings[0].values))
        except Exception as e:
            logger.error(f"Error embedding policy '{p['title']}': {e}")
            embeddings.append(None)
    _POLICY_EMBEDDINGS = embeddings
    return _POLICY_EMBEDDINGS

def search_policies(query: str) -> str:
    """Searches the company knowledge base for refund policies, verification guidelines, and compensation tiers using vector similarity.
    
    Args:
        query: The search query (e.g., 'refund policy for Tier 3' or 'how to verify customer').
        
    Returns:
        A list of matching policy articles.
    """
    client = _get_genai_client()
    try:
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=query
        )
        query_emb = np.array(response.embeddings[0].values)
    except Exception as e:
        logger.error(f"Error embedding query in search_policies: {e}")
        # Fallback to keyword matching
        matches = []
        for p in POLICIES:
            if any(word.lower() in p["content"].lower() or word.lower() in p["title"].lower() for word in query.split()):
                matches.append(f"Title: {p['title']}\nContent: {p['content']}")
        return "\n\n".join(matches) if matches else "No matching policies found."

    policy_embs = _get_policy_embeddings()
    scored = []
    for i, p in enumerate(POLICIES):
        p_emb = policy_embs[i]
        if p_emb is None:
            continue
        try:
            dot = np.dot(query_emb, p_emb)
            similarity = dot / (np.linalg.norm(query_emb) * np.linalg.norm(p_emb))
            scored.append((similarity, p))
        except Exception as e:
            logger.error(f"Error scoring policy: {e}")
            
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [f"Title: {item['title']}\nContent: {item['content']}" for sim, item in scored if sim >= 0.3]
    return "\n\n".join(results[:3]) if results else "No matching policies found."


def get_weather(location: str) -> str:
    """Get the current weather conditions for a specific location.
    
    Args:
        location: The city and state/country, e.g., 'San Francisco, CA' or 'London, UK'.
    """
    # Simulated weather response
    return f"The weather in {location} is currently sunny, 22°C."

def get_stock_price(ticker_symbol: str) -> str:
    """Get the current stock price for a given ticker symbol.
    
    Args:
        ticker_symbol: The stock ticker symbol, e.g., 'GOOGL' or 'AMZN'.
    """
    # Simulated stock price response
    return f"The current stock price for {ticker_symbol} is $150.25."

def send_email(to_address: str, subject: str, body: str) -> str:
    """Sends an email to the specified address. Use this for notifications, especially for Tier 3 policy resolutions.
    
    Args:
        to_address: The recipient's email address.
        subject: The subject of the email.
        body: The body content of the email.
        
    Returns:
        A confirmation message.
    """
    # In a real application, this would use an SMTP library or an email API.
    # For this demo, we will log the email details.
    print(f"SIMULATED EMAIL SENT TO {to_address}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")
    logger.info(f"SIMULATED EMAIL SENT TO {to_address}")
    return f"Email successfully sent to {to_address}."


def mark_as_verified(name: str, booking_id: str, email: str) -> str:
    """Internal tool to mark the guest as verified once all details are provided.
    
    Args:
        name: Guest's full name.
        booking_id: Booking confirmation number.
        email: Guest's email address.
    """
    logger.info(f"EXECUTING mark_as_verified for {name}")
    return f"VERIFICATION_SUCCESS: {name} (ID: {booking_id})"


class VectorMemoryService(BaseMemoryService):
    """A vector-based memory service using Gemini text-embedding-004 and local pickle persistence."""
    
    def __init__(self, filepath="vector_memories.pkl", embedding_model="text-embedding-004"):
        self.filepath = filepath
        self.embedding_model = embedding_model
        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.memories = []
        self.loaded_session_ids = set()
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "rb") as f:
                    data = pickle.load(f)
                    self.memories = data.get("memories", [])
                    self.loaded_session_ids = data.get("loaded_session_ids", set())
            except Exception as e:
                logger.error(f"Error loading vector memories: {e}")

    def save(self):
        try:
            with open(self.filepath, "wb") as f:
                pickle.dump({
                    "memories": self.memories,
                    "loaded_session_ids": self.loaded_session_ids
                }, f)
        except Exception as e:
            logger.error(f"Error saving vector memories: {e}")

    async def add_session_to_memory(self, session: Session):
        for event in session.events:
            if not event.content or not event.content.parts:
                continue
            text = " ".join([part.text for part in event.content.parts if part.text]).strip()
            if not text:
                continue
            
            event_id = f"{session.id}_{event.timestamp}_{event.author}"
            if event_id in self.loaded_session_ids:
                continue

            try:
                response = self.client.models.embed_content(
                    model=self.embedding_model,
                    contents=text
                )
                embedding = response.embeddings[0].values
                entry = MemoryEntry(
                    content=event.content,
                    author=event.author,
                    timestamp=event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp)
                )
                self.memories.append({
                    "text": text,
                    "embedding": embedding,
                    "entry": entry
                })
                self.loaded_session_ids.add(event_id)
            except Exception as e:
                logger.error(f"Error embedding text '{text}': {e}")
        
        self.save()

    async def search_memory(self, *, app_name: str, user_id: str, query: str) -> SearchMemoryResponse:
        if not self.memories:
            return SearchMemoryResponse()

        try:
            response = self.client.models.embed_content(
                model=self.embedding_model,
                contents=query
            )
            query_embedding = np.array(response.embeddings[0].values)
        except Exception as e:
            logger.error(f"Error embedding query '{query}': {e}")
            return SearchMemoryResponse()

        scored_memories = []
        for item in self.memories:
            item_embedding = np.array(item["embedding"])
            dot_product = np.dot(query_embedding, item_embedding)
            norm_q = np.linalg.norm(query_embedding)
            norm_i = np.linalg.norm(item_embedding)
            similarity = dot_product / (norm_q * norm_i) if norm_q > 0 and norm_i > 0 else 0.0
            scored_memories.append((similarity, item["entry"]))

        scored_memories.sort(key=lambda x: x[0], reverse=True)
        threshold = 0.4
        results = [entry for similarity, entry in scored_memories if similarity >= threshold]
        
        return SearchMemoryResponse(memories=results[:5])


# Instantiate Session and Memory services
session_service = InMemorySessionService()
memory_service = VectorMemoryService()

# 1. Verification Agent: Dedicated to identifying the guest.
verification_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="verification_agent",
    instruction="""You are the Verification Assistant. Your sole mission is to verify the guest's identity.
Gently ask for their full name, booking confirmation number, and email. 
Explain that this is necessary to retrieve their details and provide accurate service.
Once you have all three pieces of information, YOU MUST call the `mark_as_verified` tool to record the verification in the system state.
ONLY after the tool returns success should you confirm verification to the user.
Do not discuss policies or offer refunds yourself; focus only on identity verification. 
If the user asks about their complaint, remind them that you first need to verify their identity.""",
    tools=[mark_as_verified]
)

# 2. Resolution Agent: Dedicated to resolving complaints based on policies.
resolution_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="resolution_agent",
    instruction="""You are the Resolution Specialist. You handle guests who have already been verified.
Your goal is to guide the guest through a fair resolution process:
1. **Listen & Categorize:** Use `search_policies` to understand the complaint tier (0-3).
2. **Offer Options:** Based on the policy, provide clear and empathetic compensation choices.
3. **Confirm & Execute:** Once chosen, confirm details. For Tier 3, you MUST use `send_email`.
4. **Graceful Closing:** End the interaction with a friendly, reassuring note.

Always refer to the guest by the name stored in the session state if available.
Keep your tone warm, professional, and solution-oriented.""",
    tools=[search_policies, send_email, get_weather, get_stock_price]
)

class CompanionWorkflow(BaseAgent):
    """Custom orchestrator that routes between Verification and Resolution agents."""
    
    verification_agent: LlmAgent
    resolution_agent: LlmAgent
    
    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, verification_agent: LlmAgent, resolution_agent: LlmAgent):
        super().__init__(
            name=name,
            verification_agent=verification_agent,
            resolution_agent=resolution_agent,
            sub_agents=[verification_agent, resolution_agent]
        )

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # Check if guest is already verified in this session
        session_key = f"{ctx.session.app_name}_{ctx.session.user_id}_{ctx.session.id}"
        is_verified = ctx.session.state.get("is_verified", False) or session_key in VERIFIED_SESSIONS
        
        # Double check history
        if not is_verified:
            for event in ctx.session.events:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text and "VERIFICATION_SUCCESS" in part.text:
                            logger.info(f"[{self.name}] Verification detected in history. Updating state.")
                            ctx.session.state["is_verified"] = True
                            VERIFIED_SESSIONS.add(session_key)
                            is_verified = True
                            break
                if is_verified: break

        logger.info(f"[{self.name}] Current verification state: {is_verified} for {session_key}")
        
        if not is_verified:
            logger.info(f"[{self.name}] Routing to VerificationAgent.")
            async for event in self.verification_agent.run_async(ctx):
                # Update state immediately if tool response is seen in the stream
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text and "VERIFICATION_SUCCESS" in part.text:
                            logger.info(f"[{self.name}] Verification detected in stream. Updating state.")
                            ctx.session.state["is_verified"] = True
                            VERIFIED_SESSIONS.add(session_key)
                yield event
        else:
            logger.info(f"[{self.name}] Guest verified. Routing to ResolutionAgent.")
            async for event in self.resolution_agent.run_async(ctx):
                yield event

# Instantiate the workflow agent
companion_workflow = CompanionWorkflow(
    name="companion_workflow",
    verification_agent=verification_agent,
    resolution_agent=resolution_agent
)

# Initialize the persistent Runner with the workflow agent
runner = Runner(
    agent=companion_workflow,
    app_name="Demo_App",
    session_service=session_service,
    memory_service=memory_service
)
