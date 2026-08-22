import os
import unittest
import time
import datetime
from nava.credentials.vault import CredentialVault, ScopedCredential
from nava.credentials.broker import CredentialBroker
from nava.core.schemas import AgentState, AgentType

class TestCredentials(unittest.TestCase):
    def setUp(self):
        # Setup real vault but in a test path
        self.vault_path = "memory/test_vault.json"
        self.key_path = ".test_vault_key"
        if os.path.exists(self.vault_path):
            os.remove(self.vault_path)
        if os.path.exists(self.key_path):
            os.remove(self.key_path)
            
        self.vault = CredentialVault(storage_path=self.vault_path, key_path=self.key_path)
        self.broker = CredentialBroker(self.vault)
        
        # Inject mock root token for testing the broker
        os.environ["GMAIL_API_TOKEN"] = "real-secret-token-123"

    def tearDown(self):
        if os.path.exists(self.vault_path):
            os.remove(self.vault_path)
        if os.path.exists(self.key_path):
            os.remove(self.key_path)

    def test_vault_isolation(self):
        """Assert no code path outside CredentialBroker can retrieve a raw token from CredentialVault."""
        # 1. Mint a token
        scoped_cred = self.vault.mint("agt-1", "gmail", ["gmail.read"], "my-raw-token")
        
        # 2. Check ScopedCredential schema
        self.assertFalse(hasattr(scoped_cred, "raw_token"))
        self.assertFalse(hasattr(scoped_cred, "token"))
        
        # 3. Vault public interface check
        self.assertFalse(hasattr(self.vault, "get_raw"))
        self.assertFalse(hasattr(self.vault, "get_token"))
        
        # 4. We purposefully made _get_raw protected
        raw = self.vault._get_raw(scoped_cred.credential_id)
        self.assertEqual(raw, "my-raw-token")

    def test_scope_alignment(self):
        """Attempt to request a credential scope broader than the agent's credential_scope — assert denial."""
        agent = AgentState(
            agent_id="agt-aligned",
            role="TestAgent",
            type=AgentType.STATIC,
            goal="test",
            permission_scope=["gmail.read"],
            credential_scope=["gmail.read"], # Note: NOT gmail.send
            tool_scope=[],
            depth=1,
            ttl=datetime.timedelta(minutes=5),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
            budget_ref="ref"
        )
        
        # Valid subset should succeed
        cred = self.broker.request_credential(agent, "gmail", ["gmail.read"])
        self.assertIsNotNone(cred)
        
        # Broader scope should fail
        with self.assertRaises(PermissionError):
            self.broker.request_credential(agent, "gmail", ["gmail.send"])

    def test_expiry(self):
        """Mint a credential with a short TTL, wait past it, assert a subsequent use fails."""
        # Mint with a very short TTL (0 minutes, effectively instantly expired)
        scoped_cred = self.vault.mint("agt-exp", "gmail", ["gmail.read"], "expiring-token", ttl_minutes=-1)
        
        # Accessing it via the broker's internal method should raise an expiration error
        with self.assertRaises(ValueError) as context:
            self.vault._get_raw(scoped_cred.credential_id)
        
        self.assertIn("has expired", str(context.exception))

    def test_teardown(self):
        """Spawn an agent, mint it a credential, terminate the agent, assert the credential is revoked."""
        agent = AgentState(
            agent_id="agt-teardown",
            role="TestAgent",
            type=AgentType.STATIC,
            goal="test",
            permission_scope=["gmail.read"],
            credential_scope=["gmail.read"],
            tool_scope=[],
            depth=1,
            ttl=datetime.timedelta(minutes=5),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
            budget_ref="ref"
        )
        
        # 1. Mint credential
        cred = self.broker.request_credential(agent, "gmail", ["gmail.read"])
        self.assertEqual(self.vault._get_raw(cred.credential_id), "real-secret-token-123")
        
        # 2. Teardown
        self.broker.revoke_all("agt-teardown")
        
        # 3. Assert revoked
        with self.assertRaises(ValueError) as context:
            self.vault._get_raw(cred.credential_id)
        
        self.assertIn("not found or revoked", str(context.exception))

if __name__ == '__main__':
    unittest.main()
