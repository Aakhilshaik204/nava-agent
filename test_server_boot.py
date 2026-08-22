"""
Standalone smoke-test for mcp_gmail_server.py.
Sends a real MCP initialize request over stdio and checks the server responds.
Does NOT use a real Gmail token — just verifies the server boots and speaks protocol.
Run with: python test_server_boot.py
"""
import sys
import asyncio
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_server_boot():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["src/nava/tools/mcp_gmail_server.py"],
        env={**os.environ, "GMAIL_API_TOKEN": "test_token_not_real"}
    )
    print("[Test] Spawning MCP server subprocess...")
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("[Test] Connected. Calling initialize()...")
                await session.initialize()
                print("[Test] ✅ initialize() SUCCEEDED — server speaks MCP protocol correctly!")

                print("[Test] Calling tools/list...")
                tools = await session.list_tools()
                print(f"[Test] ✅ Tools available: {[t.name for t in tools.tools]}")
    except Exception as e:
        print(f"[Test] ❌ FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_server_boot())
