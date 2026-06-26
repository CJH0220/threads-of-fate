"""Abstract save/load interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class SaveInfo:
    """Metadata for a saved game slot."""
    slot: int
    day: int
    timestamp: float
    exists: bool


class SaveStorage(ABC):
    """Abstract save/load backend.

    Slots: 1-3 for manual saves, 0 for autosave.
    """

    @abstractmethod
    async def save(self, slot: int, game_data: dict) -> None:
        """Write game data to a save slot."""
        ...

    @abstractmethod
    async def load(self, slot: int) -> dict:
        """Read game data from a save slot.

        Raises:
            FileNotFoundError: slot is empty
        """
        ...

    @abstractmethod
    async def list_saves(self) -> List[SaveInfo]:
        """List all save slots and their metadata."""
        ...

    @abstractmethod
    async def delete(self, slot: int) -> None:
        """Delete a save slot."""
        ...
