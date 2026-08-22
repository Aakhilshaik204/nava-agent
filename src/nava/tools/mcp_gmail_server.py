import asyncio
import os
import sys
import httpx

log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_error.log')


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
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages",
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
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
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
