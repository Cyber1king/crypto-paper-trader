from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .data import load_ohlcv_csv
from .models import Candle


@dataclass(frozen=True)
class DatasetSummary:
    candles: int
    start: datetime
    end: datetime


def load_dataset(
    path: str | Path,
) -> tuple[list[Candle], DatasetSummary]:
    """Load an OHLCV CSV and return its candles with a summary."""

    candles = load_ohlcv_csv(path)

    summary = DatasetSummary(
        candles=len(candles),
        start=candles[0].timestamp,
        end=candles[-1].timestamp,
    )

    return candles, summary


MARKET_TYPE_UNSUPPORTED = "market type has no implemented validator"


def _is_absolute_or_rooted(raw: "str | Path") -> bool:
    """True when ``raw`` names a filesystem location rather than a repo-relative one.

    Checked **before** any normalization, because normalization strips leading
    separators and would otherwise erase the very marker that distinguishes an
    absolute path from a relative one.

    Three spellings count, all of which a registry-relative declaration must
    never be confused with:

    * POSIX absolute -- ``/data/example.csv``
    * Windows drive -- ``C:\\data\\example.csv`` (and bare ``C:``)
    * Windows rooted or UNC -- ``\\data\\example.csv``, ``\\\\server\\share``

    Backslashes are folded to forward slashes first so the Windows forms are
    caught without needing ``os.path`` semantics, which differ per platform.
    """

    text = str(raw).replace("\\", "/")

    if text.startswith("/"):
        # Covers POSIX absolute, Windows rooted, and UNC.
        return True

    # Drive letter, with or without a following separator.
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        return True

    return False


def _canonical_dataset_path(raw: "str | Path") -> str:
    """Canonical lookup key for a registry dataset path.

    One policy, applied to both the requested path and every declared path, so
    two spellings of the same file cannot disagree:

    * backslashes become forward slashes, so a Windows-style declaration and a
      POSIX-style request compare equal;
    * ``.`` segments and repeated separators are dropped, so ``./data/x.csv``,
      ``data//x.csv`` and ``././data/x.csv`` are one key;
    * the result is case-folded, because the filesystem this runs on is
      case-insensitive on Windows and ``Data/X.csv`` names the same file as
      ``data/x.csv``. Without folding, two registry records differing only in
      case would resolve to different instruments for one physical file.

    Case folding also means a genuinely distinct record that differs only by
    case is treated as a *collision* rather than as a second dataset, which is
    the correct reading on a case-insensitive filesystem. Such records are
    reported as conflicting declarations rather than silently resolved.
    """

    text = str(raw).replace("\\", "/")
    segments = [segment for segment in text.split("/") if segment not in ("", ".")]
    return "/".join(segments).casefold()


def identity_for_dataset_path(
    dataset_path: "str | Path",
    registry: "dict",
) -> "object":
    """Resolve a dataset path to its declared :class:`DatasetIdentity`.

    The declaration comes from the registry manifest: the consumed-window or
    reservation record that names this dataset path, joined to its instrument
    entry. Both sections are searched because either can declare a dataset, and
    neither is preferred.

    Identity is deliberately **not** inferred from the candles. Bar contents
    describe the data; only the manifest states what that data is *declared* to
    be, and conflating the two would let a mislabelled series validate itself.

    Fails closed with :class:`RuntimeError` when the path is undeclared, the
    record names no instrument, the instrument is missing, when two registry
    records declare the same path with different identity-defining metadata, or
    when the manifest and the instrument entry disagree. Every one of those
    means nobody stated a single unambiguous fact this function needs, and
    inventing or picking one would be worse than refusing.

    Every matching declaration is collected before one is chosen, and a
    disagreement between them is an error rather than a first-match-wins
    lookup. A dataset declared under two instruments is a registry bug, and
    silently serving whichever happened to be listed first would hide it.

    This lives here rather than in the API layer so that consumers reach the
    engine through one interface instead of importing ``dataset_identity``
    directly.
    """

    from .dataset_identity import identity_for_registry_entry

    # Refuse an absolute or rooted path before canonicalization can drop the
    # leading separator. Registry declarations are repository-relative by
    # construction, so an absolute request can only ever be a caller passing a
    # different kind of path -- and silently reducing ``/data/x.csv`` to
    # ``data/x.csv`` would let it match a relative declaration it does not name.
    if _is_absolute_or_rooted(dataset_path):
        raise RuntimeError(
            f"dataset path {dataset_path!r} is absolute or filesystem-rooted. "
            "Registry declarations are repository-relative, so resolving one "
            "against this path could match a declaration it does not name. "
            "Refusing; pass the repository-relative path."
        )

    wanted = _canonical_dataset_path(dataset_path)

    # Every section can declare a dataset, so every section is searched and all
    # matches are kept. Keeping only the first would let a duplicate declaration
    # decide the served identity by list order.
    matches = [
        (section, record)
        for section in ("consumed_windows", "reservations")
        for record in registry.get(section) or []
        if record.get("dataset_path")
        and _canonical_dataset_path(record["dataset_path"]) == wanted
    ]

    if not matches:
        raise RuntimeError(
            f"dataset {dataset_path!r} has no registry declaration. Refusing to "
            "assign an identity nobody stated; add a consumed window or "
            "reservation for it."
        )

    # Agreement is required on every identity-defining field, not just the
    # instrument: two records naming one instrument but different timeframes
    # are just as contradictory as two different instruments.
    declarations = {
        (
            str(record.get("instrument_id") or "").strip(),
            str(record.get("timeframe") or "").strip(),
        )
        for _section, record in matches
    }

    if len(declarations) > 1:
        rendered = sorted(
            f"{instrument or '<none>'}/{timeframe or '<none>'}"
            for instrument, timeframe in declarations
        )
        sections = sorted({section for section, _record in matches})
        raise RuntimeError(
            f"conflicting registry declarations for {dataset_path!r}: "
            + " vs ".join(rendered)
            + f" (sections: {', '.join(sections)}). "
            "Refusing to reconcile; fix the registry so one dataset has one "
            "declared identity."
        )

    # ``dataset_sha256`` is also a DatasetIdentity field and is carried on
    # both record types, so agreeing on instrument and timeframe is not by
    # itself enough: two records claiming one path holds two different sets of
    # bytes are contradictory. Only records that actually state a digest are
    # compared -- an absent digest is unstated, not contradictory, so a record
    # that simply omits it does not manufacture a conflict.
    digests = {
        str(_section_record.get("dataset_sha256") or "").strip().casefold()
        for _section_record in (_record for _s, _record in matches)
    }
    digests.discard("")
    if len(digests) > 1:
        sections = sorted({section for section, _record in matches})
        raise RuntimeError(
            f"conflicting dataset_sha256 for {dataset_path!r}: "
            + " vs ".join(sorted(digests))
            + f" (sections: {', '.join(sections)}). One path cannot hold two "
            "sets of bytes. Refusing to reconcile; fix the registry."
        )

    entry = matches[0][1]

    instrument_id = entry.get("instrument_id")
    if not str(instrument_id or "").strip():
        raise RuntimeError(
            f"registry record for {dataset_path!r} names no instrument_id; "
            "refusing to guess one."
        )

    instrument = next(
        (
            i
            for i in registry.get("instruments") or []
            if i.get("instrument_id") == instrument_id
        ),
        None,
    )
    if instrument is None:
        raise RuntimeError(
            f"registry has no instrument entry for {instrument_id!r}, so "
            f"{dataset_path!r} cannot declare an identity."
        )

    identity = identity_for_registry_entry(instrument)

    # The manifest and the instrument record must still agree. Two registry
    # records disagreeing with each other is checked above; this is the
    # separate case of one record disagreeing with its own instrument entry.
    declared_timeframe = entry.get("timeframe")
    if declared_timeframe and str(declared_timeframe) != identity.timeframe:
        raise RuntimeError(
            f"registry record for {dataset_path!r} declares timeframe "
            f"{declared_timeframe!r} but instrument {instrument_id!r} declares "
            f"{identity.timeframe!r}. Refusing to reconcile; fix the registry."
        )

    return identity


def _check_timezone_consistency(candles: Sequence[Candle]) -> None:
    """Refuse a dataset mixing timezone-aware and naive timestamps.

    Comparing the two forms raises ``TypeError``, which a caller would see as a
    crash rather than as a data-quality refusal. Stating the check explicitly
    turns a confusing failure into an actionable message.

    All-aware and all-naive are both permitted: the loader normalises to naive
    UTC, so all-naive is the normal case and all-aware arises only when candles
    are constructed directly.
    """

    seen_aware: int | None = None
    seen_naive: int | None = None

    for index, candle in enumerate(candles):
        if candle.timestamp.tzinfo is None:
            seen_naive = index if seen_naive is None else seen_naive
        else:
            seen_aware = index if seen_aware is None else seen_aware
        if seen_aware is not None and seen_naive is not None:
            raise ValueError(
                "dataset mixes timezone-aware and naive timestamps "
                f"(naive at index {seen_naive}, aware at index {seen_aware}). "
                "Normalise every timestamp to naive UTC before validating; "
                "comparing the two forms is undefined."
            )


def _finite(value: float) -> bool:
    """True only for a real, finite float.

    ``inf`` and ``nan`` both satisfy ``inf >= inf``, so an ordering comparison
    alone cannot detect them. Every price is checked explicitly.
    """

    return value == value and value not in (float("inf"), float("-inf"))


def validate_dataset(
    candles: Sequence[Candle],
    *,
    expected_interval_seconds: int | None = None,
    market_type: str | None = None,
    instrument_id: str | None = None,
    timeframe: str | None = None,
    identity: "object | None" = None,
) -> None:
    """Validate that a dataset is usable for historical research.

    Unconditional checks: non-empty, prices finite and strictly positive, valid
    OHLC relationships, non-negative volume, and strictly increasing timestamps.

    Opt-in checks, because they require declared context that the candles alone
    cannot supply:

    ``expected_interval_seconds``
        Enforces an exact spacing. Omitted by default: an hourly series is not
        the only legitimate input, and a daily series would be wrongly refused.
    ``market_type``
        Refuses a market type with no implemented validator here. Forex is
        deliberately refused, because no session, holiday or DST validator exists
        in this repository.
    ``instrument_id`` / ``timeframe``
        Checked for presence when either is supplied, so a dataset used under a
        declared identity must carry one.
    ``identity``
        A :class:`~crypto_paper_lab.dataset_identity.DatasetIdentity`. Supplying
        it derives ``market_type`` and the expected spacing from the declaration
        rather than trusting the caller to pass matching values by hand. Phase 45
        added this because nothing previously connected a *declared* timeframe to
        the *actual* bar spacing: a caller could declare ``1h`` and validate
        5-minute data by simply not passing ``expected_interval_seconds``.
    """

    if not candles:
        raise ValueError("dataset contains no candles")

    if identity is not None:
        # A declaration is authoritative over ad-hoc arguments, and conflicting
        # values are a contradiction rather than something to reconcile silently.
        declared_type = getattr(identity, "market_type", None)
        declared_tf = getattr(identity, "timeframe", None)
        declared_interval = getattr(identity, "expected_interval_seconds", None)

        if market_type is not None and str(market_type) != str(declared_type):
            raise ValueError(
                f"market_type={market_type!r} contradicts the declared identity "
                f"{declared_type!r}. Refusing to reconcile; state one."
            )
        if timeframe is not None and str(timeframe) != str(declared_tf):
            raise ValueError(
                f"timeframe={timeframe!r} contradicts the declared identity "
                f"{declared_tf!r}. Refusing to reconcile; state one."
            )
        if expected_interval_seconds is not None and int(
            expected_interval_seconds
        ) != int(declared_interval):
            raise ValueError(
                f"expected_interval_seconds={expected_interval_seconds} "
                f"contradicts the declared timeframe {declared_tf!r}, which "
                f"implies {declared_interval}s. Refusing to reconcile; state one."
            )

        market_type = declared_type
        timeframe = declared_tf
        instrument_id = getattr(identity, "instrument_id", None) or instrument_id
        expected_interval_seconds = declared_interval

    if market_type is not None:
        from .researchguard import MARKET_TYPES_SUPPORTED

        if market_type not in MARKET_TYPES_SUPPORTED:
            raise ValueError(
                f"{MARKET_TYPE_UNSUPPORTED}: {market_type!r}. Supported here: "
                + ", ".join(sorted(MARKET_TYPES_SUPPORTED))
                + ". Refused rather than approximated."
            )

    if (instrument_id is None) != (timeframe is None):
        raise ValueError(
            "instrument_id and timeframe must be supplied together, or neither"
        )
    if instrument_id is not None and (
        not str(instrument_id).strip() or not str(timeframe).strip()
    ):
        raise ValueError(
            "instrument_id and timeframe must both be non-empty when declared"
        )

    for candle in candles:
        prices = (candle.open, candle.high, candle.low, candle.close)

        if not all(_finite(p) for p in (*prices, candle.volume)):
            raise ValueError(
                "dataset contains a non-finite price or volume"
            )

        # A zero or negative price satisfies every ordering comparison, so
        # positivity must be stated rather than inferred.
        if min(prices) <= 0:
            raise ValueError(
                "dataset contains a non-positive price"
            )

        if candle.high < candle.low:
            raise ValueError(
                "dataset contains an invalid high/low range"
            )

        if candle.high < max(candle.open, candle.close):
            raise ValueError(
                "dataset contains an open or close above its high"
            )

        if candle.low > min(candle.open, candle.close):
            raise ValueError(
                "dataset contains an open or close below its low"
            )

        if not (
            candle.low
            <= candle.open
            <= candle.high
        ):
            raise ValueError(
                "dataset contains an invalid open price"
            )

        if not (
            candle.low
            <= candle.close
            <= candle.high
        ):
            raise ValueError(
                "dataset contains an invalid close price"
            )

        if candle.volume < 0:
            raise ValueError(
                "dataset contains a negative volume"
            )

    _check_timezone_consistency(candles)

    for previous, current in zip(candles, candles[1:]):
        if current.timestamp <= previous.timestamp:
            raise ValueError(
                "dataset timestamps must be strictly increasing"
            )

        if expected_interval_seconds is not None:
            actual = int(
                (current.timestamp - previous.timestamp).total_seconds()
            )
            if actual != expected_interval_seconds:
                raise ValueError(
                    "dataset contains a non-uniform interval: expected "
                    f"{expected_interval_seconds}s, found {actual}s between "
                    f"{previous.timestamp} and {current.timestamp}"
                )
