# ---------- state.py ----------
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd

@dataclass
class FVG:
    kind:   str                
    direction: str
    top:    float               # gap top price
    bottom: float               # gap bottom price
    created_at: pd.Timestamp
    uid =int = None
    first_touch_at: pd.Timestamp | None = None
    second_touch_at: pd.Timestamp | None = None
    hi_since_ft:     float | None = None   # running HH since first touch
    lo_since_ft:     float | None = None   # running LL since first touch
    entry_mid:       float | None = None   # cached (hi+lo)/2 once second touch stamps
    position_open: bool = False
    sl_initial: float | None = None
    sl_adjusted: float | None = None
    sl_updated_at: pd.Timestamp | None = None
    tp_initial: float | None = None
    tp_adjusted: float | None = None
    tp_updated_at: pd.Timestamp | None = None

@dataclass
class Context:
    active_fvgs:   list[FVG]            = field(default_factory=list)
    open_position: dict | None          = None      # { side, entry, sl, tp }
    session_high:  float | None         = None
    session_low:   float | None         = None

    def reset_session(self):
        self.__init__()                 # brute-force reset