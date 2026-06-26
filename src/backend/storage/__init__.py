"""Save/load system — game state persistence.

Provides:
    - SaveStorage: abstract interface for save/load backends
    - JsonStorage: JSON file implementation (3 manual + 1 auto slots)
"""

from src.backend.storage.json_storage import JsonStorage
from src.backend.storage.interface import SaveStorage, SaveInfo

__all__ = ["SaveStorage", "SaveInfo", "JsonStorage"]
