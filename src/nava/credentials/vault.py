import os
import json
import uuid
import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel

try:
    from cryptography.fernet import Fernet
except ImportError:
    # If cryptography is not installed, fail securely. We want REAL encryption, not fakes.
    raise ImportError("The 'cryptography' package is required for real AES encryption in the Vault. Please run: pip install cryptography")

class ScopedCredential(BaseModel):
    credential_id: str
    service: str
    scope: List[str]
    issued_at: datetime.datetime
    expires_at: datetime.datetime
    agent_id: str
    # IMPORTANT: The raw token is structurally omitted from this schema.

class CredentialVault:
    """
    Encrypted-at-rest storage for sensitive tokens.
    Enforces Section 17.1: No raw token exposure to callers outside the Broker/MCP layer.
    """
    def __init__(self, storage_path: str = "memory/vault.json", key_path: str = ".vault_key"):
        self.storage_path = storage_path
        self.key_path = key_path
        self._ensure_storage_dirs()
        self._load_or_generate_key()
        self.fernet = Fernet(self.key)
        self._ensure_storage()

    def _ensure_storage_dirs(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def _load_or_generate_key(self):
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            with open(self.key_path, "wb") as f:
                f.write(self.key)

    def _ensure_storage(self):
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w") as f:
                json.dump({}, f)

    def mint(self, agent_id: str, service: str, scope: List[str], raw_token: str, ttl_minutes: int = 5) -> ScopedCredential:
        """Stores the encrypted token and returns a safe ScopedCredential struct."""
        credential_id = f"cred-{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.utcnow()
        expires = now + datetime.timedelta(minutes=ttl_minutes)
        
        # Encrypt the raw token
        encrypted_token = self.fernet.encrypt(raw_token.encode("utf-8")).decode("utf-8")
        
        record = {
            "credential_id": credential_id,
            "service": service,
            "scope": scope,
            "encrypted_token": encrypted_token,
            "issued_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "agent_id": agent_id
        }
        
        with open(self.storage_path, "r") as f:
            data = json.load(f)
            
        data[credential_id] = record
        
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
            
        return ScopedCredential(
            credential_id=credential_id,
            service=service,
            scope=scope,
            issued_at=now,
            expires_at=expires,
            agent_id=agent_id
        )

    def revoke(self, credential_id: str):
        """Revokes a specific credential."""
        with open(self.storage_path, "r") as f:
            data = json.load(f)
            
        if credential_id in data:
            del data[credential_id]
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

    def validate(self, credential_id: str) -> bool:
        """Checks if a credential exists and has not expired."""
        with open(self.storage_path, "r") as f:
            data = json.load(f)
        if credential_id not in data:
            return False
        record = data[credential_id]
        expires = datetime.datetime.fromisoformat(record["expires_at"])
        if datetime.datetime.utcnow() > expires:
            self.revoke(credential_id)
            return False
        return True


    def _get_raw(self, credential_id: str) -> str:
        """
        INTERNAL USE ONLY. Used exclusively by the Broker/MCP executor.
        Will raise an error if the credential has expired.
        """
        with open(self.storage_path, "r") as f:
            data = json.load(f)
            
        if credential_id not in data:
            raise ValueError(f"Credential {credential_id} not found or revoked.")
            
        record = data[credential_id]
        expires = datetime.datetime.fromisoformat(record["expires_at"])
        
        if datetime.datetime.utcnow() > expires:
            self.revoke(credential_id)
            raise ValueError(f"Credential {credential_id} has expired.")
            
        encrypted_token = record["encrypted_token"].encode("utf-8")
        raw_token = self.fernet.decrypt(encrypted_token).decode("utf-8")
        return raw_token
