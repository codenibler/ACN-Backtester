from typing import List

TRADE_LOG: List[str] = []

def log_trade(txt: str) -> None:
    TRADE_LOG.append(txt)