from flask import Flask, render_template, request, jsonify
from google.adk.runners import InMemoryRunner
from google.genai import types
import os

app = Flask(__name__)


runner = None
memory_exists = os.path.exists('memory.py')
character_exists = os.path.exists('character.py')

if memory_exists:
    import memory
    runner = memory.runner
elif character_exists:
    import character
    runner = InMemoryRunner(
        agent=character.root_agent,
        app_name="Demo App",
    )


@app.route('/')
def index():
    """Renders the main companion chat interface page."""
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
async def chat():
    """Handles conversational chat events and routes them to the ADK agent."""
    user_message = request.json.get('message')
    session_id = request.json.get('session_id', 'default_session')
    industry = request.json.get('industry', 'hospitality')

    if not character_exists:
        return jsonify({'response': user_message})

    # Isolate session memory by industry
    industry_session_id = f"{industry}_{session_id}"

    # Retrieve or create session dynamically
    adk_session = await runner.session_service.get_session(
        app_name=runner.app_name, user_id="inapp_user", session_id=industry_session_id
    )
    if adk_session is None:
        adk_session = await runner.session_service.create_session(
            app_name=runner.app_name, user_id="inapp_user", session_id=industry_session_id
        )

    # Industry-specific persona adjustments that adapt the core 6-step flow
    industry_prompts = {
        'hospitality': (
            "[System: Hospitality Mode. Tone: Warm, welcoming, and helpful. "
            "Focus on 'Guests' and 'Bookings'.] "
        ),
        'public_sector': (
            "[System: Public Sector Mode. Tone: Formal, professional, and civic-minded. "
            "Focus on 'Citizens' and 'Service Requests'. Identity verification: "
            "Full Name, Reference/Permit Number, and Email.] "
        ),
        'hospitals': (
            "[System: Healthcare Mode. Tone: Extremely empathetic and professional. "
            "Focus on 'Patients' and 'Care Quality'. Identity verification: "
            "Full Name, Patient ID/DOB, and Email. Never offer medical diagnoses.] "
        ),
        'manufacturing': (
            "[System: Manufacturing Mode. Tone: Operational, precise, and metrics-driven. "
            "Focus on 'Suppliers/Managers' and 'Logistics/Orders'. Identity verification: "
            "Full Name, Order Number, and Email.] "
        )
    }

    prompt_prefix = industry_prompts.get(industry, industry_prompts['hospitality'])
    message_with_context = f"{prompt_prefix}{user_message}"

    content = types.Content(role="user", parts=[types.Part(text=message_with_context)])
    response_text = ""
    async for event in runner.run_async(
        user_id=adk_session.user_id,
        session_id=adk_session.id,
        new_message=content,
    ):
        if event.content and event.content.parts and event.content.parts[0].text:
            response_text += event.content.parts[0].text

    # Clean up the output if the model parrots back the System tag
    response_text = response_text.replace(prompt_prefix, "").strip()

    return jsonify({'response': response_text})


if __name__ == '__main__':
    app.run(debug=True)