"""Resource system — game resource ledger with built-in rules.

Manages four resources:
    - incense (香火): daily -1, initial 50, must reach ≥100 by day 60
    - divine_power (神力): daily refill to max, cap adjusts weekly (5-20)
    - yin_de (阴德): only increases, ≥100 triggers dark god ending
    - yang_de (阳德): only increases, ≥100 triggers light god ending

Public API:
    state.apply_daily()                             # incense -1, divine_power refill
    state.apply_weekly(inc_delta, yy_delta, rate)   # recalculate divine_power_max
    state.spend_divine_power(amount)                # validated deduction
    state.add_incense(amount)                       # add/subtract (floor at 0)
    state.add_yin_de(amount)                        # add only (≥ 0)
    state.add_yang_de(amount)                       # add only (≥ 0)
    state.to_dict()                                 # serialize
    ResourceState.from_dict(d)                      # deserialize
"""

from src.backend.engine.resource.resource_state import ResourceState

__all__ = ["ResourceState"]
