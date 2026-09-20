"""Paper-only cryptocurrency strategy research tools."""

from .models import Candle, PaperTrade, Signal
from .strategy import StrategyConfig, analyze

__all__ = ["Candle", "PaperTrade", "Signal", "StrategyConfig", "analyze"]
