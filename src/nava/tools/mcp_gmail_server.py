import asyncio
import os
import sys
import httpx

log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_error.log')


# Provider Brand: Google (Gmail API)
# Verified Destination Origin: https://gmail.googleapis.com
PROVIDER_BRAND = "google"
VERIFIED_API_ORIGIN = "https://gmail.googleapis.com"
ALLOWED_API_HOSTS = frozenset(["gmail.googleapis.com"])

def _verify_destination_brand(target_url: str) -> None:
    """
    Security Invariant: Proves that outgoing credential flows strictly target
    the verified brand endpoint (https://gmail.googleapis.com).
    Blocks token exfiltration and SSRF attacks.
    """
    from urllib.parse import urlparse
    parsed = urlparse(target_url)
    if parsed.scheme != "https":
        raise ValueError(f"Insecure protocol rejected: {parsed.scheme}")
    if parsed.hostname not in ALLOWED_API_HOSTS:
        raise ValueError(
            f"Security policy violation: Egress host '{parsed.hostname}' "
            f"does not match verified provider brand '{PROVIDER_BRAND}' ({ALLOWED_API_HOSTS})."
        )


async def run_server():
    from mcp.server import Server
    import mcp.types as types

    # ── Tool handlers (MCP 2.0.0 constructor-callback API) ──────────────

    async def handle_list_tools(ctx, params):
        return types.ListToolsResult(tools=[
            types.Tool(
                name="search",
                description="Search Gmail messages matching the given query.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Gmail search query string"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Max number of results to return (default 5)"
                        }
                    },
                    "required": ["query"]
                }
            ),
            types.Tool(
                name="read",
                description="Read a specific Gmail message by its ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "The Gmail message ID to read"
                        }
                    },
                    "required": ["message_id"]
                }
            )
        ])

    async def handle_call_tool(ctx, params):
        name = params.name
        arguments = dict(params.arguments) if params.arguments else {}

        # Read and immediately erase the token from the environment
        token = os.environ.get("GMAIL_API_TOKEN", "")
        if token:
            os.environ["GMAIL_API_TOKEN"] = ""

        if not token:
            return types.CallToolResult(content=[
                types.TextContent(type="text", text="Error: GMAIL_API_TOKEN missing from environment.")
            ])

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

        if name == "search":
            query = arguments.get("query", "")
            max_results = arguments.get("max_results", 5)
            endpoint = "/gmail/v1/users/me/messages"
            _verify_destination_brand(f"{VERIFIED_API_ORIGIN}{endpoint}")
            
            async with httpx.AsyncClient(base_url=VERIFIED_API_ORIGIN) as client:
                resp = await client.get(
                    endpoint,
                    headers=headers,
                    params={"q": query, "maxResults": max_results}
                )
            if resp.status_code == 401:
                text = "Error: Unauthorized. Token is invalid or expired."
            elif resp.status_code != 200:
                text = f"Gmail API error {resp.status_code}: {resp.text[:500]}"
            else:
                data = resp.json()
                messages = data.get("messages", [])
                if not messages:
                    text = f"No messages found for query: {query}"
                else:
                    text = f"Found {len(messages)} messages. IDs: {[m['id'] for m in messages]}"
            return types.CallToolResult(content=[types.TextContent(type="text", text=text)])

        elif name == "read":
            message_id = arguments.get("message_id", "")
            endpoint = f"/gmail/v1/users/me/messages/{message_id}"
            _verify_destination_brand(f"{VERIFIED_API_ORIGIN}{endpoint}")
            
            async with httpx.AsyncClient(base_url=VERIFIED_API_ORIGIN) as client:
                resp = await client.get(
                    endpoint,
                    headers=headers
                )
            if resp.status_code != 200:
                text = f"Gmail API error {resp.status_code}: {resp.text[:500]}"
            else:
                data = resp.json()
                text = f"Message Snippet: {data.get('snippet', 'No snippet available.')}"
            return types.CallToolResult(content=[types.TextContent(type="text", text=text)])

        return types.CallToolResult(content=[
            types.TextContent(type="text", text=f"Unknown tool: {name}")
        ])

    # ── Build server with MCP 2.0.0 constructor-callback API ─────────────
    server = Server(
        name="gmail",
        on_list_tools=handle_list_tools,
        on_call_tool=handle_call_tool,
    )

    # ── Run over stdio transport ──────────────────────────────────────────
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except Exception:
        import traceback
        with open(log_file, "w") as f:
            f.write(traceback.format_exc())
        sys.exit(1)
