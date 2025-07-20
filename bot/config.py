from datetime import datetime, time, timezone, timedelta, timezone
from dataclasses import dataclass
from typing import Final
from zoneinfo import ZoneInfo

# === Optimizable Parameters ==========================================
tick_size      = 0.25         # index-points per tick
min_fvg_usd    = 12.5

min_fvg_points = round(min_fvg_usd / tick_size) * tick_size
ignore_time_zone = False
sl_max_candles = 4 
minimum_retracement_score = 0.2 
min_space_from_fvg_to_1st_touch = 3
lot_size = 1
structure_search_bars = 30
# Change when new parameters that can be changed is added. 
PARAMETER_COUNT = 7

__version__ = "1.4.14"

# === Time Zones ===========================================
# Single fixed-offset zone: UTC+2
ACTIVE_TZ: Final = ZoneInfo("Europe/Madrid")

SESSION_OPEN  : Final = time(10, 0,  tzinfo=ACTIVE_TZ)
SESSION_CLOSE : Final = time(18, 45, tzinfo=ACTIVE_TZ)

# Return true or false for entry logic to decide whether we should trade or not 
def in_session(ts_utc: datetime) -> bool:
    """
    Return True when `ts_utc` lies inside the 10:00-18:45 UTC+2 window.
    """
    if ignore_time_zone:
        return True 
    
    local = ts_utc.astimezone(ACTIVE_TZ).timetz()          # quick conversion
    return SESSION_OPEN <= local <= SESSION_CLOSE




