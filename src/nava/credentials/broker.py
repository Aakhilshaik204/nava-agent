import os
from typing import List, Dict, Optional
from nava.core.schemas import AgentState
from nava.credentials.vault import CredentialVault, ScopedCredential

def scope_matches(scope: str, pattern: str) -> bool:
    if pattern == "*" or scope == pattern:
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return scope == prefix or scope.startswith(prefix + ".")
    return False

def is_in_scope_list(scope: str, scope_list: List[str]) -> bool:
    return any(scope_matches(scope, p) for p in scope_list)

class CredentialBroker:
    """
    Acts as the issuing authority for agent credentials (Section 17.2).
    Sits between the Action Gateway and the Credential Vault.
    """
    def __init__(self, vault: CredentialVault):
        self.vault = vault

    def _fetch_root_token(self, service: str) -> str:
        """
        In a production system, this fetches the raw root token from an HSM or Secret Manager.
        For Phase 6, we pull it from the secure environment variables.
        """
        token = os.environ.get(f"{service.upper()}_API_TOKEN")
        if not token:
            raise ValueError(f"No root token configured for service: {service}")
        return token

    def request_credential(self, agent: AgentState, service: str, requested_scope: List[str], active_domain: Optional[str] = None, allowed_domains: Optional[List[str]] = None) -> ScopedCredential:
        """
        Mints a short-lived ScopedCredential for the agent.
        Enforces Section 17.3: requested_scope ⊆ agent.credential_scope ⊆ agent.permission_scope.
        Also enforces Phase 9 Cross-Origin domain bounds if provided.
        """
        # 1. Enforce Section 17.3 Alignment Invariant
        for req_scope in requested_scope:
            if not is_in_scope_list(req_scope, agent.credential_scope):
                raise PermissionError(f"Requested scope '{req_scope}' not in agent's credential_scope.")
            if not is_in_scope_list(req_scope, agent.permission_scope):
                raise PermissionError(f"Agent's credential_scope '{req_scope}' is not a subset of its permission_scope! Broken invariant.")

                
        # 1.5 Phase 9: Cross-Origin Boundary Check
        if allowed_domains and active_domain:
            if active_domain not in allowed_domains:
                raise PermissionError(f"CROSS-ORIGIN LEAK PREVENTED: Active domain '{active_domain}' is not in allowed domains {allowed_domains} for service {service}.")

        # 2. Fetch root token securely
        raw_token = self._fetch_root_token(service)
        
        # 3. Mint short-lived credential (5 mins)
        return self.vault.mint(
            agent_id=agent.agent_id,
            service=service,
            scope=requested_scope,
            raw_token=raw_token,
            ttl_minutes=5
        )

    def revoke_all(self, agent_id: str):
        """
        Revokes all active credentials for an agent. Called during teardown.
        """
        import json
        with open(self.vault.storage_path, "r") as f:
            data = json.load(f)
            
        creds_to_revoke = []
        for cred_id, record in data.items():
            if record.get("agent_id") == agent_id:
                creds_to_revoke.append(cred_id)
                
        for cred_id in creds_to_revoke:
            self.vault.revoke(cred_id)

    def emergency_revoke_all(self):
        """
        Emergency Kill Switch (Section 31.4 & Invariant #18):
        Immediately revokes ALL active credentials across the entire vault.
        """
        import json
        if not os.path.exists(self.vault.storage_path):
            return
        with open(self.vault.storage_path, "r") as f:
            data = json.load(f)
            
        for cred_id in list(data.keys()):
            self.vault.revoke(cred_id)
        print("[CredentialBroker] EMERGENCY STOP: All active credentials across vault revoked.")

    def materialize_for_subprocess(self, credential_id: str) -> str:
        """
        Securely retrieves the raw token for environment injection.
        This ensures the Vault's _get_raw is ONLY called by the Broker.
        """
        return self.vault._get_raw(credential_id)
