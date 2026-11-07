"""Load and enforce operator-editable per-instrument live-trading gates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .base import LiveTradingDisabled


@dataclass(frozen=True)
class InstrumentGate:
    """Live-trading permission and target environment for one instrument."""

    live_trading_permitted: bool
    environment: str
    note: str


def load_live_config(path: str | Path | None = None) -> dict:
    """Read live-trading configuration, defaulting to the project data file."""
    config_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parents[3] / "data" / "live_config.json"
    )
    if not config_path.is_file():
        raise FileNotFoundError(
            "live_config.json is missing; this file is required for live trading gating. "
            "Create it before enabling any live trading."
        )
    with config_path.open("r", encoding="utf-8-sig") as config_file:
        return json.load(config_file)


def get_instrument_gate(config: dict, instrument: str) -> InstrumentGate:
    """Return the configured gate for an instrument or raise a clear KeyError."""
    try:
        gate = config["instruments"][instrument]
    except KeyError as exc:
        raise KeyError(
            f"instrument {instrument!r} is not listed in live_config.json"
        ) from exc
    return InstrumentGate(
        live_trading_permitted=gate["live_trading_permitted"],
        environment=gate["environment"],
        note=gate["note"],
    )


def is_production_unlocked(config: dict) -> bool:
    """Return whether the separate production execution unlock is enabled."""
    return bool(config.get("global", {}).get("production_unlocked", False))


def check_live_gate(
    instrument: str,
    requested_environment: str,
    config_path: str | Path | None = None,
) -> None:
    """Refuse live use unless instrument, environment, and production gates pass."""
    config = load_live_config(config_path)
    gate = get_instrument_gate(config, instrument)
    if not gate.live_trading_permitted:
        raise LiveTradingDisabled(
            f"{instrument} live trading is not permitted in live_config.json"
        )
    if gate.environment != requested_environment:
        raise LiveTradingDisabled(
            f"{instrument} is configured for {gate.environment}, not {requested_environment}"
        )
    if requested_environment == "production" and not is_production_unlocked(config):
        raise LiveTradingDisabled("production is not unlocked in live_config.json")
