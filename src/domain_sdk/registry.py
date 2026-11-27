"""Explicit registry for FarDB domain adapters."""

from __future__ import annotations

from .financial_adapter import FinancialDomainAdapter
from .protocol import DomainAdapter


class DomainRegistry:
    """Explicit in-memory registry mapping domain_id to DomainAdapter instances."""

    def __init__(self) -> None:
        """Initialize an empty DomainRegistry."""
        self._adapters: dict[str, DomainAdapter] = {}

    def register(self, adapter: DomainAdapter) -> None:
        """Register a DomainAdapter, rejecting invalid protocols or duplicate domain IDs."""
        if not isinstance(adapter, DomainAdapter):
            raise TypeError(f"Expected DomainAdapter implementation, got {type(adapter).__name__}")
        domain_id = adapter.domain_id.strip().lower()
        if not domain_id:
            raise ValueError("Adapter domain_id must be a non-empty string")
        if domain_id in self._adapters:
            raise ValueError(f"Domain adapter '{domain_id}' is already registered")
        self._adapters[domain_id] = adapter

    def get(self, domain_id: str) -> DomainAdapter:
        """Return the registered adapter for domain_id or raise KeyError."""
        key = domain_id.strip().lower()
        if key not in self._adapters:
            raise KeyError(f"Unknown domain adapter: '{domain_id}'")
        return self._adapters[key]

    def contains(self, domain_id: str) -> bool:
        """Return True if domain_id is registered."""
        return domain_id.strip().lower() in self._adapters

    def list_domains(self) -> tuple[str, ...]:
        """Return sorted registered domain IDs."""
        return tuple(sorted(self._adapters))


def create_default_registry() -> DomainRegistry:
    """Create a DomainRegistry pre-populated with the canonical financial adapter."""
    registry = DomainRegistry()
    registry.register(FinancialDomainAdapter())
    return registry
