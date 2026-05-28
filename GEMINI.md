# AI Companion Agent (Python)

This project is a Flask-based AI companion application that utilizes the **Google Agent Development Kit (ADK)**. It features an intelligent agent capable of guest verification, complaint categorization based on internal policies, and resolution offering, all while maintaining a persistent conversation memory.

## Project Overview

-   **Backend:** A Flask application (`app.py`) providing a web interface and a `/chat` API endpoint.
-   **AI Engine:** Powered by Google's Gemini models via the ADK.
-   **Agent Architecture:**
    -   `character.py`: Defines a basic `LlmAgent` with a friendly personality.
    -   `memory.py`: Implements a more advanced `Runner` with vector-based memory and specialized tools.
-   **Core Features:**
    -   **Guest Verification:** Follows a structured flow to verify identity.
    -   **Policy Search:** Uses vector similarity to search a knowledge base of compensation policies.
    -   **Long-Term Memory:** Employs `VectorMemoryService` with Gemini embeddings to remember past interactions across sessions.
    -   **Session Management:** Uses SQLite for persistent session storage.
-   **Frontend:** A modern web UI (`static/app.js`) with voice synthesis and lip-syncing animations.

## Architecture & Technologies

-   **Framework:** Flask (Python)
-   **AI SDK:** `google-adk`, `google-genai`
-   **Models:** `gemini-2.5-flash` (Conversational), `text-embedding-004` (Embeddings)
-   **Database:** SQLite (`sessions.db`)
-   **Storage:** Local pickle file (`vector_memories.pkl`) for vector embeddings.
-   **Frontend:** Vanilla JavaScript, SpeechSynthesis API for voice.

## Getting Started

### Prerequisites

-   Python 3.10+
-   Google Cloud Project with Generative AI API enabled.
-   `gcloud` CLI authenticated.

### Installation

1.  **Environment Setup:**
    ```bash
    bash init.sh          # Set your Google Cloud Project ID
    source set_env.sh     # Export environment variables (Project ID, API Key, etc.)
    ```
2.  **Install Dependencies:**
    ```bash
    pip install flask google-adk google-genai numpy
    ```

### Running the Application

Start the Flask server:
```bash
python app.py
```
The application will be available at `http://127.0.0.1:5000`.

> **Note:** The `index.html` file appears to be missing from the `templates/` directory in the current workspace. Ensure it is restored to run the full web UI.

## Development Conventions

-   **Agent Definition:** Agents should be defined using ADK's `LlmAgent`.
-   **Tools:** Extend agent capabilities by adding functions to the `tools` list in `LlmAgent`. See `memory.py` for examples like `search_policies`.
-   **Memory:** Custom memory services should inherit from `BaseMemoryService`.
-   **Scripts:** Use `init.sh` and `set_env.sh` for consistent environment configuration.

## Key Files

-   `app.py`: Flask entry point and route definitions.
-   `memory.py`: Core ADK configuration including `Runner`, `MemoryService`, and `search_policies` tool.
-   `character.py`: Alternate agent definition.
-   `static/app.js`: Frontend logic for chat interface and voice.
-   `init.sh` / `set_env.sh`: Project initialization and environment setup.
