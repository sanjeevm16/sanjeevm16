# Migration Plan: ADK to LangChain/LangGraph

This document outlines the strategy for migrating the AI Companion Agent from the Google Agent Development Kit (ADK) to a LangChain and LangGraph-based architecture.

## 1. Objectives
*   **Stateful Orchestration**: Replace the linear instruction-based flow with a formal State Machine.
*   **Explicit Logic**: Decouple verification, triage, and resolution into distinct, testable nodes.
*   **Native Persistence**: Utilize LangGraph's checkpointer for robust session management.
*   **Ecosystem Compatibility**: Enable easier integration with the broader LangChain toolset.

## 2. Architecture Overview

### State Definition (`AgentState`)
We will track the following variables in the graph state:
*   `messages`: The full conversation history.
*   `industry`: Current industry persona (Hospitality, Healthcare, etc.).
*   `user_info`: Extracted details (Name, Email, Booking ID).
*   `is_verified`: Boolean flag indicating if the guest has provided all required info.
*   `complaint_tier`: The identified severity (0-3).
*   `resolution_offered`: Boolean flag to track if a solution has been presented.

### Graph Nodes
1.  **`gatekeeper`**: Analyzes the latest message to see if the user has provided verification details. Updates `user_info` and `is_verified`.
2.  **`policy_expert`**: If verified, calls the `search_policies` tool to identify the tier and relevant policy text.
3.  **`responder`**: Generates the final message to the user based on the current state (asking for info, offering resolution, or closing).
4.  **`action_worker`**: A tool-execution node for side effects like `send_email`.

### Graph Transitions (Edges)
*   `START` -> `gatekeeper`
*   `gatekeeper` -> `policy_expert` (if verified and tier unknown)
*   `gatekeeper` -> `responder` (if info still missing)
*   `policy_expert` -> `responder`
*   `responder` -> `action_worker` (if Tier 3 action required)
*   `action_worker` -> `END`

## 3. Tool Porting
The following tools from `memory.py` will be wrapped as `@tool`:
*   `search_policies` (Vector search for compensation tiers)
*   `send_email` (Empathy-focused email for Tier 3)
*   `get_weather` / `get_stock_price` (Personalization tools)

## 4. Implementation Steps
1.  **Environment Setup**: Install `langchain`, `langgraph`, and `langchain-google-genai`.
2.  **State & Tools**: Define the `AgentState` schema and wrap existing tools.
3.  **Graph Construction**: Define node functions and compile the `StateGraph`.
4.  **Integration**: Update `app.py` to optionally use the LangGraph agent for chat requests.
5.  **Validation**: Test the 6-step flow (Verification -> Triage -> Resolution).
