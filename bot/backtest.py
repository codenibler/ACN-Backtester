import matplotlib as mpl
mpl.use("Agg", force = True)  
import matplotlib.pyplot as plt
plt.ioff()
from backtesting import Backtest
from .strategy     import QQQIntradayFVG
from .data         import fetch_csv_data
import datetime as dt
from .trade_log import TRADE_LOG, log_trade

mpl.rcParams["timezone"] = "Europe/Madrid"

def run_backtest(progress_cb=None):

    TRADE_LOG.clear() 

    if progress_cb:
        progress_cb(0)

    # 1. get all three frames
    candles = fetch_csv_data()

    # 2. hand the dict to the strategy class
    QQQIntradayFVG.candles = candles

    # 3. run Backtesting on the 1-minute DataFrame only
    bt = Backtest(
        candles["1m"],
        QQQIntradayFVG,
        cash       = 200_000,
        commission = 0.0,
    )
    results = bt.run()   

    # keep only the fields you care about  ↓↓↓
    KEEP = [
        "Duration", "Exposure Time [%]",
        "Equity Final [$]", "Equity Peak [$]", "Return [%]",
        "Sharpe Ratio", "Sortino Ratio", "Calmar Ratio",
        "Alpha [%]", "Beta",
        "Max. Drawdown [%]", "Avg. Drawdown [%]",
        "Max. Drawdown Duration", "Avg. Drawdown Duration",
        "# Trades", "Win Rate [%]", "Best Trade [%]", "Worst Trade [%]",
        "Avg. Trade [%]", "Max. Trade Duration", "Avg. Trade Duration",
        "Profit Factor", "Kelly Criterion",
    ]

    # Pandas Series supports label-based selection
    results = results.filter(items=[k for k in KEEP if k in results])

    if progress_cb:
        progress_cb(100)

    return TRADE_LOG, results

# Keep CLI behaviour exactly the same
if __name__ == "__main__":          # python3 backtest.py
    trades, results = run_backtest()
