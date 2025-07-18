from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from pathlib import Path

block_cipher = None

# ---------- assets you want copied verbatim ------------------
EXTRA_FILES = [
    ("loading.gif", "."),   # → Resources/loading.gif
    ("bot/NQ.txt",      "."),   # → Resources/nq.txt
    ("ACNBanner.png", "."),
]

# ---------- packages to pull in wholesale --------------------
hiddenimports = (
    collect_submodules("PySide6")       +
    collect_submodules("pandas._libs")  +
    collect_submodules("bokeh")         +
    collect_submodules("plotly")        +
    collect_submodules("backtesting")
)

datas = (
    collect_data_files("bokeh") +
    collect_data_files("plotly") +
    collect_data_files("backtesting") +
    EXTRA_FILES
)

# ---------- things you definitely don’t need -----------------
EXCLUDES = [
    # Windows / optional-GUI / dev-only
    "win32api","win32com","win32evtlog","winreg","nt","msvcrt",
    "_winapi","_overlapped","tkinter","IPython","jupyter",
    "pytest","pydevd","black","yapf","gevent","curio","kaleido",
    "OpenSSL","wx","gi","gtk","PyQt4","PySide2",
    # big data libs you don’t call
    "pyarrow","dask","duckdb","polars","cupy",
]

# =============================================================
a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=EXCLUDES,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ACN_Backtester",   # internal stub
    console=False,
    icon="ACN.icns",
    target_arch="arm64",   
)

app = BUNDLE(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="ACN Backtester.app",
    icon="ACN.icns",
    bundle_identifier="com.yourcompany.acnbacktester",
)
# =============================================================