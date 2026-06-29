"""Save/load system tests.

Coverage:
- json_storage: save, load, list, delete
- gamesession: to_dict / from_dict round-trip
"""

import asyncio
import os
import shutil
import tempfile

import pytest

from src.backend.storage import JsonStorage, SaveInfo
from src.backend.engine.game_session import GameSession
from src.backend.engine.time import TimeState
from src.backend.engine.resource import ResourceState
from src.backend.engine.bond import BondManager
from src.backend.engine.karma import KarmaManager
from src.backend.ai.npc_agent.manager import AgentManager
from src.backend.data.npc_loader import load_npcs


# ═══════════════════════════════════════════════════
# JsonStorage
# ═══════════════════════════════════════════════════

class TestJsonStorage:
    """Tests for JSON save/load backend."""

    def setup_method(self):
        self.storage = JsonStorage()

    def test_save_and_load(self):
        data = {"time": {"day": 15, "slot": "night"}, "test": True}
        asyncio.run(self.storage.save(1, data))
        loaded = asyncio.run(self.storage.load(1))
        assert loaded["time"]["day"] == 15
        assert loaded["time"]["slot"] == "night"
        assert loaded["test"] is True

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            asyncio.run(self.storage.load(99))

    def test_list_saves(self):
        asyncio.run(self.storage.save(1, {"time": {"day": 10}}))
        asyncio.run(self.storage.save(2, {"time": {"day": 20}}))
        saves = asyncio.run(self.storage.list_saves())
        assert len(saves) == 4  # slots 0-3
        assert saves[1].slot == 1
        assert saves[1].exists is True
        assert saves[1].day == 10

    def test_delete(self):
        asyncio.run(self.storage.save(3, {"time": {"day": 30}}))
        asyncio.run(self.storage.delete(3))
        with pytest.raises(FileNotFoundError):
            asyncio.run(self.storage.load(3))

    def test_autosave_slot_0(self):
        data = {"time": {"day": 42, "slot": "morning"}}
        asyncio.run(self.storage.save(0, data))
        loaded = asyncio.run(self.storage.load(0))
        assert loaded["time"]["day"] == 42

    def test_overwrite(self):
        asyncio.run(self.storage.save(1, {"time": {"day": 10}}))
        asyncio.run(self.storage.save(1, {"time": {"day": 20}}))
        loaded = asyncio.run(self.storage.load(1))
        assert loaded["time"]["day"] == 20


# ═══════════════════════════════════════════════════
# GameSession round-trip
# ═══════════════════════════════════════════════════

class TestGameSessionRoundTrip:
    """Tests for GameSession.to_dict() → from_dict() round-trip."""

    def setup_method(self):
        npcs = load_npcs()
        bonds = BondManager()
        bonds.register_npcs([n.id for n in npcs])
        bonds.set("lin_chaoyin", "chen_yuanzhou", "红", 70, 60)

        karma = KarmaManager()
        karma.init_from_csv()
        karma.apply_delta("chaoyin_witch_line:+35")

        agents = AgentManager()
        agents.init_from_statics(npcs)

        self.session = GameSession(
            time=TimeState(day=25),
            resource=ResourceState(incense=45, divine_power=7, yang_de=12, yin_de=3),
            agents=agents,
            bonds=bonds,
            karma=karma,
        )

    def test_round_trip_preserves_time(self):
        data = self.session.to_dict()
        restored = GameSession.from_dict(data)
        assert restored.time.day == 25

    def test_round_trip_preserves_resource(self):
        data = self.session.to_dict()
        restored = GameSession.from_dict(data)
        assert restored.resource.incense == 45
        assert restored.resource.yang_de == 12
        assert restored.resource.yin_de == 3

    def test_round_trip_preserves_bonds(self):
        data = self.session.to_dict()
        restored = GameSession.from_dict(data)
        b = restored.bonds.get("lin_chaoyin", "chen_yuanzhou")
        assert b is not None
        assert b.type == "红"
        assert b.strength == 70

    def test_round_trip_preserves_karma(self):
        data = self.session.to_dict()
        restored = GameSession.from_dict(data)
        assert restored.karma.get_progress("chaoyin_witch_line") == 35.0

    def test_round_trip_preserves_agents(self):
        data = self.session.to_dict()
        restored = GameSession.from_dict(data)
        lin = restored.agents.get("lin_chaoyin")
        assert lin is not None
        assert lin.name == "林潮音"
        assert lin.static.age == 17

    def test_save_load_via_storage(self):
        """Full save/load cycle through JsonStorage + GameSession."""
        storage = JsonStorage()
        data = self.session.to_dict()
        asyncio.run(storage.save(1, data))

        loaded_data = asyncio.run(storage.load(1))
        restored = GameSession.from_dict(loaded_data)

        assert restored.time.day == 25
        assert restored.resource.incense == 45
        assert restored.agents.get("lin_chaoyin") is not None
        assert restored.bonds.get("lin_chaoyin", "chen_yuanzhou").strength == 70

        asyncio.run(storage.delete(1))
