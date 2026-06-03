from google import genai
from google.genai import types

import os
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY")) # can do it from .env also
get_weather_fn = types.FunctionDeclaration(
    name="get_weather",
    description="Get the current weather conditions for a specific location.",
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": (
                    "The city and state/country, e.g., 'San Francisco, CA' or 'London, UK'."
                ),
            }
        },
        "required": ["location"],
    },
)

get_stock_price_fn = types.FunctionDeclaration(
    name="get_stock_price",
    description="Get the current stock price for a given ticker symbol.",
    parameters={
        "type": "object",
        "properties": {
            "ticker_symbol": {
                "type": "string",
                "description": "The stock ticker symbol, e.g., 'GOOGL' or 'AMZN'.",
            }
        },
        "required": ["ticker_symbol"],
    },
)
tool = types.Tool(function_declarations=[get_weather_fn, get_stock_price_fn])

user_prompt_content = types.Content(
    role="user",
    parts=[types.Part.from_text("What's the weather like in London?")],
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[user_prompt_content],
    config=types.GenerateContentConfig(tools=[tool]),
)
# simple code to extract the output of parts -> function call

candidate = response.candidates[0]
parts = candidate.content.parts

function_call_part = next(
    (p for p in parts if p.function_call is not None),
    None,
)

if function_call_part:
    fc = function_call_part.function_call
    print("Function name:", fc.name)
    print("Function args:", fc.args)
    