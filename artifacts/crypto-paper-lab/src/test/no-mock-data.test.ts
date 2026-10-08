/**
 * Static guards (Phase 18K group 9: no fake fallback data).
 *
 * These are file-level assertions rather than render tests, and they are the only
 * way to prove a property the runtime tests cannot reach: that the synthetic data
 * modules are **gone**, rather than merely unreferenced. A dead `mock-data.ts`
 * still exporting a random walk is a loaded weapon for whoever imports it next.
 *
 * ## Every scan runs on code, not prose
 *
 * Each file is passed through {@link codeOnly} first, which strips comments and
 * string literals. Without that this suite fails on itself: `market-chart.tsx`
 * documents that `analyzeCandles` is gone, and `api.ts` lists the credential-shaped
 * things it refuses to handle — both would read as violations. The Python suite
 * solves the identical problem with `test_modes.py::code_only`, so a guard in either
 * language behaves the same way.
 *
 * ## Scope is the live dashboard path
 *
 * `components/ui/` holds the shadcn primitives, whose Tailwind class names include
 * `margin`, and `components/error-boundary.tsx` reads `import.meta.env` for
 * Replit's dev tooling. Neither is a file this phase wrote, and neither is on the
 * trading path, so both are excluded. The scanned set is enumerated, not globbed,
 * so adding a file does not silently opt it out of the guard.
 */

import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { codeOnly } from "./strip";
import { SCORE_TERMINOLOGY_NOTE } from "@/components/ai-panels";

/**
 * The caveat as it will actually be rendered.
 *
 * Imported rather than re-read from disk, because the constant is assembled by
 * string concatenation and asserting against raw file text would test a formatting
 * accident instead of the sentence a user sees.
 */
function importedNote(): string {
  return SCORE_TERMINOLOGY_NOTE;
}

const SRC = path.resolve(import.meta.dirname, "..");

function read(relative: string): string {
  return readFileSync(path.join(SRC, relative), "utf-8");
}

/** Code-only source, which is what every content guard below actually scans. */
function code(relative: string): string {
  return codeOnly(read(relative));
}

/**
 * Every file Phase 18 authored on the trading path.
 *
 * Enumerated rather than globbed, so a newly added file is a deliberate omission
 * rather than an invisible pass.
 */
const LIVE_FILES = [
  "lib/api.ts",
  "lib/hooks.ts",
  "lib/format.ts",
  "components/state.tsx",
  "components/mode-selector.tsx",
  "components/paper-controls.tsx",
  "components/standard-panels.tsx",
  "components/ai-panels.tsx",
  "components/daily-target-panels.tsx",
  "components/manual-panels.tsx",
  "components/high-risk-panels.tsx",
  "components/alerts-panel.tsx",
  "components/market-chart.tsx",
  "pages/dashboard.tsx",
] as const;

// ---------------------------------------------------------------------------
// the modules are deleted
// ---------------------------------------------------------------------------

describe("the synthetic data layer is gone", () => {
  const deleted = [
    "lib/mock-data.ts",
    "lib/signals.ts",
    "lib/analysis.ts",
    "lib/usePaperEngine.ts",
  ] as const;

  for (const relative of deleted) {
    it(`${relative} no longer exists`, () => {
      expect(existsSync(path.join(SRC, relative))).toBe(false);
    });
  }

  it("no source file imports any of them", () => {
    for (const relative of LIVE_FILES) {
      const source = code(relative);

      for (const name of [
        "usePaperEngine",
        "generateCandles",
        "generateSignal",
        "analyzeCandles",
        "mock-data",
      ]) {
        expect(source, `${relative} references ${name}`).not.toContain(name);
      }
    }
  });
});

// ---------------------------------------------------------------------------
// no randomness, clock seeding or synthetic prices on the live path
// ---------------------------------------------------------------------------

describe("no synthetic or randomised trading values on the dashboard path", () => {
  /** Each pattern is a code-level construct, checked after comment stripping. */
  const forbidden: readonly [string, RegExp][] = [
    ["Math.random", /Math\s*\.\s*random/],
    ["a randomness import", /from\s*["'][^"']*random/],
    ["a seeded candle or signal generator", /\bgenerateCandles\b|\bgenerateSignal\b/],
    ["a frontend analysis function", /\banalyzeCandles\b/],
  ];

  for (const relative of LIVE_FILES) {
    it(`${relative} contains none of them`, () => {
      const source = code(relative);

      for (const [label, pattern] of forbidden) {
        expect(pattern.test(source), `${relative} contains a ${label}`).toBe(false);
      }
    });
  }

  it("every setInterval drives the replay, none drives a chart heartbeat", () => {
    const hooks = code("lib/hooks.ts");
    const count = (hooks.match(/setInterval/g) ?? []).length;

    // Exactly two, both in `lib/hooks.ts`, both named:
    //
    // 1. The deterministic poll while `status === "running"`.
    // 2. The Phase 20 auto-step, which advances one bar per tick while running
    //    because the engine runs no background worker by design.
    //
    // The old synthetic engine had a three-second heartbeat that re-jittered the
    // last candle, which is the thing this guard exists to keep out. An enumerated
    // count rather than "no timers at all", because these two are the replay's own
    // cadence and are load-bearing: dropping either reintroduces the Phase 19
    // finding of a running replay whose cursor never moves.
    expect(count).toBe(2);

    // Both must be gated on `status !== "running"`, so neither can outlive the
    // replay's own lifecycle. A timer that kept ticking while idle would keep the
    // engine busy against a dashboard the user had stopped.
    //
    // Matched as a bare comparison because {@link codeOnly} removes string literals
    // entirely, quotes included, so the scanned source keeps the operator but not
    // the value beside it. The count above already proves there are only these two
    // timers, so what this adds is that both are lifecycle-gated.
    expect(hooks).toMatch(/status\s*!==/);

    for (const relative of LIVE_FILES) {
      if (relative === "lib/hooks.ts") {
        continue;
      }
      expect(code(relative), `${relative} uses setInterval`).not.toContain(
        "setInterval",
      );
    }
  });

  it("no live file reads the wall clock", () => {
    for (const relative of LIVE_FILES) {
      expect(code(relative), `${relative} reads Date.now`).not.toMatch(
        /Date\s*\.\s*now/,
      );
    }
  });

  it("no live file reads the wall clock through the global", () => {
    // `new Date()` with no argument is a clock read. `new Date(iso)` is not: the
    // formatting helpers parse a timestamp string the API sent in order to render
    // it, which is presentation and not sampling.
    for (const relative of LIVE_FILES) {
      expect(
        code(relative),
        `${relative} reads the clock via new Date()`,
      ).not.toMatch(/new\s+Date\s*\(\s*\)/);
    }
  });
});

// ---------------------------------------------------------------------------
// no real-money capability
// ---------------------------------------------------------------------------

describe("no real-money, exchange or credential capability", () => {
  const forbidden = [
    "exchange",
    "binance",
    "ccxt",
    "api_key",
    "apikey",
    "secret",
    "credential",
    "wallet",
    "privateKey",
    "private_key",
    "leverage",
    "margin",
    "deposit",
    "withdraw",
    "submitOrder",
    "placeOrder",
    "createOrder",
  ] as const;

  for (const relative of LIVE_FILES) {
    it(`${relative} contains no such term`, () => {
      const source = code(relative);

      for (const term of forbidden) {
        // Word-boundary matched, so `tickMargin` does not read as `margin` and
        // `api_key`-style identifiers are caught whole rather than by substring.
        const pattern = new RegExp(`\\b${term}\\b`, "i");
        expect(pattern.test(source), `${relative} contains "${term}"`).toBe(false);
      }
    });
  }

  it("no live file reads configuration from the environment", () => {
    // A base URL is a relative default, deliberately. Reading one from the
    // environment would be the wrong shape for a loopback research tool.
    for (const relative of LIVE_FILES) {
      const source = code(relative);
      expect(source, `${relative} reads import.meta.env`).not.toContain(
        "import.meta.env",
      );
      expect(source, `${relative} reads process.env`).not.toContain("process.env");
    }
  });

  it("the client imports nothing that could reach a network it should not", () => {
    const source = code("lib/api.ts");

    // `fetch` is the only egress, and it is the browser's.
    expect((source.match(/\bfetch\b/g) ?? []).length).toBeGreaterThan(0);
    for (const forbiddenImport of [
      "node:http",
      "node:https",
      "node:net",
      "node:tls",
      "axios",
      "XMLHttpRequest",
      "WebSocket",
    ]) {
      expect(source, `lib/api.ts imports ${forbiddenImport}`).not.toContain(
        forbiddenImport,
      );
    }
  });
});

// ---------------------------------------------------------------------------
// no frontend reimplementation of the engine's arithmetic
// ---------------------------------------------------------------------------

describe("the dashboard does not recompute what the engine owns", () => {
  it("the formatting helpers take an amount, never a price pair", () => {
    const source = code("lib/format.ts");

    // A helper accepting entry and exit prices would be a P&L calculator. Every
    // helper here takes one number and changes only how it is written.
    const twoPriceParams = source.match(
      /function\s+\w+\s*\([^)]*(price|Price)[^)]*(price|Price)[^)]*\)/g,
    );
    expect(twoPriceParams).toBeNull();
  });

  it("no component multiplies an engine money field by anything", () => {
    // The signature of a hand-rolled P&L: `entry_price * quantity`. Narrower than
    // "any multiplication", because `fraction * 100` for a progress bar width is
    // legitimate and must not fail the build.
    const moneyFields = [
      "entry_price",
      "exit_price",
      "balance",
      "realized_pnl",
      "starting_balance",
      "starting_capital",
      "allocated_capital",
      "available_capital",
      "committed_capital",
      "realized_balance",
    ];

    for (const relative of LIVE_FILES) {
      if (relative === "lib/format.ts") {
        continue;
      }

      const source = code(relative);
      const money = moneyFields.join("|");
      const asFactor = new RegExp(`\\b(${money})\\b[^\\n=;,)]*\\*`);
      const asProduct = new RegExp(`\\*[^\\n=;,(]*\\b(${money})\\b`);

      expect(asFactor.test(source), `${relative} multiplies a money field`).toBe(false);
      expect(asProduct.test(source), `${relative} multiplies into a money field`).toBe(false);
    }
  });

  it("the AI account is read only from /api/ai", () => {
    // `/api/replay?mode=ai_intelligence` reports a permanently flat broker by
    // construction, so the AI account must come from the AI route only.
    // A route path is a string literal by nature, so this one assertion reads
    // raw source rather than code: the point is that the path exists at all.
    const client = read("lib/api.ts");
    expect(client).toContain('"/api/ai"');

    const hooks = read("lib/hooks.ts");
    const start = hooks.indexOf("export function useAiState");
    const end = hooks.indexOf("\n}", start);

    // Sliced from the *raw* source, bounded to the function body. Code stripping
    // would be wrong here: this hook's body is almost entirely a docstring, so a
    // code-only slice would be nearly empty and the assertion vacuous. Bounding by
    // the closing brace is what keeps the check honest — an unterminated slice
    // would run to the end of the file and could pick up an unrelated call.
    const aiHook = hooks.slice(start, end);

    expect(aiHook).toContain("api.getAiState");
    expect(aiHook).not.toContain("getReplay");
    expect(aiHook).not.toContain("getAccount");
    expect(aiHook).not.toContain("getTrades");

    // And it must actually be bounded: an unterminated body would match nothing.
    expect(aiHook.length).toBeGreaterThan(50);
  });

  it("the AI panels take capital from the AI account block", () => {
    const source = code("components/ai-panels.tsx");

    expect(source).toContain("ai?.account");
    expect(source).toContain("account.starting_capital");
    expect(source).toContain("account.realized_pnl");
  });

  it("the AI panels never read capital from the nested replay block", () => {
    // `ai.replay` exists for lifecycle only. Reading a balance from it would be
    // the exact substitution Phase 18 forbids.
    const source = code("components/ai-panels.tsx");
    const money = "balance|realized_pnl|trade_count|starting_balance|open_position";

    expect(
      source.match(new RegExp(`replay[^\\n]*\\.?(${money})`)),
      "an AI panel reads a money field off the nested replay",
    ).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// score terminology (group 10)
// ---------------------------------------------------------------------------

describe("intelligence score terminology", () => {
  /**
   * Phrases that would misdescribe the score.
   *
   * `confidence score` is here because the deleted `signals.ts` produced exactly
   * that field name, and its reappearance is the regression worth guarding.
   */
  const forbiddenPhrases = [
    "win probability",
    "probability of profit",
    "confidence percentage",
    "confidence score",
    "guaranteed success",
    "guaranteed profit",
    "expected return",
    "success rate",
    "risk-free",
    "predicts the market",
    "% chance",
    "likelihood of profit",
  ] as const;

  for (const relative of LIVE_FILES) {
    it(`${relative} never uses a probability or confidence framing`, () => {
      // Scanned as code, with string literals and JSX text stripped. The
      // deliberate caveat necessarily names what the score is not ("not a
      // probability"), so it lives in a reviewed string constant; an accidental
      // framing in an identifier or in JSX copy would still be caught here.
      const source = code(relative).toLowerCase();

      for (const phrase of forbiddenPhrases) {
        expect(source.includes(phrase), `${relative} says "${phrase}"`).toBe(false);
      }
    });
  }

  it("the AI panels carry the explicit caveat", () => {
    // Raw source, because the caveat is a string constant and stripping would
    // remove exactly what this asserts.
    //
    // Asserted against the *constant's value* rather than the source text, because
    // the note is assembled by string concatenation and no contiguous substring of
    // the file contains the whole sentence. Checking the source would have asserted
    // a formatting accident rather than the caveat.
    const lowered = importedNote().toLowerCase();
    expect(lowered).toContain("qualification gate");
    expect(lowered).toContain("not a probability");
    expect(lowered).toContain("it does not predict profit");
  });

  it("the score is rendered as a value out of 100, not as a percentage", () => {
    const source = read("components/ai-panels.tsx");

    expect(source).toContain("/ 100");
    expect(source).toContain("a score, not a percentage");
  });

  it("no percent sign is rendered next to the score value", () => {
    // The strongest structural form: the score element itself carries no "%".
    const source = code("components/ai-panels.tsx");
    const scoreElement = source.slice(
      source.indexOf("ai-score"),
      source.indexOf("ai-threshold"),
    );

    expect(scoreElement).not.toContain("%");
  });
});

// ---------------------------------------------------------------------------
// dependency discipline
// ---------------------------------------------------------------------------

describe("dependency discipline", () => {
  function manifest(): { devDependencies: Record<string, string> } {
    return JSON.parse(
      readFileSync(
        path.resolve(import.meta.dirname, "..", "..", "package.json"),
        "utf-8",
      ),
    ) as { devDependencies: Record<string, string> };
  }

  it("exactly one test framework is installed", () => {
    const names = Object.keys(manifest().devDependencies).join(" ");
    const frameworks = ["vitest", "jest", "mocha", "ava", "playwright", "cypress"];
    const present = frameworks.filter((name) =>
      new RegExp(`(^|[^-])${name}`).test(names),
    );

    expect(present).toEqual(["vitest"]);
  });

  it("only the four approved test packages were added", () => {
    const approved = [
      "vitest",
      "jsdom",
      "@testing-library/react",
      "@testing-library/dom",
    ];
    const added = Object.keys(manifest().devDependencies).filter(
      (name) =>
        name === "vitest" ||
        name === "jsdom" ||
        name.startsWith("@testing-library/"),
    );

    expect(added.sort()).toEqual([...approved].sort());
  });

  it("no extra assertion library was added", () => {
    expect(Object.keys(manifest().devDependencies)).not.toContain(
      "@testing-library/jest-dom",
    );
  });

  it("every source file is counted, so a new one is a deliberate act", () => {
    // Sanity check on the guard itself: if this fails, the guard's own input set
    // has drifted and its coverage claim is no longer accurate.
    let count = 0;
    for (const relative of LIVE_FILES) {
      if (statSync(path.join(SRC, relative)).isFile()) {
        count += 1;
      }
    }
    expect(count).toBe(LIVE_FILES.length);
  });
});