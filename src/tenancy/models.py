"""Tenant data models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TenantStatus(str, Enum):
    """Lifecycle status of a tenant."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPROVISIONING = "deprovisioning"


class ResourceQuota(BaseModel):
    """CPU / memory resource bounds for a tenant namespace."""

    cpu_requests: str = "500m"
    cpu_limits: str = "2"
    memory_requests: str = "512Mi"
    memory_limits: str = "2Gi"
    max_pods: int = 20


class TenantConfig(BaseModel):
    """Configuration for a single tenant."""

    tenant_id: str
    display_name: str
    namespace: str
    status: TenantStatus = TenantStatus.ACTIVE
    quota: ResourceQuota = Field(default_factory=ResourceQuota)
    # Tenant-specific LLM / agent overrides (optional)
    config_overrides: dict[str, Any] = Field(default_factory=dict)
    # CIDR blocks allowed to reach this tenant's services
    allowed_ingress_cidrs: list[str] = Field(default_factory=list)

    @field_validator("tenant_id")
    @classmethod
    def tenant_id_slug(cls, v: str) -> str:
        """Ensure tenant_id is a valid DNS label segment."""
        import re

        if not re.match(r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?$", v):
            raise ValueError("tenant_id must be a lowercase alphanumeric slug (a-z, 0-9, hyphens)")
        return v

    @field_validator("namespace")
    @classmethod
    def namespace_prefixed(cls, v: str) -> str:
        """Namespace must start with 'tenant-' for isolation clarity."""
        if not v.startswith("tenant-"):
            raise ValueError("namespace must start with 'tenant-'")
        return v
