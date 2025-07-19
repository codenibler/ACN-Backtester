# === Libraries ========
from __future__ import annotations
import html, re
import sys
import traceback
import pandas as pd

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from Trade_Analyzer import logic
from bot import data, backtest  
from update import check_for_updates
from preformance import find_preformance

from PySide6.QtCore import Qt, QDate, QThread, Signal, QObject, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QMovie, QGuiApplication, QPixmap, QImageReader, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDateEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QLayout
)

# ──────────────────────────────────────────────────────────────
# Paths / resources
# ──────────────────────────────────────────────────────────────
DOWNLOADS_DIR = Path.home() / "Downloads" / "BacktesterOutputs"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
GIF_PATH   = BASE / "loading.gif"     
LOGO_PATH = BASE / "ACNBanner.png"      
tz = ZoneInfo("Europe/Madrid")
# ──────────────────────────────────────────────────────────────
# Worker threads
# ──────────────────────────────────────────────────────────────
class BaseWorker(QThread):
    progress_update = Signal(int)
    error = Signal(str)

class BacktestWorker(BaseWorker):
    finished = Signal(object, object)  # trades, results

    def __init__(self, start_dt: datetime, end_dt: datetime, parent: QObject | None = None):
        super().__init__(parent)
        self.start_dt = start_dt
        self.end_dt = end_dt

    def run(self) -> None:  # noqa: D401
        try:
            # trades = run_backtest(self.start_dt, self.end_dt, self.progress_update.emit)
            # --- mock workload ---

            data.START_DATE = self.start_dt.replace(tzinfo=tz)
            data.END_DATE   = self.end_dt.replace(tzinfo=tz)

            trades, results = backtest.run_backtest(self.progress_update.emit)
            trades = find_preformance(trades, data.fetch_csv_data()["1m"])

            self.finished.emit(trades, results)

        except Exception:
            self.error.emit(traceback.format_exc())

class AnalysisWorker(BaseWorker):
    finished = Signal(Path)

    def __init__(self, trade_txt: str, out_dir: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.trade_txt = trade_txt
        self.out_dir = out_dir

    def run(self) -> None:                 
        try:
            for f in self.out_dir.glob("*.html"):
                try:
                    f.unlink()
                except OSError:
                    pass

            result_folder = logic.analyze_trade(
                self.trade_txt,
                self.out_dir
            )
            self.finished.emit(result_folder)

        except Exception:
            self.error.emit(traceback.format_exc())

# ──────────────────────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────────────────────
class MainWindow(QWidget):
    
    COLS = [
        "FVG Type",
        "Trade Type",
        "Gap created",
        "FVG Bounds",
        "First Touch",
        "Second Touch",
        "Trade Entry Time",
        "Trade Entry Price",
        "Take Profit (init)",
        "Take Profit (adj)",
        "Stop Loss (init)",
        "Stop Loss (adj)",
        "Risk to Reward Ratio",
        "Trade UID",
        "Exit Time",
        "Exit Price",
        "Result",
        "Profit"
    ]


    def download_data(self, trades) -> None:
        if not trades:
            QMessageBox.warning(self, "No Trades", "No trades to download.")
            return
            
        # Create a DataFrame from the trades list
        df = pd.DataFrame(trades)
        csv_path = DOWNLOADS_DIR / "trades.csv"
        df.to_csv(csv_path, index=False)
        
        uri = QUrl.fromLocalFile(str(csv_path))       

        msg = QMessageBox(self)
        msg.setWindowTitle("Download Complete")
        msg.setTextFormat(Qt.RichText)
        msg.setText(
            f'Trade data saved to '
            f'<a href="{uri.toString()}">{csv_path.name}</a>'
        )
        # allow the label to open external links via QDesktopServices on click
        msg.setTextInteractionFlags(Qt.TextBrowserInteraction)
        msg.exec()                              


    def _show_results_popup(self, trades, results) -> None:
        raw = str(results)

        rows = []
        zebra = ("#1a1a1a", "#141414")          # two dark grays for alt rows
        for idx, line in enumerate(raw.splitlines()):
            if not line.strip():
                continue

            parts = re.split(r'\s{2,}', line.strip())
            bg = zebra[idx % 2]                 # alternate background colour

            if len(parts) == 1:                 # header‐style line
                rows.append(
                    f"<tr style='background:{bg};'>"
                    f"<td colspan='2' style='padding:4px 0; font-weight:bold;'>"
                    f"{html.escape(parts[0])}"
                    "</td></tr>"
                )
            else:
                label = " ".join(parts[:-1])
                value = parts[-1]
                rows.append(
                    f"<tr style='background:{bg};'>"
                    f"<td style='padding:2px 1em 2px 0;'>{html.escape(label)}</td>"
                    f"<td style='text-align:right; font-weight:bold;'>{html.escape(value)}</td>"
                    "</tr>"
                )

        html_body = (
            "<table style='border-collapse:collapse; width:100%; "
            "border:1px solid #333;'>"
            + "".join(rows) +
            "</table></div>"
        )

        # ── QMessageBox setup ──────────────────────────────────────────────
        msg = QMessageBox(self)
        msg.setWindowTitle("Backtest Results")
        msg.setTextFormat(Qt.RichText)
        msg.setText(html_body)
        msg.setStandardButtons(QMessageBox.Ok)

        perf_btn = msg.addButton("Download Trade Data", QMessageBox.ActionRole)
        perf_btn.clicked.connect(lambda _=None, t=trades: self.download_data(t))

        msg.setStyleSheet(self.styleSheet())         
        msg.layout().setSizeConstraint(QLayout.SetFixedSize)
        msg.setMinimumSize(600, 400)
        msg.adjustSize()
        msg.setWindowModality(Qt.NonModal)   
        msg.show()

        # ── Dock to right edge ────────────────────────────────────────────
        screen_geo = QGuiApplication.primaryScreen().availableGeometry()
        box_geo    = msg.frameGeometry()
        x = screen_geo.right() - box_geo.width() - 20   # 20-px margin
        y = screen_geo.top() + (screen_geo.height() - box_geo.height()) // 2
        msg.move(x, y)        

    def __init__(self) -> None:
        super().__init__()
    
        self.setWindowTitle("ACN Backtester")
        self.resize(750, 500)
        x_main = 120
        y_main = 100
        self.move(x_main, y_main) 
        self.setStyleSheet(self._dark_stylesheet())
        self._setup_ui()
        self.bt_worker: BacktestWorker | None = None
        self.an_worker: AnalysisWorker | None = None

    @staticmethod
    def _parse_trade_block(txt: str) -> dict[str, str]:
        out = {}
        for line in txt.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
        return out
    

    # UI
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        # 1) Create your controls first
        self.from_date = QDateEdit(calendarPopup=True)
        self.to_date   = QDateEdit(calendarPopup=True)
        self.from_date.setDate(QDate(2024, 12, 29))
        self.to_date.setDate(QDate(2025,  6, 28))

        self.run_btn = QPushButton("Run back-test")
        self.run_btn.clicked.connect(self._kick_off_backtest)

        reader = QImageReader(str(LOGO_PATH))
        reader.setAutoTransform(True)
        img = reader.read()
        if img.isNull():
            raise RuntimeError(f"Failed to load logo: {reader.errorString()}")

        # 2) Figure out your screen’s devicePixelRatio (e.g. 2 on Retina):
        dpi_scale = QGuiApplication.primaryScreen().devicePixelRatio()

        # 3) Scale the image _in its native QImage_ up to exactly 32px logical height:
        #    multiply by the devicePixelRatio so that when Qt divides it back down it stays sharp.
        target_h = int(32 * dpi_scale)
        img = img.scaledToHeight(target_h, Qt.SmoothTransformation)

        # 4) Convert to QPixmap, tell it about the DPR, and stick it in a QLabel:
        pix = QPixmap.fromImage(img)
        pix.setDevicePixelRatio(dpi_scale)

        logo = QLabel()
        logo.setPixmap(pix)
        logo.setFixedHeight(32)         # logical height
        logo.setFixedWidth(pix.width() / dpi_scale)
        logo.setScaledContents(False)   # absolutely no further scaling

        # 3) Lay out the top bar: dates on left, centre-widget (with logo), button on right
        top = QHBoxLayout()
        top.addWidget(logo); 
        top.addStretch(1)
        top.addWidget(QLabel("From:"));  top.addWidget(self.from_date)
        top.addWidget(QLabel("To:"));    top.addWidget(self.to_date)
        top.addWidget(self.run_btn)      # stuck right
        root.addLayout(top)

        # Trade table
        self.table = QTableWidget(0, len(self.COLS) + 1)
        
        self.table.setHorizontalHeaderLabels(["Analyze"] + self.COLS)
        root.addWidget(self.table)

        vw = self.table.viewport()                       # cache the viewport
        self.loader_lbl = QLabel(vw)                     # parent = viewport
        self.loader_lbl.setFixedSize(340, 340)
        self.loader_lbl.setScaledContents(True)
        self.loader_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)

        gif = QMovie(str(GIF_PATH))                      # file sits next to main.py
        self.loader_lbl.setMovie(gif)
        self.loader_lbl.hide()                           # hidden by default

        # keep it anchored bottom-right even if window resizes
        def _reposition_loader():
            x = vw.width()  - self.loader_lbl.width()  - 8
            y = vw.height() - self.loader_lbl.height() - 8
            self.loader_lbl.move(x, y)

        vw.installEventFilter(self)                      # track viewport resize
        self._reposition_loader = _reposition_loader
        self._reposition_loader()                        # initial placement

    # Slots
    def _kick_off_backtest(self) -> None:
        self._set_ui_state(running=True)
        start_dt = self.from_date.dateTime().toPython()   # returns datetime
        end_dt   = self.to_date.dateTime().toPython()
        self.bt_worker = BacktestWorker(start_dt, end_dt, self)
        self.bt_worker.error.connect(self._show_traceback)
        self.bt_worker.finished.connect(lambda trades, results: self._populate_trades(trades, results))           
        self.bt_worker.start()

    def _populate_trades(self, trades: list, results: str) -> None:
        self.table.setRowCount(0)

        self._show_results_popup(trades, results)

        for r, txt in enumerate(trades):
            if isinstance(txt, list):
                txt = "\n".join(map(str, txt))

            row = self._parse_trade_block(txt)

            self.table.insertRow(r)

            # Analyze button
            btn = QPushButton("Analyze")
            btn.setObjectName("AnalyzeButton")
            btn.clicked.connect(lambda _=None, t=txt: self._begin_analysis(t))
            self.table.setCellWidget(r, 0, btn)

            # Data columns – value only
            for c, key in enumerate(self.COLS, start=1):
                item = QTableWidgetItem(row.get(key, ""))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, item)

        self._set_ui_state(running=False)

    def _begin_analysis(self, trade_txt: str) -> None:     
        self.an_worker = AnalysisWorker(trade_txt, DOWNLOADS_DIR, self)        
        self.an_worker.error.connect(self._show_traceback)
        self.an_worker.finished.connect(self._analysis_done)
        self.an_worker.start()

    def _analysis_done(self, folder: Path) -> None:
        # Pop the folder open in Finder so files are visible immediately
        self._set_ui_state(running=False)

    # Helpers
    def _set_ui_state(self, *, running: bool | None = None) -> None:
        self.run_btn.setEnabled(not running)

        # loader GIF visibility
        if running:
            self._reposition_loader()      # ← make sure it’s at the correct spot
            self.loader_lbl.raise_()       # ← ensure it paints above the table
            self.loader_lbl.show()
            self.loader_lbl.movie().start()
        else:
            self.loader_lbl.hide()
            self.loader_lbl.movie().stop()

    def _show_traceback(self, tb: str) -> None:
        QMessageBox.critical(self, "Error", tb)
        self._set_ui_state(running=False)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        for w in (self.bt_worker, self.an_worker):
            if w and w.isRunning():
                w.terminate()
        event.accept()

    # Dark stylesheet
    @staticmethod
    def _dark_stylesheet() -> str:
        return (
            "QWidget { background-color: #0d0d0d; color: #e0e0e0; }"
            "QTableWidget { background-color: #1a1a1a; gridline-color: #333; selection-background-color: #333; }"
            "QHeaderView::section { background-color: #111; color: #e0e0e0; border: 1px solid #333; }"
            "QPushButton { background-color: #2b2b2b; border: 1px solid #555; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #444; }"
            "QPushButton#AnalyzeButton { background-color: #555; border: 1px solid #888; font-weight: bold; }"
            "QPushButton#AnalyzeButton:hover { background-color: #777; }"
        )

# ──────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    check_for_updates()
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()