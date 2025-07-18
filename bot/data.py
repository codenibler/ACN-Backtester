import pandas as pd
import datetime as dt
from pathlib import Path
import sys

START_DATE: dt.datetime | None = None
END_DATE  : dt.datetime | None = None

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) 
CSV  = BASE / "NQ.txt"                                      

def fetch_csv_data():
    # Read data in from CSV
    df_1m = pd.read_csv(CSV, 
                    names=["date", "time", "Open", "High", "Low", "Close", "Volume"],
                    parse_dates=[["date", "time"]],
                    infer_datetime_format=True)
    
    if df_1m.empty:
        raise ValueError(f"CSV file {CSV} is empty or not found.")

    df_1m.rename(columns={"date_time": "Timestamp"}, inplace=True)
    df_1m.set_index("Timestamp", inplace=True)
    df_1m.index = (
        df_1m.index
            .tz_localize("America/New_York")  # if the CSV is in NY time
            .tz_convert("Europe/Amsterdam")   # optional
    )
    # Splice data to last 2 months. 
    df_1m = df_1m[df_1m.index >= START_DATE] 
    df_1m = df_1m[df_1m.index <= END_DATE] 

    # Resample 5m and 15m columns 
    df_5m  = df_1m.resample("5min", label="right").agg({
        "Open":  "first",
        "High":  "max",
        "Low":   "min",
        "Close": "last",
        "Volume": "sum"
    }).dropna()

    df_15m = df_1m.resample("15min", label="right").agg({
        "Open":  "first",
        "High":  "max",
        "Low":   "min",
        "Close": "last",
        "Volume": "sum"
    }).dropna()

    return {"1m": df_1m, "5m": df_5m, "15m": df_15m}
