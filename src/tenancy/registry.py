"""In-process tenant registry with optional file-backed persistence."""

import json
from pathlib import Path
from typing import Any

import structlog

from src.tenancy.models import TenantConfig, TenantStatus

logger = structlog.get_logger()


class TenantRegistry:
    """Manages the set of known tenants and their configurations.

    Tenants can be loaded from / persisted to a JSON file for lightweight
    deployments; in production this would be backed by a database or a
    Kubernetes ConfigMap/Secret store.
    """

    def __init__(self, store_path: str | Path | None = None) -> None:
        self._tenants: dict[str, TenantConfig] = {}
        self._store_path = Path(store_path) if store_path else None
        if self._store_path and self._store_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, config: TenantConfig) -> TenantConfig:
        """Add or update a tenant configuration."""
        self._tenants[config.tenant_id] = config
        logger.info("tenant_registered", tenant_id=config.tenant_id, namespace=config.namespace)
        self._persist()
        return config

    def get(self, tenant_id: str) -> TenantConfig | None:
        """Return config for *tenant_id*, or ``None`` if unknown."""
        return self._tenants.get(tenant_id)

    def require(self, tenant_id: str) -> TenantConfig:
        """Return config for *tenant_id*, raising ``KeyError`` if unknown."""
        cfg = self.get(tenant_id)
        if cfg is None:
            raise KeyError(f"Unknown tenant: {tenant_id!r}")
        return cfg

    def list_active(self) -> list[TenantConfig]:
        """Return all tenants with ``ACTIVE`` status."""
        return [t for t in self._tenants.values() if t.status == TenantStatus.ACTIVE]

    def list_all(self) -> list[TenantConfig]:
        """Return every registered tenant regardless of status."""
        return list(self._tenants.values())

    def suspend(self, tenant_id: str) -> TenantConfig:
        """Mark a tenant as suspended."""
        cfg = self.require(tenant_id)
        updated = cfg.model_copy(update={"status": TenantStatus.SUSPENDED})
        self._tenants[tenant_id] = updated
        logger.info("tenant_suspended", tenant_id=tenant_id)
        self._persist()
        return updated

    def deprovision(self, tenant_id: str) -> TenantConfig:
        """Mark a tenant as deprovisioning (graceful teardown)."""
        cfg = self.require(tenant_id)
        updated = cfg.model_copy(update={"status": TenantStatus.DEPROVISIONING})
        self._tenants[tenant_id] = updated
        logger.info("tenant_deprovisioning", tenant_id=tenant_id)
        self._persist()
        return updated

    def remove(self, tenant_id: str) -> None:
        """Fully remove a tenant from the registry."""
        self._tenants.pop(tenant_id, None)
        self._persist()

    # ------------------------------------------------------------------
    # Tenant-aware settings resolution
    # ------------------------------------------------------------------

    def resolve_setting(self, tenant_id: str, key: str, default: Any = None) -> Any:
        """Return the tenant-specific override for *key*, falling back to *default*.

        Allows individual tenants to override global ``Settings`` values such as
        ``default_model`` or ``litellm_api_base`` without mutating global config.
        """
        cfg = self.get(tenant_id)
        if cfg is None:
            return default
        if key in cfg.config_overrides:
            logger.debug(
                "tenant_setting_override",
                tenant_id=tenant_id,
                key=key,
                value=cfg.config_overrides[key],
            )
            return cfg.config_overrides[key]
        logger.debug("tenant_setting_default", tenant_id=tenant_id, key=key, default=default)
        return default

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        if self._store_path is None:
            return
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        data = [t.model_dump(mode="json") for t in self._tenants.values()]
        payload = json.dumps(data, indent=2)
        # Write to a sibling tmp file then rename for atomic replacement.
        tmp = self._store_path.with_suffix(".tmp")
        tmp.write_text(payload)
        tmp.replace(self._store_path)

    def _load(self) -> None:
        raw = json.loads(self._store_path.read_text())  # type: ignore[union-attr]
        for item in raw:
            cfg = TenantConfig.model_validate(item)
            self._tenants[cfg.tenant_id] = cfg
        logger.info("tenant_registry_loaded", count=len(self._tenants))
