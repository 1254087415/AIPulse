"""Push notification strategy base classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PushMessage:
    """Message to be pushed."""

    title: str
    summary: str
    url: str | None = None
    platform: str = ""
    extras: dict[str, str] = field(default_factory=dict)


class PushStrategy(ABC):
    """Strategy for sending push notifications."""

    @abstractmethod
    async def send(self, message: PushMessage) -> bool:
        """Send the push message."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required configuration is present."""
