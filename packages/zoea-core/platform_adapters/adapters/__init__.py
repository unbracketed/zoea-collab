"""
Platform adapter implementations.

Each adapter handles parsing inbound messages and sending outbound messages
for a specific platform type.
"""

from .base import BasePlatformAdapter
from .webhook import GenericWebhookAdapter

__all__ = [
    "BasePlatformAdapter",
    "GenericWebhookAdapter",
]
