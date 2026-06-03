from mcp.server.fastmcp import FastMCP
import logging

# Initialize FastMCP server
mcp = FastMCP("EmailServer")
logger = logging.getLogger(__name__)

@mcp.tool()
def get_weather(location: str) -> str:
    """
    Get the current weather conditions for a specific location.
    """
    return f"The weather in {location} is currently sunny, 22°C (via MCP Server)."

@mcp.tool()
def get_stock_price(ticker_symbol: str) -> str:
    """
    Get the current stock price for a given ticker symbol.
    """
    return f"The current stock price for {ticker_symbol} is $150.25 (via MCP Server)."

@mcp.tool()
def send_email(to_address: str, subject: str, body: str) -> str:
    """
    Sends an email to the specified address with a soft and professional tone.
    Used for policy notifications and guest communications.
    """
    # Simulated email sending logic
    print(f"MCP SERVER: SIMULATED EMAIL SENT TO {to_address}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")
    return f"Email successfully sent to {to_address} via MCP Server."

if __name__ == "__main__":
    mcp.run()
