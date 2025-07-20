# ---------- strategy.py INTEGRATED WITH GUI ----------
import pandas as pd
from datetime import date, timedelta
from backtesting import Strategy
from .state import Context, FVG
from .config import in_session, min_fvg_points, sl_max_candles, minimum_retracement_score, \
                                min_space_from_fvg_to_1st_touch, lot_size, structure_search_bars
from itertools import count 
from .trade_log import log_trade

uid_gen = count(1)
class QQQIntradayFVG(Strategy):
    _last_15m_ts: pd.Timestamp | None = None      # ① at class level
    ctx: Context = Context()   
    candles: None

    # ────────────────────── helpers ────────────────────────────
    def _on_new_15m(self, bar_end) -> None:
        
        # Grab our known 15m candles
        candles_15m = self.candles["15m"]

        # grab the *three* bars that ended at bar_end, bar_end-15m, bar_end-30m
        window = candles_15m.loc[
            bar_end - pd.Timedelta(minutes=30) : bar_end
        ]
        # If we don't have at least 3 15m candles, can't check for FVG
        if len(window) < 3:
            return

        # 3 candle pattern
        first, second, third = window.iloc[0], window.iloc[1], window.iloc[2]
        
        # Check if all 3 are same color 
        same_colour = (
            (first.Close > first.Open) and
            (second.Close > second.Open) and
            (third.Close > third.Open)
        ) or (
            (first.Close < first.Open) and
            (second.Close < second.Open) and
            (third.Close < third.Open)
        )
        
        # If all 3 candles are the same color, we can check whether an FVG was created. 
        if same_colour:
            # Bullish FVG
            if third['Low'] > first['High'] and abs(third['Low'] - first['High']) >= min_fvg_points:
                # Make sure we are not creating a duplicate FVG
                if not any(fvg.created_at == third.name for fvg in self.ctx.active_fvgs):
                    self.ctx.active_fvgs.append(FVG(kind= "bullish", direction="short", top= third['Low'], bottom= first["High"], created_at= third.name))
            # Bearish FVG
            elif third['High'] < first['Low'] and abs(third['High'] - first['Low']) >= min_fvg_points:
                # Make sure we are not creating a duplicate FVG
                if not any(fvg.created_at == third.name for fvg in self.ctx.active_fvgs):
                    self.ctx.active_fvgs.append(FVG(kind= "bearish", direction="long", top = first["Low"], bottom = third['High'], created_at = third.name))


    def check_first_touch_5m(self, ts: pd.Timestamp):
        current_bar = self.candles["5m"].loc[ts] 
        prev_ts = self.candles["5m"].index.get_loc(ts) - 1
        prev_bar = self.candles["5m"].iloc[prev_ts]         

        for fvg in list(self.ctx.active_fvgs):

            # If bar gaps over the entire FVG, delete it. 
            if (current_bar["High"] > fvg.top) and (current_bar["Low"] < fvg.bottom):
                    self.ctx.active_fvgs.remove(fvg)
                    continue
            
            """SHORT CHECK"""
            if (fvg.first_touch_at == None) and (fvg.direction == "short"):
                # Define what reentering the FVG means 
                inside =((fvg.bottom <= current_bar["Low"] <= fvg.top) \
                        or (fvg.bottom <= current_bar["Close"] <= fvg.top)) \
                        and (prev_bar["Low"] > fvg.top)
                
                # If we reentered, we check the ladder pattern to decide 
                # Whether to keep the FVG or not
                if inside:
                    # Check 5m structure and pass in the FVG creation time and reentry time.       created the FVG, don't count it as a reentry
                    valid = self.five_min_structure(fvg.created_at, current_bar.name, fvg)
                    if not valid:
                        self.ctx.active_fvgs.remove(fvg)
                    else:
                        fvg.first_touch_at = current_bar.name
            
            """LONG CHECK"""
            if fvg.first_touch_at == None and fvg.direction == "long":
                # Define what reentering the FVG means 
                inside =((fvg.bottom <= current_bar["High"] <= fvg.top) \
                        or (fvg.bottom <= current_bar["Close"] <= fvg.top)) \
                        and (prev_bar["High"] < fvg.bottom)
                
                # If we reentered, we check the ladder pattern to decide 
                # Whether to keep the FVG or not         
                if inside:
                    valid = self.five_min_structure(fvg.created_at, current_bar.name, fvg)
                    if not valid:
                        self.ctx.active_fvgs.remove(fvg)
                    else:
                        fvg.first_touch_at = current_bar.name
    

    def five_min_structure(self, start_ts, end_ts, fairvgap) -> bool:
        # Includes all candles from the forming of the FVG up to reentry
        df5_all = self.candles["5m"].loc[start_ts:end_ts]      

        # Need at least 2 transitions, not one large candle dropping in
        # If less than 3 candles, automatically remove fvg from memory
        if len(df5_all) < min_space_from_fvg_to_1st_touch:                                 
            return False

        """Shorts"""             
        idx_highest = df5_all['High'].idxmax()    # Returns row index of Highest High
        df5_short = df5_all.loc[idx_highest:]     # Create array ONLY with candles after higher high until reentry
        df5_short = df5_short.iloc[1:]          

        """Longs"""             
        idx_lowest = df5_all['Low'].idxmin()    # Returns row index of Lowest Low
        df5_long = df5_all.loc[idx_lowest:]     # Create array ONLY with candles after lower low until reentry
        df5_long = df5_long.iloc[1:]           

        # For both types of trades, if enither has more than 2 candles, can't check transitions
        if fairvgap.direction == "short" and len(df5_short) < 2:
            return False
        elif fairvgap.direction == "long" and len(df5_long) < 2:
            return False

        # If we are looking for a short, we check the HL LL pattern
        if fairvgap.direction == "short":
            ladder = (
                (df5_short['High'].shift(-1) < df5_short['High']) &
                (df5_short['Low'].shift(-1)  < df5_short['Low'])
            ).iloc[:-1]

        # If we are looking for a long, we check the HH LH pattern
        if fairvgap.direction == "long":
            ladder = (
                (df5_long['High'].shift(-1) > df5_long['High']) &
                (df5_long['Low'].shift(-1) > df5_long['Low'])
            ).iloc[:-1]                                        

        score = ladder.mean()     
    
        # Checks whether 20% or more of the candles in the downward movement set LH and LL. 
        valid = score >= minimum_retracement_score
        return valid
                 

    def _check_second_touch_5m(self, ts: pd.Timestamp) -> None:
        """
        Call on every 5-minute Close.
        If the bar finishes inside an armed FVG, stamp second_touch_at
        and pre-compute the midpoint entry level.
        """
        # fetch the just-Closed 5-minute bar
        current_bar = self.candles["5m"].loc[ts] 
        prev_ts = self.candles["5m"].index.get_loc(ts) - 1
        prev_bar = self.candles["5m"].iloc[prev_ts]        

        for fvg in self.ctx.active_fvgs:
            # work only with gaps that have passed the ladder filter
            if fvg.first_touch_at and fvg.second_touch_at is None:
                # Did 5m Bar enter the FVG and previous bar wasn't inside?
                """SHORT + LONG CHECK"""
                if fvg.direction == "short":
                    # Define what reentering the FVG means 
                    inside =((fvg.bottom <= current_bar["Low"] <= fvg.top) \
                            or (fvg.bottom <= current_bar["Close"] <= fvg.top)) \
                            and (prev_bar["Low"] > fvg.top)
                elif fvg.direction == "long":    
                    # Define what reentering the FVG means 
                    inside =((fvg.bottom <= current_bar["High"] <= fvg.top) \
                            or (fvg.bottom <= current_bar["Close"] <= fvg.top)) \
                            and (prev_bar["High"] < fvg.bottom)

                if inside and ts != fvg.first_touch_at:
                    # ── Mark second touch─────────────────────────────
                    fvg.second_touch_at = ts

                    # 1-minute slab from first-touch → this bar
                    # Set high and low since first touch, calculate entry point. 
                    slab = self.candles["1m"].loc[fvg.first_touch_at:ts]
                    fvg.hi_since_ft = slab["High"].max()
                    fvg.lo_since_ft = slab["Low"].min()
                    fvg.entry_mid   = round((fvg.hi_since_ft + fvg.lo_since_ft) / 2, 2)


    def _maybe_enter_trade_1m(self, ts: pd.Timestamp) -> None:
        """
        Every 1-minute bar after the second touch:
        • keep rolling HH / LL since first touch
        • keep timestamps of the most-recent extreme for SL *and* TP
        • if price crosses the midpoint, derive SL/TP (with structure filters) and send the order
        """
        for fvg in self.ctx.active_fvgs:
            if not (fvg.second_touch_at and not fvg.position_open):
                continue

            # ─── 1) Update running extremes ───────────────────────────────
            hi_changed = lo_changed = False

            if self.data.High[-1] > fvg.hi_since_ft:
                fvg.hi_since_ft = self.data.High[-1]
                hi_changed = True

            if self.data.Low[-1] < fvg.lo_since_ft:
                fvg.lo_since_ft = self.data.Low[-1]
                lo_changed = True

            # stamp which extreme moved for SL / TP bookkeeping
            if hi_changed:
                if fvg.direction == "short":          # hi => SL for shorts, TP for longs
                    fvg.sl_updated_at = ts
                else:
                    fvg.tp_updated_at = ts

            if lo_changed:
                if fvg.direction == "short":          # lo => TP for shorts, SL for longs
                    fvg.tp_updated_at = ts
                else:
                    fvg.sl_updated_at = ts

            # update midpoint after possible extreme changes
            fvg.entry_mid = round((fvg.hi_since_ft + fvg.lo_since_ft) / 2, 2)

            # ─── 2) Wait until price trades through the midpoint ──────────
            crossed = self.data.Low[-1] <= fvg.entry_mid <= self.data.High[-1]
            if not crossed:
                continue

            # ─── 3) Derive **initial** SL / TP from freshest extremes ─────
            if fvg.direction == "short":
                fvg.sl_initial = fvg.hi_since_ft     # protective stop = highest high
                fvg.tp_initial = fvg.lo_since_ft     # profit target  = lowest low
            else:                                    # long
                fvg.sl_initial = fvg.lo_since_ft
                fvg.tp_initial = fvg.hi_since_ft

            if fvg.sl_updated_at is None:
                fvg.sl_updated_at = fvg.second_touch_at        # treat 2-nd touch as last SL mark
            if fvg.tp_updated_at is None:
                fvg.tp_updated_at = fvg.second_touch_at  

            # ─── 4) Structure filters (identical window length) ───────────
            idx_now = self.candles["1m"].index.get_loc(ts)
            idx_sl  = self.candles["1m"].index.get_loc(fvg.sl_updated_at)
            age_sl  = idx_now - idx_sl
            tp_updated = False

            if age_sl <= sl_max_candles:
                new_stop = self._find_sd_stop(fvg, ts, structure_search_bars)
                fvg.sl_adjusted = new_stop
                tp_updated = True
                # If we adjust SL, readjust TP as well to keep the same RR 
                if fvg.direction == "short":
                    fvg.tp_adjusted = round(fvg.entry_mid - (new_stop - fvg.entry_mid), 2)
                else:
                    fvg.tp_adjusted = round(fvg.entry_mid + (fvg.entry_mid - new_stop), 2)
            else:
                fvg.sl_adjusted = fvg.sl_initial

            # TP
            idx_tp = self.candles["1m"].index.get_loc(fvg.tp_updated_at)
            age_tp = idx_now - idx_tp

            if not tp_updated:
                if age_tp <= sl_max_candles:
                    new_tp = self._find_sd_tp(fvg, ts, structure_search_bars)
                    fvg.tp_adjusted = new_tp
                else:
                    fvg.tp_adjusted = fvg.tp_initial
                    
            # ─── 5) Safety guard – never make SL looser or TP harder ──────
            if fvg.direction == "short":
                if fvg.sl_adjusted < fvg.sl_initial:   
                    fvg.sl_adjusted = fvg.sl_initial
                if fvg.tp_adjusted > fvg.tp_initial:   
                    fvg.tp_adjusted = fvg.tp_initial
            else:  # long
                if fvg.sl_adjusted > fvg.sl_initial:
                    fvg.sl_adjusted = fvg.sl_initial
                if fvg.tp_adjusted < fvg.tp_initial:
                    fvg.tp_adjusted = fvg.tp_initial

            # ─── 6) Place order ───────────────────────────────────────────
            if fvg.direction == "short":
                self.sell(size=lot_size,
                        sl=fvg.sl_adjusted,
                        tp=fvg.tp_adjusted,
                        limit=fvg.entry_mid,
                        tag=fvg.uid)
            else:
                self.buy(size=lot_size,
                        sl=fvg.sl_adjusted,
                        tp=fvg.tp_adjusted,
                        limit=fvg.entry_mid,
                        tag=fvg.uid)

            fvg.position_open = True
            fvg.uid = next(uid_gen)  

            # ─── 7) Trade log ─────────────────────────────────────────────
            trade = (
                f"FVG Type= {fvg.kind}\n"
                f"Trade Type= {fvg.direction}\n"
                f"Gap created= {fvg.created_at}\n"
                f"FVG Bounds= {fvg.bottom:.2f}-{fvg.top:.2f}\n"
                f"First Touch= {fvg.first_touch_at}\n"
                f"Second Touch= {fvg.second_touch_at}\n"
                f"Trade Entry Time= {ts}\n"
                f"Trade Entry Price= {fvg.entry_mid:.2f}\n"
                f"Take Profit (init)= {fvg.tp_initial:.2f}\n"
                f"Take Profit (adj)=  {fvg.tp_adjusted:.2f}\n"
                f"Stop Loss (init)=   {fvg.sl_initial:.2f}\n"
                f"Stop Loss (adj)=    {fvg.sl_adjusted:.2f}\n"
                f"Risk to Reward Ratio= {(abs(fvg.tp_adjusted - fvg.entry_mid) / abs(fvg.entry_mid - fvg.sl_adjusted))}\n"
                f"Trade UID= {fvg.uid}\n"
                "─------------------------------------------\n"
            )
            log_trade(trade)


     # ────────────────────── Structure helpers ──────────────────────────
    def _find_sd_stop(self, fvg, ts: pd.Timestamp, lookback: int):
        """
        Return the protective stop based on proven structure.
        • Skip the entry candle **and the four candles before it** (-5 minutes total).
        • Then look back `lookback` further minutes for the extreme.
        """
        end   = ts - pd.Timedelta(minutes=5)              # last bar to include
        start = end - pd.Timedelta(minutes=lookback - 1)  # first bar to include
        slab  = self.candles["1m"].loc[start:end]

        if slab.empty:                                    # fallback
            return fvg.sl_initial

        if fvg.direction == "short":
            return slab.High.max()
        else:                                             # long
            return slab.Low.min()

    def _find_sd_tp(self, fvg, ts: pd.Timestamp, lookback: int):
        """
        Return the take-profit based on proven structure.
        • Skip the entry candle **and the four candles before it** (-5 minutes total).
        • Then look back `lookback` further minutes for the extreme.
        """
        end   = ts - pd.Timedelta(minutes=5)
        start = end - pd.Timedelta(minutes=lookback - 1)
        slab  = self.candles["1m"].loc[start:end]

        if slab.empty:
            return fvg.tp_initial

        if fvg.direction == "short":
            return slab.Low.min()
        else:                                             # long
            return slab.High.max()



    # ────────────────────── Strategy API ───────────────────────
    def init(self):
        self.candles = {
            "1m": pd.DataFrame(columns=["Open","High","Low","Close","Volume"]),
            "5m": pd.DataFrame(columns=["Open","High","Low","Close","Volume"]),
            "15m": pd.DataFrame(columns=["Open","High","Low","Close","Volume"]),
        }
        self.ctx = Context()

    def next(self):
        ts: pd.Timestamp = self.data.index[-1]     # current 1-m bar close          
        # 1) Session gate
        if not in_session(ts):
            if self.position:
                self.position.close()
            self.ctx.reset_session()
            return
        self.candles["1m"].loc[ts] = [
            self.data.Open[-1], self.data.High[-1],
            self.data.Low[-1],  self.data.Close[-1],
            self.data.Volume[-1],
        ]

        if ts.minute % 5 == 0:
            slice5 = self.candles["1m"].iloc[-5:]
            self.candles["5m"].loc[ts] = [
                slice5.Open.iloc[0],
                slice5.High.max(),
                slice5.Low.min(),
                slice5.Close.iloc[-1],
                slice5.Volume.sum(),
            ]
            self.check_first_touch_5m(ts)
            self._check_second_touch_5m(ts)

        if ts.minute % 15 == 0:
            slice15 = self.candles["1m"].loc[ts - pd.Timedelta(minutes=14): ts]
            self.candles["15m"].loc[ts] = [
                slice15.Open.iloc[0],
                slice15.High.max(),
                slice15.Low.min(),
                slice15.Close.iloc[-1],
                slice15.Volume.sum(),
            ]
            self._on_new_15m(ts)          # <── pass the timestamp you just built
    
        # 4) Run 1-m micro-structure every bar
        self._maybe_enter_trade_1m(ts)

        # 5) Maintain session high/low (optional for risk stats)
        #    self.ctx.session_high = max(self.ctx.session_high or -inf, self.data.High[-1])
        #    self.ctx.session_low  = min(self.ctx.session_low  or  inf, self.data.Low[-1])
