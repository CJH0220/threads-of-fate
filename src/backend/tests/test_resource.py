"""Resource system module tests.

Coverage:
- resource_state: initial values, daily/weekly, spending, serialization
- constraints: incense floor, divine_power bounds, yin/yang non-decreasing
"""

import math
import pytest

from src.backend.engine.resource import ResourceState


# ═══════════════════════════════════════════════════
# Initial state
# ═══════════════════════════════════════════════════

class TestInitialState:
    """Tests for default ResourceState."""

    def test_defaults(self):
        state = ResourceState()
        assert state.incense == 50
        assert state.divine_power == 10
        assert state.divine_power_max == 10
        assert state.yin_de == 0
        assert state.yang_de == 0

    def test_custom_init(self):
        state = ResourceState(incense=30, divine_power=5, divine_power_max=12,
                              yin_de=10, yang_de=20)
        assert state.incense == 30
        assert state.divine_power == 5
        assert state.divine_power_max == 12
        assert state.yin_de == 10
        assert state.yang_de == 20


# ═══════════════════════════════════════════════════
# Daily application
# ═══════════════════════════════════════════════════

class TestDaily:
    """Tests for apply_daily()."""

    def test_incense_decreases_by_one(self):
        state = ResourceState(incense=50)
        state.apply_daily()
        assert state.incense == 49

    def test_divine_power_refills_to_max(self):
        state = ResourceState(divine_power=3, divine_power_max=12)
        state.apply_daily()
        assert state.divine_power == 12

    def test_incense_floored_at_zero(self):
        state = ResourceState(incense=0)
        state.apply_daily()
        assert state.incense == 0

    def test_60_days_of_daily(self):
        """After 60 daily applications, incense = 50 - 60 = 0 (floored)."""
        state = ResourceState()
        for _ in range(60):
            state.apply_daily()
        assert state.incense == 0  # 50 - 60 = -10, floored to 0
        assert state.divine_power == state.divine_power_max  # refilled daily


# ═══════════════════════════════════════════════════
# Divine power spending
# ═══════════════════════════════════════════════════

class TestSpendDivinePower:
    """Tests for spend_divine_power()."""

    def test_normal_spend(self):
        state = ResourceState(divine_power=8)
        state.spend_divine_power(3)
        assert state.divine_power == 5

    def test_spend_all(self):
        state = ResourceState(divine_power=10)
        state.spend_divine_power(10)
        assert state.divine_power == 0

    def test_insufficient_raises(self):
        state = ResourceState(divine_power=2)
        with pytest.raises(ValueError, match="Not enough divine power"):
            state.spend_divine_power(5)

    def test_negative_amount_raises(self):
        state = ResourceState()
        with pytest.raises(ValueError, match="negative divine power"):
            state.spend_divine_power(-1)

    def test_zero_spend_allowed(self):
        state = ResourceState(divine_power=5)
        state.spend_divine_power(0)
        assert state.divine_power == 5


# ═══════════════════════════════════════════════════
# Incense
# ═══════════════════════════════════════════════════

class TestAddIncense:
    """Tests for add_incense()."""

    def test_positive(self):
        state = ResourceState(incense=40)
        state.add_incense(15)
        assert state.incense == 55

    def test_negative(self):
        state = ResourceState(incense=40)
        state.add_incense(-10)
        assert state.incense == 30

    def test_zero_floor(self):
        state = ResourceState(incense=3)
        state.add_incense(-10)
        assert state.incense == 0

    def test_accumulate_past_100(self):
        state = ResourceState(incense=95)
        state.add_incense(20)
        assert state.incense == 115


# ═══════════════════════════════════════════════════
# Yin De
# ═══════════════════════════════════════════════════

class TestAddYinDe:
    """Tests for add_yin_de()."""

    def test_positive(self):
        state = ResourceState(yin_de=30)
        state.add_yin_de(10)
        assert state.yin_de == 40

    def test_zero_allowed(self):
        state = ResourceState(yin_de=30)
        state.add_yin_de(0)
        assert state.yin_de == 30

    def test_negative_raises(self):
        state = ResourceState()
        with pytest.raises(ValueError, match="cannot decrease"):
            state.add_yin_de(-5)

    def test_reaches_100_threshold(self):
        state = ResourceState(yin_de=95)
        state.add_yin_de(5)
        assert state.yin_de == 100


# ═══════════════════════════════════════════════════
# Yang De
# ═══════════════════════════════════════════════════

class TestAddYangDe:
    """Tests for add_yang_de()."""

    def test_positive(self):
        state = ResourceState(yang_de=20)
        state.add_yang_de(15)
        assert state.yang_de == 35

    def test_zero_allowed(self):
        state = ResourceState(yang_de=20)
        state.add_yang_de(0)
        assert state.yang_de == 20

    def test_negative_raises(self):
        state = ResourceState()
        with pytest.raises(ValueError, match="cannot decrease"):
            state.add_yang_de(-5)

    def test_reaches_100_threshold(self):
        state = ResourceState(yang_de=90)
        state.add_yang_de(10)
        assert state.yang_de == 100


# ═══════════════════════════════════════════════════
# Weekly settlement
# ═══════════════════════════════════════════════════

class TestApplyWeekly:
    """Tests for apply_weekly() — divine_power_max recalculation."""

    def test_no_change(self):
        """Zero deltas and 50% success → no change to max."""
        state = ResourceState(divine_power_max=10)
        state.apply_weekly(incense_delta=0, yin_yang_delta=0, success_rate=0.5)
        assert state.divine_power_max == 10

    def test_good_performance_increases_max(self):
        """Positive results should raise the cap."""
        state = ResourceState(divine_power_max=10)
        state.apply_weekly(incense_delta=5, yin_yang_delta=10, success_rate=0.7)
        # 10 + 5*0.1 + (0.7-0.5)*2 + 10*0.05 = 10 + 0.5 + 0.4 + 0.5 = 11.4 → ceil = 12
        assert state.divine_power_max == 12

    def test_poor_performance_decreases_max(self):
        """Negative results should lower the cap."""
        state = ResourceState(divine_power_max=10)
        state.apply_weekly(incense_delta=-3, yin_yang_delta=0, success_rate=0.2)
        # 10 + (-3)*0.1 + (0.2-0.5)*2 + 0*0.05 = 10 - 0.3 - 0.6 = 9.1 → ceil = 10
        assert state.divine_power_max == 10

    def test_clamp_at_5(self):
        """Cap cannot go below 5."""
        state = ResourceState(divine_power_max=6)
        state.apply_weekly(incense_delta=-50, yin_yang_delta=0, success_rate=0.0)
        assert state.divine_power_max == 5

    def test_clamp_at_20(self):
        """Cap cannot go above 20."""
        state = ResourceState(divine_power_max=18)
        state.apply_weekly(incense_delta=100, yin_yang_delta=100, success_rate=1.0)
        assert state.divine_power_max == 20

    def test_rounding_up(self):
        """Ceil rounding: 10.1 → 11."""
        state = ResourceState(divine_power_max=10)
        state.apply_weekly(incense_delta=1, yin_yang_delta=0, success_rate=0.5)
        # 10 + 1*0.1 + 0 + 0 = 10.1 → ceil = 11
        assert state.divine_power_max == 11


# ═══════════════════════════════════════════════════
# Serialization
# ═══════════════════════════════════════════════════

class TestSerialization:
    """Tests for to_dict() / from_dict() round-trip."""

    def test_to_dict(self):
        state = ResourceState(incense=30, divine_power=7, divine_power_max=14,
                              yin_de=5, yang_de=10)
        d = state.to_dict()
        assert d == {
            "incense": 30,
            "divine_power": 7,
            "divine_power_max": 14,
            "yin_de": 5,
            "yang_de": 10,
        }

    def test_from_dict(self):
        state = ResourceState.from_dict({
            "incense": 40, "divine_power": 8, "divine_power_max": 15,
            "yin_de": 12, "yang_de": 25,
        })
        assert state.incense == 40
        assert state.divine_power == 8
        assert state.divine_power_max == 15
        assert state.yin_de == 12
        assert state.yang_de == 25

    def test_round_trip(self):
        original = ResourceState(incense=55, divine_power=3, divine_power_max=11,
                                 yin_de=7, yang_de=42)
        data = original.to_dict()
        restored = ResourceState.from_dict(data)
        assert restored.incense == original.incense
        assert restored.divine_power == original.divine_power
        assert restored.divine_power_max == original.divine_power_max
        assert restored.yin_de == original.yin_de
        assert restored.yang_de == original.yang_de

    def test_from_dict_defaults(self):
        state = ResourceState.from_dict({})
        assert state.incense == 50
        assert state.divine_power == 10
        assert state.divine_power_max == 10
        assert state.yin_de == 0
        assert state.yang_de == 0

    def test_from_dict_invalid_incense_negative(self):
        with pytest.raises(ValueError, match="Invalid incense"):
            ResourceState.from_dict({"incense": -1})

    def test_from_dict_invalid_divine_power_max_low(self):
        with pytest.raises(ValueError, match="Invalid divine_power_max"):
            ResourceState.from_dict({"divine_power_max": 3})

    def test_from_dict_invalid_divine_power_max_high(self):
        with pytest.raises(ValueError, match="Invalid divine_power_max"):
            ResourceState.from_dict({"divine_power_max": 25})

    def test_from_dict_divine_power_exceeds_max(self):
        with pytest.raises(ValueError, match="Invalid divine_power"):
            ResourceState.from_dict({"divine_power": 15, "divine_power_max": 10})

    def test_from_dict_invalid_types(self):
        with pytest.raises(ValueError, match="expected int"):
            ResourceState.from_dict({"incense": "many"})

    def test_from_dict_invalid_yin_de_negative(self):
        with pytest.raises(ValueError, match="Invalid yin_de"):
            ResourceState.from_dict({"yin_de": -5})

    def test_from_dict_invalid_yang_de_negative(self):
        with pytest.raises(ValueError, match="Invalid yang_de"):
            ResourceState.from_dict({"yang_de": -5})


# ═══════════════════════════════════════════════════
# Integration scenarios
# ═══════════════════════════════════════════════════

class TestIntegrationScenarios:
    """Multi-step scenarios simulating real gameplay."""

    def test_daily_spend_refill_cycle(self):
        """A day: spend power → daily reset → power back to max."""
        state = ResourceState(divine_power=10, divine_power_max=10, incense=50)

        # Player spends 8 divine power on interventions
        state.spend_divine_power(3)
        state.spend_divine_power(5)
        assert state.divine_power == 2

        # Advance to next day
        state.apply_daily()
        assert state.divine_power == 10  # refilled
        assert state.incense == 49       # -1

    def test_endgame_incense_check(self):
        """Simulate: if incense < 100 at day 60, game is lost (§5.2)."""
        state = ResourceState(incense=90)
        # Player did not earn enough incense
        assert state.incense < 100  # failure condition met

    def test_endgame_yin_de_ending(self):
        """Yin_de ≥ 100 + incense ≥ 100 + yang_de < 100 → dark god ending."""
        state = ResourceState(incense=120, yin_de=110, yang_de=20)
        is_dark_god = (
            state.incense >= 100
            and state.yin_de >= 100
            and state.yang_de < 100
        )
        assert is_dark_god is True

    def test_endgame_yang_de_ending(self):
        """Yang_de ≥ 100 + incense ≥ 100 + yin_de < 100 → light god ending."""
        state = ResourceState(incense=105, yin_de=30, yang_de=120)
        is_light_god = (
            state.incense >= 100
            and state.yang_de >= 100
            and state.yin_de < 100
        )
        assert is_light_god is True

    def test_endgame_legendary_ending(self):
        """Both ≥ 100 + incense ≥ 100 → legendary ending."""
        state = ResourceState(incense=150, yin_de=105, yang_de=110)
        is_legendary = (
            state.incense >= 100
            and state.yin_de >= 100
            and state.yang_de >= 100
        )
        assert is_legendary is True

    def test_weekly_cycle_with_full_week(self):
        """Simulate a week of gameplay: daily + weekly settlement."""
        state = ResourceState(incense=50, divine_power_max=10, yang_de=0)

        # Simulate 7 days
        for _ in range(7):
            state.apply_daily()
            # Player earns some yang_de each day from good outcomes
            state.add_yang_de(3)

        # After 7 days: incense = 50 - 7 = 43, yang_de = 21
        assert state.incense == 43
        assert state.yang_de == 21

        # Weekly settlement
        state.apply_weekly(
            incense_delta=43 - 50,   # -7
            yin_yang_delta=21 - 0,   # +21
            success_rate=0.7,
        )
        # 10 + (-7)*0.1 + (0.7-0.5)*2 + 21*0.05 = 10 - 0.7 + 0.4 + 1.05 = 10.75 → 11
        assert state.divine_power_max == 11
