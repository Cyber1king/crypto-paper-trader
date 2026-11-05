/** Money Management (Phase 27).
 * Allows manual entry and editing of real account balance and reserved funds.
 * Available funds = real balance - reserved funds.
 * Supports currency selection with reliable exchange rate conversion.
 * Entries are persisted across refreshes via localStorage.
 * Real money, reserved funds and paper-trading balances remain separate.
 */

import { useEffect, useState, useCallback } from "react";

import { Badge } from "@/components/ui";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Folder, Globe, Bitcoin, Euro } from "lucide-react";

/** Supported account currencies. */
type AccountCurrency = "USD" | "INR" | "GHS" | "EUR" | "GBP";

 /** Supported display (conversion) currencies. */
type DisplayCurrency = "USD" | "INR" | "GHS" | "EUR" | "GBP";

/** Exchange rates (fixed placeholder rates for UI demonstration).
 * In production these would be fetched from a reliable source.
 * Rates are expressed as 1 USD = <target_currency>.
 */
const exchangeRates: Record<DisplayCurrency, number> = {
  USD: 1,
  INR: 83,
  GHS: 14.5,
  EUR: 0.92,
  GBP: 0.78,
};

/** Format a number with appropriate precision for the given currency. */
function formatAmount(amount: number, currency: DisplayCurrency): string {
  const decimals = currency === "INR" || currency === "GHS" ? 2 : 2;
  return amount.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Parse a locale-formatted amount string back to a number. */
function parseAmount(value: string | null | undefined, currency: DisplayCurrency): number {
  if (value == null || value === "" || value === "—") return 0;
  const cleaned = value.replace(/[^\d.-]/g, "");
  const num = parseFloat(cleaned);
  return isNaN(num) ? 0 : num;
}

/** Convert an amount from the account currency to the display currency. */
function convertToDisplay(amount: number, from: AccountCurrency, to: DisplayCurrency): number {
  if (from === to) return amount;
  // Always convert via USD as base
  const amountInUsd = amount / exchangeRates[from as DisplayCurrency];
  return amountInUsd * exchangeRates[to];
}

/** Money Management component. */
export function MoneyManagement() {
  const [storedBalance, setStoredBalance] = useState(() => {
    try {
      const saved = localStorage.getItem("money-management:balance");
      return parseAmount(saved, "USD");
    } catch {
      return 0;
    }
  });

  const [storedReserved, setStoredReserved] = useState(() => {
    try {
      const saved = localStorage.getItem("money-management:reserved");
      return parseAmount(saved, "USD");
    } catch {
      return 0;
    }
  });

  // UI state (controlled from persisted state)
  const [balance, setBalance] = useState(storedBalance);
  const [reserved, setReserved] = useState(storedReserved);

  // Currency selection
  const [accountCurrency, setAccountCurrency] = useState<AccountCurrency>("USD");
  const [displayCurrency, setDisplayCurrency] = useState<DisplayCurrency>("USD");

  // Safe onValueChange handlers that convert string from Select to union type
  const onAccountCurrencyChange = useCallback(
    (value: string) => {
      const validCurrencies: AccountCurrency[] = ["USD", "INR", "GHS", "EUR", "GBP"] as AccountCurrency[];
      const currency = validCurrencies.find((c) => c === value);
      if (currency) {
        setAccountCurrency(currency);
      }
    },
    [setAccountCurrency]
  );

  const onDisplayCurrencyChange = useCallback(
    (value: string) => {
      const validCurrencies: DisplayCurrency[] = ["USD", "INR", "GHS", "EUR", "GBP"] as DisplayCurrency[];
      const currency = validCurrencies.find((c) => c === value);
      if (currency) {
        setDisplayCurrency(currency);
      }
    },
    [setDisplayCurrency]
  );

  // Computed values
  const available = balance - reserved;
  const balanceInDisplay = convertToDisplay(balance, accountCurrency, displayCurrency);
  const reservedInDisplay = convertToDisplay(reserved, accountCurrency, displayCurrency);
  const availableInDisplay = convertToDisplay(available, accountCurrency, displayCurrency);

  // Save to localStorage
  const saveToStorage = useCallback(
    (key: string, value: number) => {
      try {
        localStorage.setItem(key, value.toString());
      } catch (err) {
        console.warn("localStorage failed:", err);
      }
    },
    []
  );

  useEffect(() => {
    setStoredBalance(localStorage.getItem("money-management:balance")
      ? parseAmount(localStorage.getItem("money-management:balance"), "USD")
      : 0);
    setStoredReserved(localStorage.getItem("money-management:reserved")
      ? parseAmount(localStorage.getItem("money-management:reserved"), "USD")
      : 0);
  }, []);

  useEffect(() => {
    saveToStorage("money-management:balance", balance);
    saveToStorage("money-management:reserved", reserved);
  }, [balance, reserved, saveToStorage]);

  const handleBalanceChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = parseAmount(e.target.value, "USD");
      if (!isNaN(value)) {
        setBalance(value);
      }
    },
    [setBalance]
  );

  const handleReservedChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = parseAmount(e.target.value, "USD");
      if (!isNaN(value)) {
        setReserved(value);
      }
    },
    [setReserved]
  );

  return (
    <div className="p-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-6">Money Management</h1>

      {/* Balance section */}
      <div className="border rounded-lg p-4 mb-6 bg-card">
        <div className="flex justify-between items-start mb-3">
          <Label htmlFor="balance">Real Account Balance</Label>
          <span className="text-sm text-muted-foreground">
            (in {accountCurrency})
          </span>
        </div>
        <Input
          id="balance"
          type="number"
          step="0.01"
          value={formatAmount(balance, displayCurrency)}
          onChange={handleBalanceChange}
          placeholder="0.00"
          className="w-full"
        />
        <div className="mt-2 text-sm">
          <span className="me-4 font-mono text-primary">
            {formatAmount(balanceInDisplay, displayCurrency)} {displayCurrency}
          </span>
          <span className="me-4 font-mono text-muted-foreground">
            — Available: {formatAmount(availableInDisplay, displayCurrency)} {displayCurrency}
          </span>
          <span className="font-mono text-muted-foreground">
            — Reserved: {formatAmount(reservedInDisplay, displayCurrency)} {displayCurrency}
          </span>
        </div>
      </div>

      {/* Reserved funds section */}
      <div className="border rounded-lg p-4 mb-6 bg-card">
        <div className="flex justify-between items-start mb-3">
          <Label htmlFor="reserved">Reserved Funds</Label>
          <span className="text-sm text-muted-foreground">(in {accountCurrency})</span>
        </div>
        <Input
          id="reserved"
          type="number"
          step="0.01"
          value={formatAmount(reserved, displayCurrency)}
          onChange={handleReservedChange}
          placeholder="0.00"
          className="w-full"
        />
        <div className="mt-2 text-sm">
          <span className="me-4 font-mono text-primary">
            {formatAmount(reservedInDisplay, displayCurrency)} {displayCurrency}
          </span>
          <span className="font-mono text-muted-foreground">
            — Available: {formatAmount(availableInDisplay, displayCurrency)} {displayCurrency}
          </span>
        </div>
      </div>

      {/* Currency selector */}
      <div className="border rounded-lg p-4 bg-card mb-6">
        <Label className="block text-sm font-medium mb-2">Account Currency</Label>
        <Select onValueChange={onAccountCurrencyChange} defaultValue="USD">
          <SelectTrigger>
            <SelectValue>
              <span className="truncate">
                {accountCurrency}
              </span>
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="USD">USD</SelectItem>
            <SelectItem value="INR">INR</SelectItem>
            <SelectItem value="GHS">GHS</SelectItem>
            <SelectItem value="EUR">EUR</SelectItem>
            <SelectItem value="GBP">GBP</SelectItem>
          </SelectContent>
        </Select>

        <Label className="block text-sm font-medium mt-4 mb-2">Display Currency</Label>
        <Select onValueChange={onDisplayCurrencyChange} defaultValue="USD">
          <SelectTrigger>
            <SelectValue>
              <span className="truncate">
                {displayCurrency}
              </span>
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="USD">USD</SelectItem>
            <SelectItem value="INR">INR</SelectItem>
            <SelectItem value="GHS">GHS</SelectItem>
            <SelectItem value="EUR">EUR</SelectItem>
            <SelectItem value="GBP">GBP</SelectItem>
          </SelectContent>
        </Select>

        <p className="mt-3 text-xs text-muted-foreground">
          Rates are fixed placeholder values (1 USD = {exchangeRates[displayCurrency]} {displayCurrency}).
          Used for display conversion only; balances are stored in {accountCurrency}.
        </p>
      </div>

      {/* Summary */}
      <div className="border rounded-lg p-4 bg-card">
        <div className="flex justify-between items-center mb-2">
          <span className="font-medium">Available Funds</span>
          <span className="font-mono text-primary">
            {formatAmount(availableInDisplay, displayCurrency)} {displayCurrency}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          Real balance {formatAmount(balanceInDisplay, displayCurrency)} {displayCurrency}
          minus reserved {formatAmount(reservedInDisplay, displayCurrency)} {displayCurrency}
          = available {formatAmount(availableInDisplay, displayCurrency)} {displayCurrency}
        </p>
      </div>
    </div>
  );
}
