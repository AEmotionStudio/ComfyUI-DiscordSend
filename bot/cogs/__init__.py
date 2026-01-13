"""Discord bot cogs (command groups)."""

from .generate import GenerateCog
from .queue import QueueCog
from .templates import TemplateCog
from .history import HistoryCog
from .admin import AdminCog

__all__ = [
    "GenerateCog",
    "QueueCog",
    "TemplateCog",
    "HistoryCog",
    "AdminCog",
]
