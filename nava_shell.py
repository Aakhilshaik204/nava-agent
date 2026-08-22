import os
import sys
import getpass
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.abspath("src"))
from nava.orchestrator import Orchestrator

def main():
    print("========================================")
    print("             Nava OS Shell              ")
    print("========================================")
    print("Welcome to the Nava Agentic OS.")
    print("You can ask for file creation, code searches, or MCP integrations (like Gmail).")
    print("\n[SECURITY DISCLAIMER]")
    print("DEV-ONLY BOOTSTRAP: Raw token entry below is for local testing only.")
    print("Production uses a Broker-mediated OAuth flow, not raw terminal entry.")
    print("========================================\n")
    print("Press Ctrl+C or type 'exit' to quit.\n")

    # Prompt for Gmail token once per session if not in env (using getpass to prevent echo)
    token = os.environ.get("GMAIL_API_TOKEN")
    if not token:
        print("To use Gmail MCP tools, you need a valid access token (https://developers.google.com/oauthplayground/).")
        token = getpass.getpass("Enter Gmail Access Token (ya29...) or press Enter to skip: ").strip()
        if token:
            os.environ["GMAIL_API_TOKEN"] = token

    orchestrator = Orchestrator()

    # Display Project Context Continuity Banner if available
    if hasattr(orchestrator, "workspace"):
        welcome_banner = orchestrator.workspace.get_welcome_back_message()
        if welcome_banner:
            print(f"\n{welcome_banner}\n")

    while True:
        try:
            query = input("\n[Nava] What is your objective? > ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit"]:
                break
            if query.lower() in ["continue", "resume"]:
                active_obj = orchestrator.workspace.get_active_objective()
                if active_obj:
                    query = f"Resume and continue next steps for: {active_obj}"
                    print(f"\n[Context Continuity] Resuming objective: {active_obj}")
                else:
                    print("[Context Continuity] No unfinished objective found. Please enter a new goal.")
                    continue
                
            orchestrator.execute(query)
            
        except KeyboardInterrupt:
            print("\nExiting Nava OS.")
            break
        except Exception as e:
            print(f"\n[Fatal Error] {e}")

if __name__ == "__main__":
    main()
