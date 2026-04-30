"""
Alert Strategy — Strategy Design Pattern
Different component failures map to different alert priorities.
Swap strategies without modifying the ingestion caller.
"""

from abc import ABC, abstractmethod


class AlertStrategy(ABC):
    @abstractmethod
    def get_priority(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass


class P0CriticalAlert(AlertStrategy):
    def get_priority(self) -> str:
        return "P0"

    def get_description(self) -> str:
        return "CRITICAL — Immediate response required. Page on-call engineer."


class P1HighAlert(AlertStrategy):
    def get_priority(self) -> str:
        return "P1"

    def get_description(self) -> str:
        return "HIGH — Response required within 15 minutes."


class P2WarningAlert(AlertStrategy):
    def get_priority(self) -> str:
        return "P2"

    def get_description(self) -> str:
        return "WARNING — Monitor and respond within 1 hour."


COMPONENT_ALERT_STRATEGIES = {
    "RDBMS":       P0CriticalAlert(),
    "MCP_HOST":    P0CriticalAlert(),
    "ASYNC_QUEUE": P1HighAlert(),
    "API":         P1HighAlert(),
    "NOSQL":       P1HighAlert(),
    "CACHE":       P2WarningAlert(),
}


def get_alert_strategy(component_type: str) -> AlertStrategy:
    """Return the appropriate AlertStrategy for the given component type."""
    return COMPONENT_ALERT_STRATEGIES.get(component_type.upper(), P1HighAlert())


def resolve_alert_priority(component_type: str) -> str:
    """Convenience function — returns the priority string for a component type."""
    strategy = get_alert_strategy(component_type)
    return strategy.get_priority()