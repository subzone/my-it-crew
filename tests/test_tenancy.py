"""Tests for the multi-tenancy framework (src/tenancy/)."""

import json
import tempfile
from pathlib import Path

import pytest

from src.tenancy.models import ResourceQuota, TenantConfig, TenantStatus
from src.tenancy.registry import TenantRegistry


def _make_tenant(tenant_id: str = "acme", namespace: str | None = None) -> TenantConfig:
    return TenantConfig(
        tenant_id=tenant_id,
        display_name="ACME Corp",
        namespace=namespace or f"tenant-{tenant_id}",
    )


# ---------------------------------------------------------------------------
# TenantConfig model validation
# ---------------------------------------------------------------------------


class TestTenantConfig:
    def test_valid_config(self):
        cfg = _make_tenant()
        assert cfg.tenant_id == "acme"
        assert cfg.namespace == "tenant-acme"
        assert cfg.status == TenantStatus.ACTIVE

    def test_default_quota(self):
        cfg = _make_tenant()
        assert isinstance(cfg.quota, ResourceQuota)
        assert cfg.quota.cpu_requests == "500m"
        assert cfg.quota.max_pods == 20

    def test_custom_quota(self):
        quota = ResourceQuota(cpu_limits="4", memory_limits="4Gi", max_pods=50)
        cfg = TenantConfig(
            tenant_id="bigcorp",
            display_name="Big Corp",
            namespace="tenant-bigcorp",
            quota=quota,
        )
        assert cfg.quota.cpu_limits == "4"
        assert cfg.quota.max_pods == 50

    def test_invalid_tenant_id_uppercase(self):
        with pytest.raises(ValueError, match="tenant_id must be"):
            TenantConfig(tenant_id="ACME", display_name="x", namespace="tenant-acme")

    def test_invalid_tenant_id_underscore(self):
        with pytest.raises(ValueError, match="tenant_id must be"):
            TenantConfig(tenant_id="acme_corp", display_name="x", namespace="tenant-acme-corp")

    def test_single_char_tenant_id(self):
        cfg = TenantConfig(tenant_id="a", display_name="A", namespace="tenant-a")
        assert cfg.tenant_id == "a"

    def test_two_char_tenant_id(self):
        cfg = TenantConfig(tenant_id="ab", display_name="AB", namespace="tenant-ab")
        assert cfg.tenant_id == "ab"

    def test_namespace_missing_prefix(self):
        with pytest.raises(ValueError, match="namespace must start with"):
            TenantConfig(tenant_id="acme", display_name="x", namespace="my-namespace")

    def test_config_overrides(self):
        cfg = TenantConfig(
            tenant_id="acme",
            display_name="ACME",
            namespace="tenant-acme",
            config_overrides={"default_model": "gpt-4o", "cycle_interval_seconds": 60},
        )
        assert cfg.config_overrides["default_model"] == "gpt-4o"

    def test_allowed_ingress_cidrs(self):
        cfg = TenantConfig(
            tenant_id="acme",
            display_name="ACME",
            namespace="tenant-acme",
            allowed_ingress_cidrs=["10.0.0.0/8", "192.168.1.0/24"],
        )
        assert len(cfg.allowed_ingress_cidrs) == 2


# ---------------------------------------------------------------------------
# TenantRegistry – in-memory
# ---------------------------------------------------------------------------


class TestTenantRegistry:
    def test_register_and_get(self):
        registry = TenantRegistry()
        cfg = _make_tenant()
        registry.register(cfg)
        result = registry.get("acme")
        assert result is not None
        assert result.tenant_id == "acme"

    def test_get_unknown_returns_none(self):
        registry = TenantRegistry()
        assert registry.get("nonexistent") is None

    def test_require_known(self):
        registry = TenantRegistry()
        cfg = _make_tenant()
        registry.register(cfg)
        assert registry.require("acme").tenant_id == "acme"

    def test_require_unknown_raises(self):
        registry = TenantRegistry()
        with pytest.raises(KeyError, match="nonexistent"):
            registry.require("nonexistent")

    def test_list_active(self):
        registry = TenantRegistry()
        registry.register(_make_tenant("acme"))
        registry.register(_make_tenant("beta"))
        registry.suspend("beta")
        active = registry.list_active()
        assert len(active) == 1
        assert active[0].tenant_id == "acme"

    def test_list_all(self):
        registry = TenantRegistry()
        registry.register(_make_tenant("acme"))
        registry.register(_make_tenant("beta"))
        assert len(registry.list_all()) == 2

    def test_suspend(self):
        registry = TenantRegistry()
        registry.register(_make_tenant("acme"))
        updated = registry.suspend("acme")
        assert updated.status == TenantStatus.SUSPENDED

    def test_deprovision(self):
        registry = TenantRegistry()
        registry.register(_make_tenant("acme"))
        updated = registry.deprovision("acme")
        assert updated.status == TenantStatus.DEPROVISIONING

    def test_remove(self):
        registry = TenantRegistry()
        registry.register(_make_tenant("acme"))
        registry.remove("acme")
        assert registry.get("acme") is None

    def test_resolve_setting_override(self):
        registry = TenantRegistry()
        cfg = TenantConfig(
            tenant_id="acme",
            display_name="ACME",
            namespace="tenant-acme",
            config_overrides={"default_model": "gpt-4o"},
        )
        registry.register(cfg)
        model = registry.resolve_setting("acme", "default_model", default="nemotron-nano")
        assert model == "gpt-4o"

    def test_resolve_setting_fallback(self):
        registry = TenantRegistry()
        registry.register(_make_tenant("acme"))
        result = registry.resolve_setting("acme", "missing_key", default="fallback")
        assert result == "fallback"

    def test_resolve_setting_unknown_tenant(self):
        registry = TenantRegistry()
        result = registry.resolve_setting("ghost", "any_key", default="default")
        assert result == "default"


# ---------------------------------------------------------------------------
# TenantRegistry – file persistence
# ---------------------------------------------------------------------------


class TestTenantRegistryPersistence:
    def test_persist_and_reload(self, tmp_path: Path):
        store = tmp_path / "tenants.json"
        registry = TenantRegistry(store_path=store)
        registry.register(_make_tenant("acme"))
        registry.register(_make_tenant("beta"))

        # A fresh registry loaded from the same file should see both tenants
        registry2 = TenantRegistry(store_path=store)
        assert registry2.get("acme") is not None
        assert registry2.get("beta") is not None

    def test_persist_file_content(self, tmp_path: Path):
        store = tmp_path / "tenants.json"
        registry = TenantRegistry(store_path=store)
        registry.register(_make_tenant("acme"))

        data = json.loads(store.read_text())
        assert isinstance(data, list)
        assert data[0]["tenant_id"] == "acme"

    def test_reload_preserves_status(self, tmp_path: Path):
        store = tmp_path / "tenants.json"
        registry = TenantRegistry(store_path=store)
        registry.register(_make_tenant("acme"))
        registry.suspend("acme")

        registry2 = TenantRegistry(store_path=store)
        assert registry2.require("acme").status == TenantStatus.SUSPENDED
