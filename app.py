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

    # Industry instructions mapped to 6-step ADK flow, split to stay under 100 chars
    industry_prompts = {
        'hospitality': (
            "[System: You are in Hospitality mode. Follow the Guest Verification Policy, "
            "complaint tiers, and offer resolutions. Keep the tone warm, welcoming, and helpful.] "
        ),
        'public_sector': (
            "[System: You are in Public Sector / Government mode. Adapt the flow: "
            "1. Citizen submits query/complaint. "
            "2. Verify identity: Ask for full name, reference/permit number, and email. "
            "3. Categorize query (Tier 0: Info request, Tier 1: Service delay, "
            "Tier 2: Code violation/Permit issue, Tier 3: Critical infrastructure issue). "
            "4. Offer resolution (Tier 3 requires email notification using send_email). "
            "Maintain a formal, professional, and civic-minded tone.] "
        ),
        'hospitals': (
            "[System: You are in Hospital / Healthcare mode. Adapt the flow: "
            "1. Patient submits query/complaint. "
            "2. Verify identity: Ask for full name, patient ID/DOB, and email. "
            "3. Categorize query (Tier 0: General info, Tier 1: Appointment scheduling, "
            "Tier 2: Billing discrepancy, Tier 3: Urgent medical record request / patient "
            "complaint). "
            "4. Offer resolution (Tier 3 requires email notification using send_email). "
            "Be extremely empathetic, professional, and maintain confidentiality. "
            "Never offer medical diagnoses.] "
        ),
        'manufacturing': (
            "[System: You are in Manufacturing / Supply Chain mode. Adapt the flow: "
            "1. Supplier/Manager submits query (parts, logistics, maintenance). "
            "2. Verify identity: Ask for full name, supplier/order number, and email. "
            "3. Categorize issue (Tier 0: Status request, Tier 1: Delay, "
            "Tier 2: Defect/shipment error, Tier 3: Production line stoppage/critical dispute). "
            "4. Offer resolution (Tier 3 requires email notification using send_email). "
            "Keep the tone operational, metrics-driven, and focused on logistics.] "
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
