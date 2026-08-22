import os
import sys

import asyncio
from nava.orchestrator import Orchestrator
from nava.core.schemas import ToolRequest

def main():
    print("========================================")
    print("   Nava Phase 6: Real MCP Integration   ")
    print("========================================")
    print("\nTo test this for real, you need a valid Gmail Access Token.")
    print("You can generate one quickly here: https://developers.google.com/oauthplayground/")
    print(" 1. Select 'Gmail API v1' -> 'https://www.googleapis.com/auth/gmail.readonly'")
    print(" 2. Click 'Authorize APIs' and log in to your Google Account.")
    print(" 3. Click 'Exchange authorization code for tokens'.")
    print(" 4. Copy the 'Access token' and paste it below.\n")
    
    token = input("Enter your Gmail Access Token: ").strip()
    if not token:
        print("Token is required. Exiting.")
        return

    # Use the token in the environment just like our pipeline expects
    os.environ["GMAIL_API_TOKEN"] = token
    query = input("Enter a Gmail search query (e.g., 'from:github'): ").strip()
    if not query:
        query = "from:github"

    print("\n[Orchestrator] Bootstrapping...")
    orchestrator = Orchestrator()
    
    print(f"\n[Planner] Planning goal: '{query}'...")
    agent_specs = orchestrator.planner.plan(query, orchestrator.root_agent.agent_id)
    
    # We will grab the first agent spec that requires gmail
    spec = next((s for s in agent_specs if "gmail.search" in s.requested_tools), None)
    if not spec:
        print("Planner didn't request a Gmail agent. Using a default specification.")
        from nava.core.schemas import AgentSpec, Priority
        import datetime
        spec = AgentSpec(
            request_id="req-mcp-test",
            requested_role="DataAgent",
            goal="Test the MCP integration",
            parent_agent_id=orchestrator.root_agent.agent_id,
            requested_tools=["gmail.search"],
            requested_permission_scope=["gmail.read"],
            ttl=datetime.timedelta(minutes=5),
            max_steps=10,
            max_tokens=1000,
            max_children=0,
            priority=Priority.NORMAL,
            dedup_hash="hash"
        )
        
    print(f"[Factory] Spawning agent: {spec.requested_role}")
    child_agent = orchestrator.factory.spawn_agent(spec, orchestrator.root_agent)
    
    # The Vault step: securely minting the user's provided token into the AES encrypted vault
    print("[Vault] Minting and encrypting raw token into the Vault...")
    orchestrator.vault.mint(child_agent.agent_id, "gmail", ["gmail.read"], token)
    
    # Simulate the agent executing a ToolRequest
    print(f"\n[Agent] Requesting tool execution: gmail.search(query='{query}')")
    request = ToolRequest(
        request_id="exec-1",
        agent_id=child_agent.agent_id,
        tool_name="gmail.search",
        arguments={"query": query, "max_results": 3},
        requested_scope="gmail.read"
    )
    
    # Build the isolated Gateway for this agent
    from tests.utils import build_test_gateway
    gateway = build_test_gateway(
        orchestrator.registry, 
        orchestrator.policy, 
        orchestrator.risk, 
        orchestrator.budget_engine, 
        orchestrator.hitl, 
        orchestrator.ledger, 
        child_agent, 
        receipt_store=None,
        concurrency_manager=None,
        credential_broker=orchestrator.credential_broker
    )
    
    # Configure the MCP Client Manager and Executor
    from nava.tools.mcp_client import MCPClientManager
    mcp_manager = MCPClientManager(orchestrator.registry, credential_broker=orchestrator.credential_broker)
    import sys
    mcp_manager.register_server("gmail", sys.executable, ["src/nava/tools/mcp_gmail_server.py"], "gmail")
    
    from nava.tools.executor import LocalToolExecutor
    gateway.executor = LocalToolExecutor(mcp_manager=mcp_manager)
    
    # Fire the request through the Gateway!
    print("\n[Gateway] Intercepting request, verifying policy, and requesting ScopedCredential from Broker...")
    try:
        receipt = gateway.process_request(request)
        
        print("\n================= LIVE RESULTS =================")
        print(f"Status: {receipt.result}")
        print(f"Data: {receipt.result_data}")
        print("================================================\n")
    except Exception as e:
        print(f"\n[Gateway Error]: {e}")
        
    finally:
        # Secure teardown
        print("[Orchestrator] Running Teardown...")
        orchestrator.credential_broker.revoke_all(child_agent.agent_id)
        print("[Vault] Credentials revoked securely.")

if __name__ == "__main__":
    main()
