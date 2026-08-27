import os
import sys
import json
import hashlib
import asyncio
import subprocess
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from pydantic import BaseModel

from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.core.schemas import RiskTier

class MCPToolTrustState(str, Enum):
    TRUSTED = "TRUSTED"
    UNTRUSTED_NEW = "UNTRUSTED_NEW"
    UNTRUSTED_MODIFIED = "UNTRUSTED_MODIFIED"


class StdioMCPClient:
    """
    Standard JSON-RPC 2.0 Client communicating over stdio subprocess transport.
    Complies with Model Context Protocol (MCP) specifications.
    """
    def __init__(self, command: str, args: List[str], env: Optional[Dict[str, str]] = None, timeout: float = 15.0):
        self.command = command
        self.args = args or []
        self.env = env or os.environ.copy()
        self.timeout = timeout
        self.process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def start(self):
        full_cmd = [self.command] + self.args
        self.process = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env
        )

    async def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.process or self.process.returncode is not None:
            await self.start()

        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {}
        }
        raw_msg = json.dumps(payload) + "\n"
        
        try:
            self.process.stdin.write(raw_msg.encode("utf-8"))
            await self.process.stdin.drain()
            
            line = await asyncio.wait_for(self.process.stdout.readline(), timeout=self.timeout)
            if not line:
                stderr_data = await self.process.stderr.read()
                raise RuntimeError(f"MCP server terminated unexpectedly. Stderr: {stderr_data.decode('utf-8', errors='ignore')}")
                
            resp = json.loads(line.decode("utf-8").strip())
            if "error" in resp:
                raise RuntimeError(f"MCP JSON-RPC Error: {resp['error']}")
            return resp.get("result", {})
        except asyncio.TimeoutError:
            raise TimeoutError(f"MCP request to method '{method}' timed out after {self.timeout}s")

    async def list_tools(self) -> List[Dict[str, Any]]:
        # Initialize handshake first
        try:
            await self.send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nava-os", "version": "1.0.0"}
            })
        except Exception:
            pass # Some servers accept tools/list directly
            
        result = await self.send_request("tools/list", {})
        return result.get("tools", [])

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        result = await self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        # Extract content text from MCP response format
        contents = result.get("content", [])
        if contents and isinstance(contents, list):
            texts = [c.get("text", "") for c in contents if isinstance(c, dict) and "text" in c]
            if texts:
                return "\n".join(texts)
        return result

    async def close(self):
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception:
                pass


class MCPClientManager:
    """
    Manages registration, discovery, hash-locking verification, and execution of MCP tools.
    Designed for effortless registration of local and remote MCP servers.
    """
    def __init__(self, registry: ToolRegistry, credential_broker: Any = None, ledger_path: str = "memory/trusted_mcp_servers.json"):
        self.registry = registry
        self.credential_broker = credential_broker
        self.ledger_path = ledger_path
        self.ledger: Dict[str, dict] = {}
        self.servers: Dict[str, dict] = {}
        self.pending_tools: Dict[str, Dict[str, dict]] = {} # server_name -> {tool_name -> tool_dict}
        self._load_ledger()

    def _load_ledger(self):
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    self.ledger = json.load(f)
            except Exception as e:
                print(f"[MCPClientManager] Failed to load trusted ledger: {e}")
                self.ledger = {}
        else:
            self.ledger = {}

    def _save_ledger(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.ledger_path)), exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(self.ledger, f, indent=2)

    def _hash_tool_def(self, tool_dict: dict) -> str:
        """Canonicalizes and hashes a tool definition dict."""
        canonical_dict = {
            "name": tool_dict.get("name", ""),
            "description": tool_dict.get("description", ""),
            "input_schema": tool_dict.get("input_schema", {}),
            "permissions_required": tool_dict.get("permissions_required", []),
            "risk_level": tool_dict.get("risk_level", "MEDIUM"),
            "reversible": tool_dict.get("reversible", True),
            "required_credentials": tool_dict.get("required_credentials", [])
        }
        canonical_str = json.dumps(canonical_dict, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def _infer_risk(self, name: str, schema: dict) -> RiskTier:
        lower = (name + " " + json.dumps(schema)).lower()
        if any(w in lower for w in ["delete", "drop", "destroy", "wire", "transfer", "execute", "shell"]):
            return RiskTier.CRITICAL
        elif any(w in lower for w in ["write", "update", "create", "send", "post", "patch", "modify"]):
            return RiskTier.HIGH
        elif any(w in lower for w in ["search", "query", "find", "get", "list", "read", "inspect"]):
            return RiskTier.LOW
        return RiskTier.MEDIUM

    def register_server(
        self, 
        name: str, 
        command: str, 
        args: Optional[List[str]] = None, 
        env: Optional[Dict[str, str]] = None, 
        required_service: Optional[str] = None,
        custom_tools: Optional[List[dict]] = None,
        enabled: bool = True
    ):
        """
        Easy registration API for any MCP Server.
        If enabled is False, the server is ignored and excluded.
        """
        if not enabled:
            return

        self.servers[name] = {
            "type": "local",
            "command": command,
            "args": args or [],
            "env": env or {},
            "required_service": required_service,
            "enabled": True
        }

        # If custom tool schemas were provided explicitly, process them directly
        if custom_tools:
            self._process_fetched_tools(name, custom_tools)
            return

        # Attempt dynamic discovery via JSON-RPC stdio
        try:
            fetched_tools = self._discover_server_tools_sync(name, command, args or [], env or {})
            if fetched_tools:
                self._process_fetched_tools(name, fetched_tools)
        except Exception as e:
            # If server isn't running or stdio discovery fails, fall back to built-in discovery defaults
            print(f"[MCPClientManager] Dynamic tool discovery notice for '{name}': {e}")
            if name == "gmail":
                fallback_tools = [
                    {
                        "name": "gmail.search",
                        "description": "Search Gmail messages using Gmail search syntax.",
                        "input_schema": {"query": "string"},
                        "permissions_required": ["gmail.read"],
                        "risk_level": "MEDIUM",
                        "reversible": True,
                        "required_credentials": ["gmail"]
                    },
                    {
                        "name": "gmail.read",
                        "description": "Read a specific Gmail message by ID.",
                        "input_schema": {"message_id": "string"},
                        "permissions_required": ["gmail.read"],
                        "risk_level": "LOW",
                        "reversible": True,
                        "required_credentials": ["gmail"]
                    }
                ]
                self._process_fetched_tools(name, fallback_tools)

    def _discover_server_tools_sync(self, name: str, command: str, args: List[str], env: dict) -> List[dict]:
        """Synchronously runs async tool discovery."""
        async def _discover():
            client = StdioMCPClient(command, args, env, timeout=5.0)
            try:
                raw_tools = await client.list_tools()
                normalized = []
                for t in raw_tools:
                    raw_name = t.get("name", "")
                    full_name = f"{name}.{raw_name}" if not raw_name.startswith(f"{name}.") else raw_name
                    schema = t.get("inputSchema", t.get("input_schema", {}))
                    risk = self._infer_risk(full_name, schema)
                    req_service = self.servers.get(name, {}).get("required_service")
                    
                    normalized.append({
                        "name": full_name,
                        "raw_name": raw_name,
                        "description": t.get("description", f"MCP tool from {name}"),
                        "input_schema": schema,
                        "permissions_required": [f"{name}.write" if risk in [RiskTier.HIGH, RiskTier.CRITICAL] else f"{name}.read"],
                        "risk_level": risk.value,
                        "reversible": (risk != RiskTier.CRITICAL),
                        "required_credentials": [req_service] if req_service else []
                    })
                return normalized
            finally:
                await client.close()

        return asyncio.run(_discover())

    def _process_fetched_tools(self, server_name: str, fetched_tools: List[dict]):
        server_ledger = self.ledger.get(server_name, {"tools": {}})
        self.pending_tools[server_name] = {}
        
        for tool_dict in fetched_tools:
            tool_name = tool_dict["name"]
            tool_hash = self._hash_tool_def(tool_dict)
            
            if tool_name not in server_ledger.get("tools", {}):
                trust_state = MCPToolTrustState.UNTRUSTED_NEW
            else:
                if server_ledger["tools"][tool_name]["hash"] == tool_hash:
                    trust_state = MCPToolTrustState.TRUSTED
                else:
                    trust_state = MCPToolTrustState.UNTRUSTED_MODIFIED
            
            tool_dict["trust_state"] = trust_state
            self.pending_tools[server_name][tool_name] = tool_dict
            
            if trust_state == MCPToolTrustState.TRUSTED:
                t_def = ToolDefinition(
                    name=tool_dict["name"],
                    description=tool_dict["description"],
                    input_schema=tool_dict["input_schema"],
                    output_schema={"result": "string"},
                    permissions_required=tool_dict["permissions_required"],
                    risk_level=RiskTier(tool_dict["risk_level"]),
                    reversible=tool_dict["reversible"],
                    required_credentials=tool_dict.get("required_credentials", [])
                )
                try:
                    self.registry.get_tool(t_def.name)
                except KeyError:
                    self.registry.register_tool(t_def)
                    print(f"[MCPClientManager] Registered TRUSTED tool (verified: {tool_hash[:8]}): {t_def.name}")

    def get_pending_approvals(self, server_name: str) -> List[dict]:
        """Returns tools that require human approval for a given server."""
        if server_name not in self.pending_tools:
            return []
        return [t for t in self.pending_tools[server_name].values() if t["trust_state"] != MCPToolTrustState.TRUSTED]

    def approve_tool(self, server_name: str, tool_name: str, actor: str = "local_user"):
        if server_name not in self.pending_tools or tool_name not in self.pending_tools[server_name]:
            raise ValueError(f"Tool {tool_name} not pending for server {server_name}")
            
        tool_dict = self.pending_tools[server_name][tool_name]
        tool_hash = self._hash_tool_def(tool_dict)
        
        if server_name not in self.ledger:
            self.ledger[server_name] = {"tools": {}}
            
        canonical_dict = {
            "name": tool_dict.get("name", ""),
            "description": tool_dict.get("description", ""),
            "input_schema": tool_dict.get("input_schema", {}),
            "permissions_required": tool_dict.get("permissions_required", []),
            "risk_level": tool_dict.get("risk_level", "MEDIUM"),
            "reversible": tool_dict.get("reversible", True),
            "required_credentials": tool_dict.get("required_credentials", [])
        }
            
        self.ledger[server_name]["tools"][tool_name] = {
            "hash": tool_hash,
            "last_trusted_content": json.dumps(canonical_dict, indent=2),
            "approved_by": actor
        }
        self._save_ledger()
        
        tool_dict["trust_state"] = MCPToolTrustState.TRUSTED
        
        t_def = ToolDefinition(
            name=tool_dict["name"],
            description=tool_dict["description"],
            input_schema=tool_dict["input_schema"],
            output_schema={"result": "string"},
            permissions_required=tool_dict["permissions_required"],
            risk_level=RiskTier(tool_dict["risk_level"]),
            reversible=tool_dict["reversible"],
            required_credentials=tool_dict.get("required_credentials", [])
        )
        try:
            self.registry.get_tool(t_def.name)
        except KeyError:
            self.registry.register_tool(t_def)
            print(f"[MCPClientManager] Registered newly-approved tool: {t_def.name}")

    def get_ledger_content(self, server_name: str, tool_name: str) -> Optional[str]:
        if server_name in self.ledger and tool_name in self.ledger[server_name].get("tools", {}):
            return self.ledger[server_name]["tools"][tool_name].get("last_trusted_content")
        return None

    async def execute_tool(self, server_name: str, tool_name: str, request: Any) -> Any:
        """Executes a tool on an MCP server via JSON-RPC stdio."""
        server_info = self.servers.get(server_name)
        if not server_info:
            return {"error": f"MCP server '{server_name}' is not registered."}

        command = server_info["command"]
        args = server_info["args"]
        env = dict(server_info.get("env", os.environ))

        # Check if raw tool name is needed (strip prefix if server uses short names)
        raw_name = tool_name
        if tool_name.startswith(f"{server_name}."):
            raw_name = tool_name[len(server_name) + 1:]

        client = StdioMCPClient(command, args, env=env)
        try:
            result = await client.call_tool(raw_name, request.arguments)
            return {"result": result, "status": "executed"}
        except Exception as e:
            return {"error": str(e), "tool": tool_name, "server": server_name}
        finally:
            await client.close()
