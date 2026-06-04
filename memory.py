import os
import pickle
import numpy as np
import logging
from google import genai
from google.adk.agents.llm_agent import LlmAgent
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.adk.memory.base_memory_service import BaseMemoryService, SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.sessions import Session
from google.adk.runners import Runner
from google.adk.tools import preload_memory

logger = logging.getLogger(__name__)

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

def search_policies(query: str) -> str:
    """Searches the company knowledge base for refund policies, verification guidelines, and compensation tiers using vector similarity.
    
    Args:
        query: The search query (e.g., 'refund policy for Tier 3' or 'how to verify customer').
        
    Returns:
        A list of matching policy articles.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
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

    scored = []
    for p in POLICIES:
        try:
            p_resp = client.models.embed_content(
                model="text-embedding-004",
                contents=p["content"]
            )
            p_emb = np.array(p_resp.embeddings[0].values)
            dot = np.dot(query_emb, p_emb)
            similarity = dot / (np.linalg.norm(query_emb) * np.linalg.norm(p_emb))
            scored.append((similarity, p))
        except Exception as e:
            logger.error(f"Error embedding policy: {e}")
            
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
session_service = DatabaseSessionService(db_url="sqlite:///sessions.db")
memory_service = VectorMemoryService()

# Define the companion agent
companion_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="companion_agent",
    instruction="""You are the AI Companion, a warm, empathetic, and highly capable digital assistant. Your mission is to turn a stressful support experience into a seamless and reassuring journey for every guest.

You guide guests through a simple, 6-step resolution path, ensuring they feel heard and valued at every turn:

1. **Listen with Empathy:** When a guest shares a concern, acknowledge their feelings first. Let them know you're here to help.
2. **Seamless Verification:** Gently ask for their full name, booking confirmation number, and email. Explain that this helps you retrieve their specific details to provide better service.
3. **Smart Categorization:** Behind the scenes, use the `search_policies` tool to understand the situation's tier (0, 1, 2, or 3).
4. **Tailored Resolutions:** Based on the policy, offer clear and fair compensation options. Explain the 'why' behind the offer to build trust.
5. **Empowered Selection:** Let the guest choose the option that feels right for them.
6. **Graceful Closing:** Confirm the details, express your sincere hope that the resolution helps, and close the ticket with a friendly note.

**Key Guidelines:**
* Always use `search_policies` to stay aligned with official guidelines.
* For Tier 3 (Major Disruption) issues, you MUST use the `send_email` tool. Write the email with deep empathy, acknowledging the significant impact on their plans and clearly outlining the resolution.
* Use `get_weather` or `get_stock_price` only if it adds a thoughtful, personal touch to the conversation.
* Keep your tone professional yet approachable, and always prioritize the guest's peace of mind.
""",
    tools=[preload_memory, search_policies, send_email, get_weather, get_stock_price]
)

# Initialize the persistent Runner
runner = Runner(
    agent=companion_agent,
    app_name="Demo_App",
    session_service=session_service,
    memory_service=memory_service
)
