from mcp.server.fastmcp import FastMCP
import logging

# Initialize FastMCP server
mcp = FastMCP("EmailServer")
logger = logging.getLogger(__name__)

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
