/**
 * Test helpers shared by the Phase 18 static guards.
 */

/**
 * Strip comments, string literals and JSX text from TypeScript source.
 *
 * Necessary, and the reason is specific rather than defensive: every module in this
 * project documents at length what it deliberately does not contain, and the UI
 * states in prose what it is not. A guard reading raw source flags
 * `market-chart.tsx` for the sentence explaining that `analyzeCandles` is gone,
 * `api.ts` for a docstring listing credential-shaped things it refuses to handle,
 * and the paper-only banner for the words "No exchange, wallet or real capital".
 *
 * The Python suite hit exactly this and solves it the same way
 * (`test_modes.py::code_only`): strip, then scan. This is the same approach, so a
 * guard in either language behaves identically.
 *
 * Three kinds of non-code are removed:
 *
 * - line and block comments;
 * - the three string-literal quote forms, replaced by an empty placeholder so an
 *   identifier adjacent to a removed string keeps its spacing;
 * - JSX text between `>` and `<`, because a rendered sentence is not a capability.
 *
 * Not a full parser. It is a conservative stripper, which is sufficient for the
 * single question these guards ask: does *code* contain this construct?
 */
export function codeOnly(source: string): string {
  let out = "";
  let index = 0;

  while (index < source.length) {
    const char = source[index];
    const next = source[index + 1];

    // Line comment.
    if (char === "/" && next === "/") {
      while (index < source.length && source[index] !== "\n") {
        index += 1;
      }
      continue;
    }

    // Block comment.
    if (char === "/" && next === "*") {
      index += 2;
      while (index < source.length && !(source[index] === "*" && source[index + 1] === "/")) {
        index += 1;
      }
      index += 2;
      out += " ";
      continue;
    }

    // String literal in any of the three quote forms.
    if (char === '"' || char === "'" || char === "`") {
      const quote = char;
      index += 1;
      while (index < source.length && source[index] !== quote) {
        // Skip an escaped quote so `"a\"b"` does not terminate early.
        if (source[index] === "\\") {
          index += 1;
        }
        index += 1;
      }
      index += 1;
      out += ' "" ';
      continue;
    }

    out += char;
    index += 1;
  }

  return stripJsxText(out);
}

/**
 * Remove JSX text nodes.
 *
 * Only removes a run of plain characters with no angle brackets, braces or
 * newlines between two tags, so an expression container like `{value}` and any
 * multi-line JSX are left alone. A rendered sentence is presentation, and a
 * capability guard must not be satisfied by prose.
 */
function stripJsxText(source: string): string {
  return source.replace(/>([^<>{}]*[^<>{}\n][^<>{}]*)</g, '>""<');
}