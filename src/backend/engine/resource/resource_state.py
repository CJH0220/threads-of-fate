"""Resource state — game resource ledger with built-in rules.

Constraints:
    - incense: floor at 0, no upper bound
    - divine_power: 0 ~ divine_power_max, daily refill to max
    - divine_power_max: 5 ~ 20, adjusted weekly by formula
    - yin_de / yang_de: non-decreasing (add only, ≥ 0)
"""

import math
from dataclasses import dataclass
from typing import Any, Dict


# ── Constants ──

DEFAULT_INCENSE = 50
DEFAULT_DIVINE_POWER_MAX = 10
DEFAULT_DIVINE_POWER = 10
DEFAULT_YIN_DE = 0
DEFAULT_YANG_DE = 0

MIN_DIVINE_POWER_MAX = 5
MAX_DIVINE_POWER_MAX = 20


# ── Main state ──

@dataclass
class ResourceState:
    """Mutable game resource state.

    All mutations validate constraints. Invalid operations raise ValueError.
    """
    incense: int = DEFAULT_INCENSE
    divine_power: int = DEFAULT_DIVINE_POWER
    divine_power_max: int = DEFAULT_DIVINE_POWER_MAX
    yin_de: int = DEFAULT_YIN_DE
    yang_de: int = DEFAULT_YANG_DE

    # ── Daily / Weekly ──

    def apply_daily(self) -> None:
        """Apply daily resource changes.

        - incense: -1 (hardcoded maintenance cost)
        - divine_power: refill to max
        """
        self.add_incense(-1)
        self.divine_power = self.divine_power_max

    def apply_weekly(
        self,
        incense_delta: int,
        yin_yang_delta: int,
        success_rate: float,
    ) -> None:
        """Recalculate divine_power_max based on weekly performance.

        Formula (design doc §10.3):
            new_max = current_max
                    + (incense_delta × 0.1)
                    + (success_rate - 0.5) × 2
                    + (yin_yang_delta × 0.05)
            new_max = clamp(ceil(new_max), 5, 20)

        Args:
            incense_delta: net incense change this week
            yin_yang_delta: total yin_de + yang_de gained this week
            success_rate: fraction of interventions that succeeded (0.0 ~ 1.0)
        """
        raw = (
            self.divine_power_max
            + incense_delta * 0.1
            + (success_rate - 0.5) * 2.0
            + yin_yang_delta * 0.05
        )
        self.divine_power_max = max(
            MIN_DIVINE_POWER_MAX,
            min(MAX_DIVINE_POWER_MAX, math.ceil(raw)),
        )

    # ── Intervention spending ──

    def spend_divine_power(self, amount: int) -> None:
        """Deduct divine power for an intervention.

        Args:
            amount: positive integer to spend

        Raises:
            ValueError: amount is negative or exceeds current divine_power
        """
        if amount < 0:
            raise ValueError(f"Cannot spend negative divine power: {amount}")
        if amount > self.divine_power:
            raise ValueError(
                f"Not enough divine power: need {amount}, have {self.divine_power}"
            )
        self.divine_power -= amount

    def add_incense(self, amount: int) -> None:
        """Add or subtract incense. Floor at 0.

        Args:
            amount: positive to gain, negative to lose
        """
        self.incense = max(0, self.incense + amount)

    def add_yin_de(self, amount: int) -> None:
        """Add yin_de. Only non-negative values allowed.

        Raises:
            ValueError: amount is negative (yin_de is non-decreasing)
        """
        if amount < 0:
            raise ValueError(f"yin_de cannot decrease: attempted {amount}")
        self.yin_de += amount

    def add_yang_de(self, amount: int) -> None:
        """Add yang_de. Only non-negative values allowed.

        Raises:
            ValueError: amount is negative (yang_de is non-decreasing)
        """
        if amount < 0:
            raise ValueError(f"yang_de cannot decrease: attempted {amount}")
        self.yang_de += amount

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict.

        Returns:
            {"incense": 50, "divine_power": 10, "divine_power_max": 10,
             "yin_de": 0, "yang_de": 0}
        """
        return {
            "incense": self.incense,
            "divine_power": self.divine_power,
            "divine_power_max": self.divine_power_max,
            "yin_de": self.yin_de,
            "yang_de": self.yang_de,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceState":
        """Deserialize from dict with validation.

        Raises:
            ValueError: any field is invalid
        """
        incense = data.get("incense", DEFAULT_INCENSE)
        divine_power = data.get("divine_power", DEFAULT_DIVINE_POWER)
        divine_power_max = data.get("divine_power_max", DEFAULT_DIVINE_POWER_MAX)
        yin_de = data.get("yin_de", DEFAULT_YIN_DE)
        yang_de = data.get("yang_de", DEFAULT_YANG_DE)

        # Validate types
        for name, val in [
            ("incense", incense), ("divine_power", divine_power),
            ("divine_power_max", divine_power_max),
            ("yin_de", yin_de), ("yang_de", yang_de),
        ]:
            if not isinstance(val, int):
                raise ValueError(f"Invalid {name}: expected int, got {type(val).__name__}")

        # Validate ranges
        if incense < 0:
            raise ValueError(f"Invalid incense: {incense}, must be ≥ 0")
        if not (MIN_DIVINE_POWER_MAX <= divine_power_max <= MAX_DIVINE_POWER_MAX):
            raise ValueError(
                f"Invalid divine_power_max: {divine_power_max}, "
                f"must be {MIN_DIVINE_POWER_MAX}-{MAX_DIVINE_POWER_MAX}"
            )
        if not (0 <= divine_power <= divine_power_max):
            raise ValueError(
                f"Invalid divine_power: {divine_power}, "
                f"must be 0-{divine_power_max}"
            )
        if yin_de < 0:
            raise ValueError(f"Invalid yin_de: {yin_de}, must be ≥ 0")
        if yang_de < 0:
            raise ValueError(f"Invalid yang_de: {yang_de}, must be ≥ 0")

        return cls(
            incense=incense,
            divine_power=divine_power,
            divine_power_max=divine_power_max,
            yin_de=yin_de,
            yang_de=yang_de,
        )
