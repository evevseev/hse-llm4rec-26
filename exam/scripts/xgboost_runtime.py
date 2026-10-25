# Generated with an AI assistant
"""Load an optional project-local OpenMP runtime before importing XGBoost on macOS."""
import ctypes
import sys
from pathlib import Path

if sys.platform == 'darwin':
    runtime = Path(__file__).resolve().parents[1] / '.venv' / 'libomp' / 'lib' / 'libomp.dylib'
    if runtime.exists():
        ctypes.CDLL(str(runtime), mode=ctypes.RTLD_GLOBAL)

import xgboost  # noqa: E402

XGBRanker = xgboost.XGBRanker
