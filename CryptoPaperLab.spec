# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import os

REPO_ROOT = os.path.abspath(os.getcwd())

# Data files that must be bundled
datas = [
    (os.path.join(REPO_ROOT, "research_engine", "data"), "research_engine/data"),
    (os.path.join(REPO_ROOT, "artifacts", "crypto-paper-lab", "dist", "public"), "frontend_dist"),
]

# Hidden imports: modules imported dynamically (inside lazy loaders)
hiddenimports = [
    "paper_api",
    "paper_api.app",
    "paper_api.assistant",
    "paper_api.assistant.tools",
    "paper_api.assistant.llm",
    "paper_api.assistant.history",
    "paper_api.brokers",
    "paper_api.brokers.base",
    "paper_api.brokers.risk",
    "paper_api.brokers.paper_adapter",
    "paper_api.brokers.live_config",
    "paper_api.brokers.binance_live",
    "paper_api.brokers.mt5_live",
    "crypto_paper_lab",
    "crypto_paper_lab.dataset",
    "crypto_paper_lab.walkforward",
    "crypto_paper_lab.researchguard",
    "crypto_paper_lab.registry_schema",
    "crypto_paper_lab.forex_session",
    "crypto_paper_lab.costs",
    "MetaTrader5",
    "openai",
    "uvicorn",
    "fastapi",
    "starlette",
]
hiddenimports += collect_submodules("paper_api")
hiddenimports += collect_submodules("crypto_paper_lab")

a = Analysis(
    ["desktop_launcher.py"],
    pathex=[os.path.join(REPO_ROOT, "research_engine", "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CryptoPaperLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no black window
    disable_windowed_traceback=False,
)
