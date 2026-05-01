from abc import ABC, abstractmethod


class AlertStrategy(ABC):
    @abstractmethod
    def get_priority(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass


class P0CriticalAlert(AlertStrategy):
    def get_priority(self):
        return "P0"

    def get_description(self):
        return "CRITICAL — Immediate response required."


class P1HighAlert(AlertStrategy):
    def get_priority(self):
        return "P1"

    def get_description(self):
        return "HIGH — Respond within 15 minutes."


class P2WarningAlert(AlertStrategy):
    def get_priority(self):
        return "P2"

    def get_description(self):
        return "WARNING — Monitor within 1 hour."


COMPONENT_ALERT_STRATEGIES = {
    "RDBMS": P0CriticalAlert(),
    "MCP_HOST": P0CriticalAlert(),
    "ASYNC_QUEUE": P1HighAlert(),
    "API": P1HighAlert(),
    "NOSQL": P1HighAlert(),
    "CACHE": P2WarningAlert(),
}


def get_alert_strategy(component_type: str):
    return COMPONENT_ALERT_STRATEGIES.get(component_type.upper(), P1HighAlert())


def resolve_alert_priority(component_type: str):
    return get_alert_strategy(component_type).get_priority()