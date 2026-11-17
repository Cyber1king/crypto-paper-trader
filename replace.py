#!/usr/bin/env python3
import re

path = r"C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\pages\dashboard.tsx"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# The old function to replace
old_func = '''/**
 * The header balance.
 * Shown only for Standard, because the header has one slot and the AI account must
 * not be labelled Standard's balance. When Standard is not selected, no balance
 * appears here at all rather than another mode's figure wearing its name.
 */
function StandardHeaderBalance(
  mode: ModeInfo | undefined,
  replay: { balance: number } | undefined,
  account: { balance: number } | undefined,
) {
  if (mode?.mode !== "standard") {
    return (
      <div className="text-right min-w-0" data-testid="header-no-balance">
        <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider break-words">
          Paper Balance
        </div>
        <div className="font-mono text-xl font-bold tracking-tight text-muted-foreground">
          —
        </div>
        <div className="text-[10px] text-muted-foreground font-mono">
          shown in the {mode?.label ?? "selected"} panel
        </div>
      </div>
    );
  }

  const balance = replay?.balance ?? account?.balance;

  return (
    <div className="text-right min-w-0">
      <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider break-words">
        Paper Balance
      </div>
      <div
        className="font-mono text-xl font-bold tracking-tight text-primary"
        data-testid="header-balance"
      >
        {balance === undefined
          ? "—"
          : balance.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
      </div>
    </div>
  );
}'''

# The new function
new_func = '''/** Get real account balance from localStorage (Money Management single source of truth). */
function getRealAccountBalanceFromStorage(): number {
  try {
    const saved = localStorage.getItem("money-management:balance");
    if (saved == null || saved === "" || saved === "—") return 0;
    const cleaned = saved.replace(/[^\\d.-]/g, "");
    const num = parseFloat(cleaned);
    return isNaN(num) ? 0 : num;
  } catch {
    return 0;
  }
}

/** Get reserved funds from localStorage (Money Management single source of truth). */
function getReservedFromStorage(): number {
  try {
    const saved = localStorage.getItem("money-management:reserved");
    if (saved == null || saved === "" || saved === "—") return 0;
    const cleaned = saved.replace(/[^\\d.-]/g, "");
    const num = parseFloat(cleaned);
    return isNaN(num) ? 0 : num;
  } catch {
    return 0;
  }
}

/** The header balance.
 * Shown only for Standard, because the header has one slot and the AI account must
 * not be labelled Standard's balance. When Standard is not selected, no balance
 * appears here at all rather than another mode's figure wearing its name.
 * The real account balance is the single source of truth, persisted via
 * localStorage (money-management:balance). Reserved funds and available funds are
 * calculated consistently: Available Funds = Real Account Balance - Reserved Funds.
 */
function StandardHeaderBalance(
  mode: ModeInfo | undefined,
  replay: { balance: number } | undefined,
  account: { balance: number } | undefined,
) {
  const realBalance = getRealAccountBalanceFromStorage();
  const reserved = getReservedFromStorage();
  const available = realBalance - reserved;

  if (mode?.mode !== "standard") {
    return (
      <div className="text-right min-w-0" data-testid="header-no-balance">
        <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider break-words">
          Real Account Balance
        </div>
        <div className="font-mono text-xl font-bold tracking-tight text-primary">
          {realBalance === undefined || isNaN(realBalance) ? "—" : realBalance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="text-[10px] text-muted-foreground font-mono">
          — Reserved: {reserved === undefined || isNaN(reserved) ? "—" : reserved.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
          — Available: {available === undefined || isNaN(available) ? "—" : available.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
        </div>
      </div>
    );
  }

  const displayBalance = realBalance !== undefined && !isNaN(realBalance) ? realBalance : (replay?.balance ?? account?.balance);

  return (
    <div className="text-right min-w-0">
      <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider break-words">
        Real Account Balance
      </div>
      <div
        className="font-mono text-xl font-bold tracking-tight text-primary"
        data-testid="header-balance"
      >
        {displayBalance === undefined || isNaN(displayBalance) ? "—" : displayBalance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
      <div className="text-xs text-muted-foreground">
        — Reserved: {reserved === undefined || isNaN(reserved) ? "—" : reserved.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
        — Available: {available === undefined || isNaN(available) ? "—" : available.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
      </div>
    </div>
  );
}'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Replacement successful")
else:
    print("OLD function not found - trying alternate match")
    # Try finding where StandardHeaderBalance starts
    idx = content.find("function StandardHeaderBalance(")
    if idx >= 0:
        print(f"Found at index: {idx}")
        # Print surrounding context
        print(content[idx-20:idx+200])