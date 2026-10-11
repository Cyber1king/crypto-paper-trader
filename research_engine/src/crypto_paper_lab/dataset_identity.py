"""Declared dataset identity: what the file says it is, checked against how it is used.

Phase 41. Two problems this addresses, both real rather than theoretical:

1. **A dataset carries no identity.** ``load_ohlcv_csv`` returns a bare list of
   candles. Nothing records which instrument, timeframe or market the data
   represents, so a BTC-labelled configuration could be handed an ETH file with
   nothing to notice.

2. **Volume semantics are ambiguous.** A ``volume`` column could be centralised
   traded volume, tick volume, or something else entirely, and a backtest that
   mixes them across instruments is comparing different quantities.

The declared identity is therefore explicit, carried on a small immutable record
rather than inferred from a filename, and *checked* rather than trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "DatasetIdentity",
    "VOLUME_SEMANTICS",
    "MARKET_TYPES_SUPPORTED",
    "identity_for_registry_entry",
]

#: Volume semantics this repository understands. Anything else must be refused
#: rather than assumed.
#:
#: * ``central_base``   centralised, denominated in the base asset (Binance spot)
#: * ``central_quote``  centralised, denominated in the quote asset
#: * ``tick``           count of price changes; NOT a traded quantity
#: * ``none``           volume is absent by nature of the source (e.g. ECB
#:                      reference rates) and must never be fabricated
VOLUME_SEMANTICS = frozenset(
    {"central_base", "central_quote", "tick", "none"}
)

#: Market types with an implemented validator in this repository.
#:
#: Forex is deliberately absent. No session, holiday or DST validator exists
#: here, so claiming forex support would be false. See Phase 41's readiness
#: matrix rather than inferring readiness from this constant.
MARKET_TYPES_SUPPORTED = frozenset({"crypto_spot"})

#: Timeframes the pipeline can currently verify spacing for.
TIMEFRAMES_SUPPORTED = frozenset({"1h"})


@dataclass(frozen=True)
class DatasetIdentity:
    """What a dataset declares itself to be.

    Immutable and explicit: a caller must supply these fields rather than have
    them guessed from a path, because a guessed identity is exactly the failure
    mode this record exists to prevent.
    """

    instrument_id: str
    timeframe: str
    market_type: str
    volume_semantics: str
    dataset_sha256: str | None = None

    def __post_init__(self) -> None:
        for name in ("instrument_id", "timeframe", "market_type", "volume_semantics"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{name} must be a non-empty string; refusing to infer it"
                )

        if self.market_type not in MARKET_TYPES_SUPPORTED:
            raise ValueError(
                f"market_type {self.market_type!r} has no implemented validator "
                "in this repository. Supported: "
                + ", ".join(sorted(MARKET_TYPES_SUPPORTED))
                + ". Refused rather than approximated."
            )

        if self.volume_semantics not in VOLUME_SEMANTICS:
            raise ValueError(
                f"volume_semantics {self.volume_semantics!r} is not one of "
                + ", ".join(sorted(VOLUME_SEMANTICS))
                + ". Declaring it explicitly is required because a volume column "
                "alone does not say which quantity it holds."
            )

        if self.timeframe not in TIMEFRAMES_SUPPORTED:
            raise ValueError(
                f"timeframe {self.timeframe!r} cannot be validated here; "
                "supported: " + ", ".join(sorted(TIMEFRAMES_SUPPORTED))
            )

        if self.volume_semantics == "none" and self.market_type == "crypto_spot":
            # Crypto venues publish volume. Absence means the field was not
            # populated, not that the market has none.
            raise ValueError(
                "volume_semantics='none' is not valid for crypto_spot: a crypto "
                "venue publishes volume, so an absent value means the field was "
                "not populated. Absence is honest for forex reference rates only."
            )

    @property
    def expected_interval_seconds(self) -> int:
        """Spacing implied by the declared timeframe, for continuity checks."""

        return {"1h": 3600}[self.timeframe]

    def as_record(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "timeframe": self.timeframe,
            "market_type": self.market_type,
            "volume_semantics": self.volume_semantics,
            "dataset_sha256": self.dataset_sha256,
        }

    def assert_compatible_with_config(self, config_asset: str) -> None:
        """Refuse a config whose ``asset`` label disagrees with the dataset.

        ``StrategyConfig.asset`` is only a label, and nothing in the engine
        compared it to the data. Comparing it here makes an ETH dataset under a
        BTC-labelled config an explicit, recorded mismatch rather than a silent
        one.

        The frozen BTC configuration is never modified to make a dataset fit.
        """

        if str(config_asset) != self.instrument_id:
            raise ValueError(
                f"dataset is {self.instrument_id!r} but the strategy "
                f"configuration declares asset={config_asset!r}. Relabelling "
                "the data or the configuration is not permitted. An "
                "intentional cross-asset evaluation requires an explicit "
                "CrossAssetAuthorization in the research registry."
            )


def identity_for_registry_entry(entry: dict[str, Any]) -> DatasetIdentity:
    """Build a :class:`DatasetIdentity` from a registry instrument entry.

    Refuses rather than filling in defaults: an entry missing a field is
    malformed, and defaulting it would assert a fact nobody stated.
    """

    missing = [
        field
        for field in ("instrument_id", "market_type", "timeframe", "volume_semantics")
        if not str(entry.get(field, "")).strip()
    ]
    if missing:
        raise ValueError(
            "registry instrument entry is incomplete; missing: "
            + ", ".join(sorted(missing))
        )

    return DatasetIdentity(
        instrument_id=str(entry["instrument_id"]),
        timeframe=str(entry["timeframe"]),
        market_type=str(entry["market_type"]),
        volume_semantics=str(entry["volume_semantics"]),
        dataset_sha256=(
            str(entry["dataset_sha256"]) if entry.get("dataset_sha256") else None
        ),
    )