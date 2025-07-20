from __future__ import annotations

import re
import sys
import textwrap
import webbrowser
from datetime import timedelta
from pathlib import Path
from typing import List

import importlib.resources as res
import pandas as pd
import plotly.graph_objects as go
import pytz

# ── Constants ──────────────────────────────────────────────────────────
DATA_TZ = pytz.timezone("America/New_York")   # timezone of the CSV file
VIEW_TZ = pytz.timezone("Europe/Amsterdam")   # charts will be displayed in this TZ

if getattr(sys, "frozen", False):          # running inside PyInstaller
    # _MEIPASS = .../Contents/Frameworks/
    BASE_DIR = Path(sys._MEIPASS).parent / "Resources"
else:                                      # running from source
    BASE_DIR = Path(__file__).parent

CSV_PATH = BASE_DIR / "NQ.txt"

LOOKBACK_MIN   = 150            # minutes shown before FVG creation
AFTER_EXIT_MIN = 45             # ← NEW: minutes shown **after Exit**
FWD_FALLBACK   = 330            # legacy forward window when exit is unknown
CHART_HEIGHT   = 750

# Colour / opacity tweaks
FVG_COLOR          = "rgba(0, 160, 255, 0.25)"   # light-blue, 25 % opac
TP_RECT_COLOR      = "#4aff71"                    # green, 40 % opac
INIT_TP_LINE_COLOR = "#008000"                    # solid dark-green
ADJ_SL_RECT_COLOR  = "#ff595c"                    # translucent red
ORIG_SL_LINE_COLOR = "#ff0000"                    # solid dark-red
EXIT_MARKER_COLOR  = "#000000"                    # black marker (easy to see)

# ── Regex patterns ─────────────────────────────────────────────────────
# NB: Line numbers referenced in comments are relative to this file.
_TRADE_RX = re.compile(
    r"""
    ^FVG\s+Type=\s*(?P<side>bullish|bearish)\s+                             
    Trade\s+Type=\s*(?P<trade_type>long|short)\s+                           
    Gap\s+created=\s*(?P<fvg_created>[^\n]+?)\s+                            
    FVG\s+Bounds=\s*(?P<low>\d+\.\d+)\s*-\s*(?P<high>\d+\.\d+)\s+           
    First\s+Touch=\s*(?P<first_touch>[^\n]+?)\s+                            
    Second\s+Touch=\s*(?P<second_touch>[^\n]+?)\s+                          
    Trade\s+Entry\s+Time=\s*(?P<entry_time>[^\n]+?)\s+                      
    Trade\s+Entry\s+Price=\s*(?P<entry_price>-?\d+\.\d+)\s+                 
    (?:Initial\s+Take\s+Profit|Take\s+Profit\s+\(init\))=\s*                    
    (?P<init_tp>-?\d+\.\d+)\s+                                      
    (?:Adjusted\s+Take\s+Profit|Take\s+Profit\s+\(adj\))=\s*            
        (?P<adj_tp>-?\d+\.\d+)\s+                                       
    (?:Original\s+Stop\s+Loss|Stop\s+Loss\s+\(init\))=\s*               
        (?P<orig_sl>-?\d+\.\d+)\s+                                      
    (?:Adjusted\s+Stop\s+Loss|Stop\s+Loss\s+\(adj\))=\s*                
        (?P<adj_sl>-?\d+\.\d+)\s+                                       
    Risk\s+to\s+Reward\s+Ratio=\s*(?P<rr_ratio>-?\d+(?:\.\d+)?)\s+      
    Trade\s+UID=\s*(?P<trade_uid>\S+)\s+                                
    (?:Exit\s+Time=\s*(?P<exit_time>[^\n]+?)\s+)?                       
    (?:Exit\s+Price=\s*(?P<exit_price>-?\d+\.\d+)\s+)?                  
    (?:Result=\s*(?P<result>\w+)\s+)?                                   
    (?:Profit=\s*(?P<profit>-?\d+\.\d+)\s*)?                            
    (?:\s*[-─—–]+\s*)?  
    \s*$                                                                
    """,
    re.I | re.VERBOSE | re.MULTILINE,
)

_TP_ROLL_RX = re.compile(r"TP\s+rolled\s+to\s+(?P<tp>\d+\.\d+)", re.I)

# ── Helpers ────────────────────────────────────────────────────────────

def _clean(raw: str) -> str:
    """Strip outer quotes & stray escape chars; dedent."""
    raw = textwrap.dedent(raw).strip()
    if raw.startswith("\"") and raw.endswith("\""):
        raw = raw[1:-1]
    return raw.replace("\"", "")


def _to_dt_any(s: str):
    ts = pd.to_datetime(s)
    return ts if ts.tzinfo else ts.tz_localize("UTC")


# 140-149 — parser now captures `adj_tp`
# --------------------------------------

def parse_trade_block(raw: str) -> dict:
    """Return a dict with parsed & typed trade metadata."""
    raw = _clean(raw)

    header = _TRADE_RX.search(" ".join(raw.splitlines()))
    if not header:
        sys.exit("❌ Couldn’t parse trade header — check spelling / spacing.")
    g = header.groupdict()

    # Collect TP rolls; final_tp = last roll or initial_tp (legacy support).
    rolls: List[float] = [float(x) for x in _TP_ROLL_RX.findall(raw)]

    # NEW: prefer explicit adjusted TP when present (line 149)
    if g.get("adj_tp"):
        adj_tp = float(g["adj_tp"])
    elif rolls:
        adj_tp = rolls[-1]
    else:
        adj_tp = float(g["init_tp"])

    to_f  = float
    to_dt = lambda s: _to_dt_any(s).tz_convert(VIEW_TZ)

    exit_time  = to_dt(g["exit_time"])  if g.get("exit_time")  else None
    exit_price = to_f(g["exit_price"])  if g.get("exit_price") else None
    result     = g.get("result", "")
    profit     = to_f(g["profit"])      if g.get("profit")     else None

    return {
        "side"        : g["side"].lower(),
        "trade_type"  : g["trade_type"].lower(),
        "fvg_created" : to_dt(g["fvg_created"]),
        "first_touch" : to_dt(g["first_touch"]),
        "second_touch": to_dt(g["second_touch"]),
        "entry_time"  : to_dt(g["entry_time"]),
        "entry_price" : to_f(g["entry_price"]),
        "initial_tp"  : to_f(g["init_tp"]),
        "adj_tp"      : adj_tp,             # ← used for profit rectangle
        "orig_sl"     : to_f(g["orig_sl"]),
        "adj_sl"      : to_f(g["adj_sl"]),
        "trade_uid"   : g["trade_uid"],
        "fvg_low"     : to_f(g["low"]),
        "fvg_high"    : to_f(g["high"]),
        "exit_time"  : exit_time,     # may be None
        "exit_price" : exit_price,          # may be None
        "result"     : result,
        "profit"     : profit,
    }

# ── Data utilities ────────────────────────────────────────────────────

def load_m1(path: Path) -> pd.DataFrame:
    """Load 1-minute OHLCV CSV (no header) into a tz-aware DataFrame."""
    df = pd.read_csv(
        path,
        header=None,
        names=["date", "time", "open", "high", "low", "close", "volume"],
        dtype={"open": float, "high": float, "low": float,
               "close": float, "volume": float},
    )
    dt_str = df["date"].str.strip() + " " + df["time"].str.strip()
    df["timestamp"] = (
        pd.to_datetime(dt_str, format="%m/%d/%Y %H:%M")
          .dt.tz_localize(DATA_TZ)
    )
    return (df.set_index("timestamp").sort_index()
              [["open", "high", "low", "close", "volume"]])


def slice_window(df: pd.DataFrame, start, end) -> pd.DataFrame:
    return df.loc[start:end]


def resample_full(df_m1: pd.DataFrame):
    """Return 5- and 15-minute resamples alongside 1-min data."""
    agg = dict(open=("open", "first"), high=("high", "max"),
               low=("low", "min"), close=("close", "last"))
    m5  = (df_m1.resample("5min", label="right", closed="right",
                         origin="start_day").agg(**agg).dropna())
    m15 = (df_m1.resample("15min", label="right", closed="right",
                         origin="start_day").agg(**agg).dropna())
    return m5, m15

# ── Figure builder ────────────────────────────────────────────────────

def make_candle_fig(df: pd.DataFrame, title: str, meta: dict) -> go.Figure:
    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df.open, high=df.high,
        low=df.low, close=df.close, name=title)])

    fig.update_layout(
        title=title,
        height=CHART_HEIGHT,
        showlegend=False,
        xaxis_rangeslider_visible=False,
    )

    if meta.get("exit_time") and meta.get("exit_price"):
        fig.add_trace(
            go.Scatter(
                x=[meta["exit_time"]],
                y=[meta["exit_price"]],
                mode="markers",
                marker=dict(
                    symbol="triangle-down",
                    size=14,
                    color="#000000",
                    line=dict(color="#ffffff", width=1),
                ),
                name="Exit",
            )
        )

    # FVG (blue rectangle)
    fig.add_shape(type="rect", layer="below", fillcolor=FVG_COLOR, line_width=0,
                  xref="x", yref="y",
                  x0=meta["fvg_created"], x1=df.index[-1],
                  y0=meta["fvg_low"],     y1=meta["fvg_high"])

    # Profit rectangle (entry ↔ adjusted TP)
    fig.add_shape(type="rect", layer="below", fillcolor=TP_RECT_COLOR,
                  opacity=0.4, line_width=0, xref="x", yref="y",
                  x0=meta["entry_time"], x1=df.index[-1],
                  y0=min(meta["entry_price"], meta["adj_tp"]),
                  y1=max(meta["entry_price"], meta["adj_tp"]))

    # Initial TP line (bold green)
    fig.add_shape(type="line", layer="above", xref="x", yref="y",
                  x0=meta["entry_time"], x1=df.index[-1],
                  y0=meta["initial_tp"], y1=meta["initial_tp"],
                  line=dict(color=INIT_TP_LINE_COLOR, width=3))

    # Adjusted SL rectangle (red zone)
    fig.add_shape(type="rect", layer="below", fillcolor=ADJ_SL_RECT_COLOR,
                  opacity=0.4, line_width=0, xref="x", yref="y",
                  x0=meta["entry_time"], x1=df.index[-1],
                  y0=min(meta["entry_price"], meta["adj_sl"]),
                  y1=max(meta["entry_price"], meta["adj_sl"]))

    # Original SL line (bold red)
    fig.add_shape(type="line", layer="above", xref="x", yref="y",
                  x0=meta["entry_time"], x1=df.index[-1],
                  y0=meta["orig_sl"],     y1=meta["orig_sl"],
                  line=dict(color=ORIG_SL_LINE_COLOR, width=3))

    # Info annotation (UID, touches)
    info = (
        (f"UID: {meta['trade_uid']}" if meta['trade_uid'] else "UID: —")
        + f"<br>1st Touch: {meta['first_touch']:%Y-%m-%d %H:%M}"
        + f"<br>2nd Touch: {meta['second_touch']:%Y-%m-%d %H:%M}"
        + f"<br>TP init: {meta['initial_tp']:.2f}"
        + f"<br>TP adj:  {meta['adj_tp']:.2f}"
        + f"<br>SL init: {meta['orig_sl']:.2f}"
        + f"<br>SL adj:  {meta['adj_sl']:.2f}"
    )

    if meta.get("result"):
        info += f"<br>Result: {meta['result'].capitalize()}"
    if meta.get("profit") is not None:
        info += f"<br>Profit: {meta['profit']:+.2f}"

    fig.add_annotation(xref="paper", yref="paper", x=0.01, y=0.99,
                       text=info, showarrow=False, bgcolor="white",
                       bordercolor="black", borderwidth=1, opacity=0.9,
                       font=dict(size=12))

    return fig

# ── Main entry point ──────────────────────────────────────────────────

from pathlib import Path

def _main():
    # ── Clean up old charts ───────────────────────────────────────────
    for f in Path().glob("*.html"):
        try:
            f.unlink()
        except OSError:
            pass

    # 1. Acquire raw block --------------------------------------------
    if len(sys.argv) > 1:
        raw_block = " ".join(sys.argv[1:])
    else:
        print("Paste the trade block, then press Ctrl-D (␛ on Windows) …")
        raw_block = sys.stdin.read()

    trade = parse_trade_block(raw_block)

    # 2. Load & slice price data --------------------------------------
    df_m1 = load_m1(CSV_PATH).tz_convert(VIEW_TZ)
    start = trade["fvg_created"] - timedelta(minutes=LOOKBACK_MIN)
    if trade.get("exit_time"):
        end = trade["exit_time"] + timedelta(minutes=AFTER_EXIT_MIN)
    else:
        end = trade["second_touch"] + timedelta(minutes=FWD_FALLBACK)

    win_1m = slice_window(df_m1, start, end)
    m5, m15 = resample_full(df_m1)
    win_5m = slice_window(m5, start, end)
    win_15m = slice_window(m15, start, end)

    # 3. Generate figures ---------------------------------------------
    figs = {
        "1m":  make_candle_fig(win_1m,  "1-minute",  trade),
        "5m":  make_candle_fig(win_5m,  "5-minute",  trade),
        "15m": make_candle_fig(win_15m, "15-minute", trade),
    }

    # 4. Save & open ---------------------------------------------------
    base = f"trade_{trade['fvg_created']:%Y%m%d_%H%M}"
    for name, fig_obj in figs.items():
        out = Path(f"{base}_{name}.html")
        fig_obj.write_html(out, include_plotlyjs="cdn")
        webbrowser.open_new_tab(out.as_uri())

# Almost same thing as main, just here to execute from another file. 
def analyze_trade(raw_block: str, out_dir: Path) -> Path:

    trade = parse_trade_block(raw_block)

    df_m1 = load_m1(CSV_PATH).tz_convert(VIEW_TZ)
    start = trade["fvg_created"] - timedelta(minutes=LOOKBACK_MIN)
    if trade.get("exit_time"):
        end = trade["exit_time"] + timedelta(minutes=AFTER_EXIT_MIN)
    else:
        end = trade["second_touch"] + timedelta(minutes=FWD_FALLBACK)

    win_1m = slice_window(df_m1, start, end)
    m5, m15 = resample_full(df_m1)
    win_5m  = slice_window(m5, start, end)
    win_15m = slice_window(m15, start, end)

    figs = {
        "1m":  make_candle_fig(win_1m,  "1-minute",  trade),
        "5m":  make_candle_fig(win_5m,  "5-minute",  trade),
        "15m": make_candle_fig(win_15m, "15-minute", trade),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    name_map = {"1m": "1m.html", "5m": "5m.html", "15m": "15m.html"}
    for tf, fig in figs.items():
        out = out_dir / name_map[tf]         
        fig.write_html(out, include_plotlyjs="cdn")
        webbrowser.open_new_tab(out.as_uri())  

    return out_dir

if __name__ == "__main__":
    _main()
