from datetime import datetime, time, timezone, timedelta, timezone
from dataclasses import dataclass
from typing import Final
from zoneinfo import ZoneInfo

# === Instrument constants ==========================================
TICK_SIZE      = 0.25         # index-points per tick
MIN_FVG_USD    = 12.5
# Convert to index-points, round *up* to the nearest tick
MIN_FVG_POINTS = round(MIN_FVG_USD / TICK_SIZE) * TICK_SIZE
__version__ = "1.4.0"

SL_MAX_CANDLES = 4 # Stop must have been set at a minimum 8 1 min candles before entry. 

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
    local = ts_utc.astimezone(ACTIVE_TZ).timetz()          # quick conversion
    return SESSION_OPEN <= local <= SESSION_CLOSE




