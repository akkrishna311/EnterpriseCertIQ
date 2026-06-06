"""Tests for Azure Key Vault secret loading (offline — no real vault)."""
from config.settings import get_settings
from config import key_vault


def test_secret_map_covers_expected_secrets():
    assert key_vault.SECRET_MAP["azure-ai-api-key"] == "azure_ai_api_key"
    assert key_vault.SECRET_MAP["azure-search-key"] == "azure_search_key"
    assert key_vault.SECRET_MAP["cosmos-key"] == "cosmos_key"
    # KV names are hyphenated (no underscores allowed in Key Vault)
    assert all("_" not in name for name in key_vault.SECRET_MAP)


def test_load_is_noop_when_no_vault_url(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "azure_key_vault_url", "")
    result = key_vault.load_key_vault_secrets()
    assert result == {"enabled": False, "loaded": 0}


def test_load_applies_secrets_from_vault(monkeypatch):
    s = get_settings()
    original = {"azure_search_key": s.azure_search_key,
               "azure_ai_api_key": s.azure_ai_api_key}
    try:
        monkeypatch.setattr(s, "azure_key_vault_url", "https://fake.vault.azure.net")

        class _FakeSecret:
            def __init__(self, value):
                self.value = value

        class _FakeClient:
            def __init__(self, *a, **k):
                pass

            def get_secret(self, name):
                data = {"azure-search-key": "SK-from-kv", "azure-ai-api-key": "AK-from-kv"}
                if name in data:
                    return _FakeSecret(data[name])
                raise RuntimeError("SecretNotFound")

        import azure.keyvault.secrets as kvmod
        import azure.identity as idmod
        monkeypatch.setattr(kvmod, "SecretClient", _FakeClient)
        monkeypatch.setattr(idmod, "DefaultAzureCredential", lambda *a, **k: object())

        result = key_vault.load_key_vault_secrets()
        assert result["enabled"] is True
        assert result["loaded"] == 2
        assert set(result["secrets"]) == {"azure-search-key", "azure-ai-api-key"}
        # secrets were applied to the live settings singleton
        assert s.azure_search_key == "SK-from-kv"
        assert s.azure_ai_api_key == "AK-from-kv"
    finally:
        # restore the singleton so other tests see the real env values
        for attr, val in original.items():
            setattr(s, attr, val)
        monkeypatch.setattr(s, "azure_key_vault_url", "")
