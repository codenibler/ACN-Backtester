from __future__ import annotations
from bot import config
import pandas as pd
import re
from typing import Iterable

_TRADE_RX = re.compile(
    r"""
    FVG\s+Type=\s*(?P<side>bullish|bearish)\s+
    Trade\s+Type=\s*(?P<trade_type>long|short)\s+
    Gap\s+created=\s*(?P<fvg_created>[^\n]+?)\s+
    FVG\s+Bounds=\s*(?P<low>\d+\.\d+)\s*-\s*(?P<high>\d+\.\d+)\s+
    First\s+Touch=\s*(?P<first_touch>[^\n]+?)\s+
    Second\s+Touch=\s*(?P<second_touch>[^\n]+?)\s+
    Trade\s+Entry\s+Time=\s*(?P<entry_time>[^\n]+?)\s+
    Trade\s+Entry\s+Price=\s*(?P<entry_price>\d+\.\d+)\s+
    (?:Initial\s+Take\s+Profit|Take\s+Profit\s+\(init\))=\s*(?P<init_tp>\d+\.\d+)\s+
    (?:Adjusted\s+Take\s+Profit|Take\s+Profit\s+\(adj\))=\s*(?P<adj_tp>\d+\.\d+)\s+
    (?:Original\s+Stop\s+Loss|Stop\s+Loss\s+\(init\))=\s*(?P<orig_sl>\d+\.\d+)\s+
    (?:Adjusted\s+Stop\s+Loss|Stop\s+Loss\s+\(adj\))=\s*(?P<adj_sl>\d+\.\d+)\s+
    Risk\s+to\s+Reward\s+Ratio=\s*(?P<rr_ratio>\d+(?:\.\d+)?)\s+
    Trade\s+UID=\s*(?P<trade_uid>\S+)
    """,
    re.I | re.VERBOSE,
)

# ── 2) parser that translates the groups ────────────────────
def _parse_trade(block: str) -> dict:
    m = _TRADE_RX.search(block)
    if not m:
        raise ValueError("Trade block does not match expected format")

    g = m.groupdict()

    return dict(
        # keep whatever extra fields you want; these are the ones the
        # evaluator needs downstream
        uid=g["trade_uid"],
        direction=g["trade_type"].lower(),        # "long" | "short"
        entry_ts=pd.Timestamp(g["entry_time"]),
        entry_price=float(g["entry_price"]),
        tp=float(g["adj_tp"]),                    # we use the *adjusted* levels
        sl=float(g["adj_sl"]),
        rr=float(g["rr_ratio"]),
        side=g["side"].lower(),                   # bullish | bearish (optional)
    )

def _walk_until_exit(
    df_slice: pd.DataFrame, direction: str, tp: float, sl: float
) -> tuple[pd.Timestamp, float, str]:

    # If outside of market hours, assume trade closed and immediately set exit. 
    for ts, row in df_slice.iterrows():
        if not config.in_session(ts):
            return ts, row["Close"], "session-close"

        hi, lo = row["High"], row["Low"]

        if direction == "long":
            if lo <= sl:
                return ts, sl, "loss"
            if hi >= tp:
                return ts, tp, "win"
        else:  # short
            if hi >= sl:
                return ts, sl, "loss"
            if lo <= tp:
                return ts, tp, "win"

    # ran out of data – treat like session close
    last_ts = df_slice.index[-1]
    return last_ts, df_slice.loc[last_ts, "Close"], "session-close"


def find_preformance(trade_log: Iterable[str], prices: pd.DataFrame) -> list[str]:
    """Return a *new* list with exit information appended to each block."""
    out: list[str] = []

    for block in trade_log:
        t = _parse_trade(block)

        # slice the price DataFrame from entry time onward
        df_fwd = prices.loc[t["entry_ts"] :]
        if df_fwd.empty:
            raise ValueError(f"No price data at/after {t['entry_ts']}")

        exit_ts, exit_px, tag = _walk_until_exit(
            df_fwd, t["direction"], t["tp"], t["sl"]
        )

        # simple 1-contract profit
        pnl = (
            exit_px - t["entry_price"]
            if t["direction"] == "long"
            else t["entry_price"] - exit_px
        )

        # build the new block
        augmented = (
            block.rstrip("─------------------------------------------\n")  # remove trailing newline if present
            + f"\nExit Time= {exit_ts}\n"
            + f"Exit Price= {exit_px:.2f}\n"
            + f"Result= {tag}\n"
            + f"Profit= {pnl:.2f}\n"
            "─------------------------------------------\n"
        )
        out.append(augmented)

    return out