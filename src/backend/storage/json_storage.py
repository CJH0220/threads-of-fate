"""JSON file save/load implementation.

Save directory: saves/ (alongside src/)
Files:
    saves/slot_1.json, saves/slot_2.json, saves/slot_3.json
    saves/autosave.json
    saves/index.json — metadata for quick listing
"""

import json
import os
import time
from typing import List

from src.backend.storage.interface import SaveStorage, SaveInfo


SAVES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "saves",
)


def _slot_path(slot: int) -> str:
    """Return the file path for a save slot."""
    if slot == 0:
        return os.path.join(SAVES_DIR, "autosave.json")
    return os.path.join(SAVES_DIR, f"slot_{slot}.json")


def _index_path() -> str:
    return os.path.join(SAVES_DIR, "index.json")


def _ensure_dir() -> None:
    os.makedirs(SAVES_DIR, exist_ok=True)


class JsonStorage(SaveStorage):
    """JSON file save/load backend."""

    async def save(self, slot: int, game_data: dict) -> None:
        """Write game data to a JSON save file."""
        _ensure_dir()

        # Write the save file
        path = _slot_path(slot)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(game_data, f, ensure_ascii=False, indent=2)

        # Update index
        day = game_data.get("time", {}).get("day", 1)
        self._update_index(slot, day)

    async def load(self, slot: int) -> dict:
        """Load game data from a JSON save file.

        Raises:
            FileNotFoundError: slot is empty
        """
        path = _slot_path(slot)
        if not os.path.exists(path):
            raise FileNotFoundError(f"存档槽位 {slot} 为空")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def list_saves(self) -> List[SaveInfo]:
        """List all save slots with metadata."""
        _ensure_dir()
        index = self._read_index()
        result = []
        for slot in [0, 1, 2, 3]:
            path = _slot_path(slot)
            exists = os.path.exists(path)
            info = SaveInfo(
                slot=slot,
                day=index.get(str(slot), {}).get("day", 0) if exists else 0,
                timestamp=index.get(str(slot), {}).get("timestamp", 0) if exists else 0,
                exists=exists,
            )
            result.append(info)
        return result

    async def delete(self, slot: int) -> None:
        """Delete a save slot. No-op if slot is empty."""
        path = _slot_path(slot)
        if os.path.exists(path):
            os.remove(path)
        self._remove_from_index(slot)

    # ── Index helpers ──

    @staticmethod
    def _read_index() -> dict:
        path = _index_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def _write_index(index: dict) -> None:
        _ensure_dir()
        with open(_index_path(), "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _update_index(slot: int, day: int) -> None:
        index = JsonStorage._read_index()
        index[str(slot)] = {"day": day, "timestamp": time.time()}
        JsonStorage._write_index(index)

    @staticmethod
    def _remove_from_index(slot: int) -> None:
        index = JsonStorage._read_index()
        index.pop(str(slot), None)
        JsonStorage._write_index(index)
