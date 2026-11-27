"""Canonical Domain-Adapter SDK for plugging non-financial domains into FarDB."""

from __future__ import annotations

from .conformance import ConformanceResult, DomainConformanceSuite
from .financial_adapter import FinancialDomainAdapter
from .protocol import DomainAdapter, DomainEdge, DomainEntity
from .registry import DomainRegistry, create_default_registry

__all__ = [
    "ConformanceResult",
    "DomainAdapter",
    "DomainConformanceSuite",
    "DomainEdge",
    "DomainEntity",
    "DomainRegistry",
    "FinancialDomainAdapter",
    "create_default_registry",
]
