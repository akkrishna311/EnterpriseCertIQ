"""Tests for the per-service Azure credential factory (multi-account support)."""
from config.settings import get_settings
from backend.core.azure_credentials import get_service_credential, has_dedicated_spn


def test_falls_back_to_default_credential_when_no_spn():
    # 'foundry' has no *_tenant_id/_client_id/_client_secret triple → shared identity.
    from azure.identity import DefaultAzureCredential
    cred = get_service_credential("foundry")
    assert isinstance(cred, DefaultAzureCredential)
    assert has_dedicated_spn("foundry") is False


def test_fabric_uses_dedicated_service_principal(monkeypatch):
    from azure.identity import ClientSecretCredential
    s = get_settings()
    monkeypatch.setattr(s, "fabric_tenant_id", "tenant-B")
    monkeypatch.setattr(s, "fabric_client_id", "client-B")
    monkeypatch.setattr(s, "fabric_client_secret", "secret-B")

    assert has_dedicated_spn("fabric") is True
    cred = get_service_credential("fabric")
    assert isinstance(cred, ClientSecretCredential)


def test_async_variant_returns_aio_default_credential():
    from azure.identity.aio import DefaultAzureCredential as AioDefault
    cred = get_service_credential("foundry", is_async=True)
    assert isinstance(cred, AioDefault)


def test_partial_spn_does_not_count_as_dedicated(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "fabric_tenant_id", "tenant-B")
    monkeypatch.setattr(s, "fabric_client_id", "")        # incomplete
    monkeypatch.setattr(s, "fabric_client_secret", "secret-B")
    assert has_dedicated_spn("fabric") is False
