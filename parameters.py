# === Libraries ========
from __future__ import annotations
import sys 
from pathlib import Path

from bot.config import min_fvg_points, ignore_time_zone, sl_max_candles, minimum_retracement_score, \
                        min_space_from_fvg_to_1st_touch, lot_size, PARAMETER_COUNT
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QSizePolicy,
    QFrame,
    QSpinBox,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))

class ParameterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        
        font_path = BASE / "OliviarSans-Light.ttf"
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        ACN_font = QFontDatabase.applicationFontFamilies(font_id)[0]

        self.setFont(ACN_font)
        self.setWindowTitle("Change Parameters")
        self.setFixedSize(500, 600)
        self.setModal(False)
        self.move(200, 150)

        NUMBER_INPUT_WIDTH = 60

        min_fvg_holder = QHBoxLayout()
        min_fvg_text_holder = QVBoxLayout()
        min_fvg_text_holder.addStretch()
        min_fvg_text_holder.setSpacing(2)
        min_fvg_text_holder.addWidget(QLabel("**Minimum FVG Size**", wordWrap=True, textFormat=Qt.TextFormat.MarkdownText))
        min_fvg_text_holder.addWidget(QLabel("*Minimum FVG size to consider trades(In NQ1! Index Points):*", textFormat=Qt.TextFormat.MarkdownText))
        min_fvg_holder.addLayout(min_fvg_text_holder)        
        min_fvg_value = QSpinBox()
        min_fvg_value.setFixedWidth(NUMBER_INPUT_WIDTH)
        min_fvg_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        min_fvg_holder.addStretch()
        min_fvg_holder.addWidget(min_fvg_value)

        ignore_tz_holder = QHBoxLayout()
        ignore_tz_text_holder = QVBoxLayout()
        ignore_tz_text_holder.addStretch()
        ignore_tz_text_holder.setSpacing(2)
        ignore_tz_text_holder.addWidget(QLabel("**Ignore Time Zone**", wordWrap=True, textFormat=Qt.TextFormat.MarkdownText))
        ignore_tz_text_holder.addWidget(QLabel("*Ignore Time Zones? ___Write True or False___ (Default if True are 10:00:18:45)*", textFormat=Qt.TextFormat.MarkdownText, wordWrap=True)) 
        ignore_tz_holder.addLayout(ignore_tz_text_holder, 1)
        ignore_tz_value = QLineEdit(maxLength=5, text="True", alignment=Qt.AlignmentFlag.AlignCenter)
        ignore_tz_value.setFixedWidth(NUMBER_INPUT_WIDTH)
        ignore_tz_holder.addStretch()
        ignore_tz_holder.addWidget(ignore_tz_value, 0)

        sl_max_candles_holder = QHBoxLayout()
        sl_max_candles_text_holder = QVBoxLayout()
        sl_max_candles_text_holder.addStretch()
        sl_max_candles_text_holder.setSpacing(2)
        sl_max_candles_text_holder.addWidget(QLabel("**Entry SL/TP Lookback Candles**", textFormat=Qt.TextFormat.MarkdownText))
        sl_max_candles_text_holder.addWidget(QLabel("*Number of Candles to Check if SL or TP was set in proximity to entry point. If smaller/equal to this number, we search back in structure for X bars. \"X bars\" parameter is below*", textFormat=Qt.TextFormat.MarkdownText, wordWrap=True))
        sl_max_candles_holder.addLayout(sl_max_candles_text_holder, 1)
        sl_max_candles_value = QSpinBox()
        sl_max_candles_value.setFixedWidth(NUMBER_INPUT_WIDTH)
        sl_max_candles_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl_max_candles_holder.addStretch()
        sl_max_candles_holder.addWidget(sl_max_candles_value, 0)

        structure_search_holder = QHBoxLayout()
        structure_search_text_holder = QVBoxLayout()
        structure_search_text_holder.addStretch()
        structure_search_text_holder.setSpacing(2)
        structure_search_text_holder.addWidget(QLabel("**Structure Search Lookback Candles**", textFormat=Qt.TextFormat.MarkdownText))
        structure_search_text_holder.addWidget(QLabel("*Number of candles to search for significant point of structure after SL / TP is found to be set too close to entry point (In 1m candles)*", wordWrap=True, textFormat=Qt.TextFormat.MarkdownText))
        structure_search_holder.addLayout(structure_search_text_holder, 1)
        structure_search_value = QSpinBox()
        structure_search_value.setFixedWidth(NUMBER_INPUT_WIDTH)
        structure_search_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        structure_search_holder.addStretch()
        structure_search_holder.addWidget(structure_search_value, 0)

        min_retracement_holder = QHBoxLayout()
        min_retracement_text_holder = QVBoxLayout()
        min_retracement_text_holder.addStretch()
        min_retracement_text_holder.setSpacing(2)
        min_retracement_text_holder.addWidget(QLabel("**Minimum Retracement Pattern Percent**", textFormat=Qt.TextFormat.MarkdownText))
        min_retracement_text_holder.addWidget(QLabel("*Minimum percentage of candle movements from 1st touch to reentry setting LH LL / HH HL patterns*", wordWrap=True, textFormat=Qt.TextFormat.MarkdownText))
        min_retracement_holder.addLayout(min_retracement_text_holder, 1)
        min_retracement_value = QSpinBox()
        min_retracement_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        min_retracement_value.setFixedWidth(NUMBER_INPUT_WIDTH)
        min_retracement_holder.addStretch()
        min_retracement_holder.addWidget(min_retracement_value, 0)

        min_space_from_1st_holder = QHBoxLayout()
        min_space_from_1st_text_holder = QVBoxLayout()
        min_space_from_1st_text_holder.addStretch()
        min_space_from_1st_text_holder.setSpacing(2)
        min_space_from_1st_text_holder.addWidget(QLabel("**Min Candles: FVG to Reentry**", textFormat=Qt.TextFormat.MarkdownText))
        min_space_from_1st_text_holder.addWidget(QLabel("*Minimum candles from FVG's Creation to 1st reentry. Used to avoid immediate reentry scenarios (In 5m candles)*", wordWrap=True, textFormat=Qt.TextFormat.MarkdownText))
        min_space_from_1st_holder.addLayout(min_space_from_1st_text_holder, 1)
        min_space_from_1st_value = QSpinBox()
        min_space_from_1st_value.setFixedWidth(NUMBER_INPUT_WIDTH)
        min_space_from_1st_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        min_space_from_1st_holder.addStretch()
        min_space_from_1st_holder.addWidget(min_space_from_1st_value, 0)

        lot_sizing_holder = QHBoxLayout()
        lot_sizing_text_holder = QVBoxLayout()
        lot_sizing_text_holder.addStretch()
        lot_sizing_text_holder.setSpacing(2)
        lot_sizing_text_holder.addWidget(QLabel("**Lot Size**", textFormat=Qt.TextFormat.MarkdownText))
        lot_sizing_text_holder.addWidget(QLabel("*More specifically, number of lots every entry. Consider NQ hovers around 20k index points, meaning that simulating with a 200,000 Euro account, 10 lots is already bigger than the entire account. Trade responsibly, buddy.*", wordWrap=True, textFormat=Qt.TextFormat.MarkdownText))
        lot_sizing_holder.addLayout(lot_sizing_text_holder, 1)
        lot_sizing_value = QSpinBox()
        lot_sizing_value.setFixedWidth(NUMBER_INPUT_WIDTH)
        lot_sizing_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lot_sizing_holder.addStretch()
        lot_sizing_holder.addWidget(lot_sizing_value, 0)

        save_button_holder = QHBoxLayout()
        save_button_holder.addStretch(1)   
        save_btn = QPushButton("Save Strategy Parameters")
        save_btn.setStyleSheet("""QPushButton {border-radius: 2px;}""")   
        save_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        save_button_holder.addWidget(save_btn)

        title = QLabel("Strategy Parameters")
        title.setStyleSheet("font-size:20px; font-weight:bold; font-weight:italic;")

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)   
        line.setFixedHeight(2)  
        line.setStyleSheet("background-color: gray;")

        title_layout = QVBoxLayout()
        title_layout.addWidget(title)
        title_layout.addWidget(line)

        panel = QVBoxLayout()
        panel.addLayout(title_layout)
        panel.addLayout(min_fvg_holder);            panel.addLayout(ignore_tz_holder)
        panel.addLayout(sl_max_candles_holder);     panel.addLayout(structure_search_holder)
        panel.addLayout(min_retracement_holder);    panel.addLayout(min_space_from_1st_holder)
        panel.addLayout(lot_sizing_holder);         panel.addSpacing(20)
        panel.addLayout(save_button_holder)
        panel.addStretch(1)

        self.setLayout(panel)
        self.setWindowModality(Qt.NonModal)   
