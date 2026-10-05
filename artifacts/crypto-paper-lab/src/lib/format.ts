/**
 * Display-only formatting helpers (Phase 18).
 *
 * ## The one rule
 *
 * Every function here changes how a number is *written*, never what it *is*. There
 * is no arithmetic on trading quantities: no percentage of a position, no P&L from
 * two prices, no aggregate across trades. If a value is not in an API response it
 * is not displayed, and these helpers are never asked to produce one.
 *
 * That is why `formatMoney` takes an amount and not two prices. The moment a
 * helper accepts a pair of prices it becomes a P&L calculator, and the dashboard
 * grows a second accounting truth that can disagree with the engine's.
 */

const MONEY = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const MONEY_COMPACT = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const PRICE = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * A money amount, with a leading sign for signed values.
 *
 * `signed` exists so a P&L figure is visually distinguishable from a balance at a
 * glance. It only prefixes a character; the magnitude is untouched.
 */
export function formatMoney(value: number, signed = false): string {
  if (!Number.isFinite(value)) {
    return "—";
  }

  const body = MONEY.format(value);
  if (!signed || value === 0) {
    return body;
  }

  return `${value > 0 ? "+" : ""}${body}`;
}

/** A money amount with no decimals, for allocation-sized figures. */
export function formatMoneyCompact(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }

  return MONEY_COMPACT.format(value);
}

/** A price. Uses more precision than money, because BTC quotes need it. */
export function formatPrice(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }

  return PRICE.format(value);
}

/** A unit price with the asset's quote currency. */
export function formatQuoted(value: number, quote = "USDT"): string {
  if (!Number.isFinite(value)) {
    return "—";
  }

  return `${PRICE.format(value)} ${quote}`;
}

/** A signed percentage that the server itself produced, e.g. `win_rate`. */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }

  return `${value.toFixed(1)}%`;
}

/** A signed P&L figure with its currency. */
export function formatSignedMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }

  return `${value > 0 ? "+" : ""}${MONEY.format(value)}`;
}

/**
 * A signed *fraction* as a percentage.
 *
 * Used only for values the engine defines as fractions - `breakout_distance`,
 * `retest_distance`, and the realised-volatility proxy. Never used to derive a
 * return from a pair of prices.
 */
export function formatFractionAsPercent(
  value: number | null | undefined,
  digits = 4,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }

  return `${(value * 100).toFixed(digits)}%`;
}

/** A quantity of an asset, at the precision the engine recorded. */
export function formatQuantity(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }

  // 8 significant decimals is well beyond display needs and well inside what a
  // BTC-denominated size needs to be distinguishable from zero.
  return value.toFixed(8).replace(/0+$/, "").replace(/\.$/, "");
}

/** An integer count. */
export function formatCount(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }

  return value.toLocaleString("en-US");
}

/**
 * A UTC timestamp in a stable, readable form.
 *
 * Always rendered in UTC with a `Z`, because the dataset is UTC and a viewer's
 * local timezone would otherwise make two people's dashboards disagree about the
 * same replay. This is a presentation choice about one string, not a conversion
 * of any trading value.
 */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) {
    return "—";
  }

  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }

  const pad = (value: number, width = 2) => String(value).padStart(width, "0");

  return (
    `${parsed.getUTCFullYear()}-${pad(parsed.getUTCMonth() + 1)}-${pad(parsed.getUTCDate())}` +
    ` ${pad(parsed.getUTCHours())}:${pad(parsed.getUTCMinutes())}Z`
  );
}

/** Just the clock part, for chart axes. */
export function formatClock(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(parsed.getUTCHours())}:${pad(parsed.getUTCMinutes())}`;
}

/**
 * A date label for chart points, derived from the candle's own timestamp.
 *
 * The label is a slice of the API's timestamp string. Nothing here invents a date:
 * if the timestamp is absent the label is empty and the point renders unlabelled.
 */
export function chartLabel(iso: string | null | undefined): string {
  if (!iso) {
    return "";
  }

  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(parsed.getUTCMonth() + 1)}-${pad(parsed.getUTCDate())} ${pad(parsed.getUTCHours())}:${pad(parsed.getUTCMinutes())}`;
}

/** A short identity hash for display. Never abbreviated in a way that implies precision. */
export function shortHash(hash: string | null | undefined, length = 12): string {
  if (!hash) {
    return "—";
  }

  return hash.length <= length ? hash : `${hash.slice(0, length)}…`;
}

/** True when the value is absent, for rendering an explicit em dash. */
export function isAbsent(value: number | null | undefined): boolean {
  return value === null || value === undefined;
}

/**
 * A deterministic colour for a side, as a CSS custom-property reference.
 *
 * Presentation only. `long` and `short` map to the theme's success and destructive
 * tokens, so the palette stays in one place.
 */
export function sideClass(side: "long" | "short"): string {
  return side === "long"
    ? "text-success border-success/30 bg-success/10"
    : "text-destructive border-destructive/30 bg-destructive/10";
}

/** Human label for a replay status. */
export function statusLabel(status: string): string {
  switch (status) {
    case "idle":
      return "Idle";
    case "running":
      return "Running";
    case "paused":
      return "Paused";
    case "finished":
      return "Finished";
    default:
      return status;
  }
}

/** Human label for a signal side. */
export function sideLabel(side: string): string {
  switch (side) {
    case "long":
      return "Long";
    case "short":
      return "Short";
    case "flat":
      return "Flat";
    default:
      return side;
  }
}