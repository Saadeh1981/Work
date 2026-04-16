
"""
keyvault.py
-----------
Placeholder helper for pulling secrets (e.g., DI endpoint) via Managed Identity.
"""
from typing import Optional

class KeyVaultClient:
    def __init__(self, vault_url: Optional[str] = None):
        self.vault_url = vault_url

    def get_secret(self, name: str) -> str:
        # TODO: Use azure-identity + azure-keyvault-secrets to fetch at runtime.
        raise NotImplementedError("Key Vault access not implemented yet.")
