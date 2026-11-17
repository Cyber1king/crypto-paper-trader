#!/usr/bin/env python
# Fix dashboard.tsx - add balance functions and update StandardHeaderBalance

with open('C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\artifacts\\crypto-paper-lab\\src\\pages\\dashboard.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# New functions to insert BEFORE StandardHeaderBalance
new_functions = '''(/** Get real account balance from localStorage (Money Management single source of truth). */
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

/**'''

# Insert the new functions before StandardHeaderBalance
# Find the position: "/** The header balance." comment which precedes StandardHeaderBalance
insert_marker = '/** The header balance.'
insert_pos = content.find(insert_marker)

if insert_pos >= 0:
    # Insert before the marker
    new_content = content[:insert_pos] + new_functions + content[insert_pos:]
    print(f"Inserted new functions at position {insert_pos}")
else:
    print("Insert marker not found!")
    exit(1)

# Now replace the StandardHeaderBalance function
old_func_start = 'function StandardHeaderBalance('
old_func_start_pos = new_content.find(old_func_start)

if old_func_start_pos >= 0:
    # Find the closing "}" of this function - need to count braces
    # The function ends at the last "}" before "interface ControlsProps" or the end
    # Let's find "interface ControlsProps" which comes after StandardHeaderBalance
    controls_props_pos = new_content.find('interface ControlsProps')
    
    if controls_props_pos >= 0:
        # The StandardHeaderBalance function is between old_func_start_pos and controls_props_pos
        # But we need to find the exact end of the function
        # Let's find the "}" that closes StandardHeaderBalance
        
        # Strategy: find the function body and its closing brace
        substring = new_content[old_func_start_pos:controls_props_pos]
        
        # Find the last "}" in this range that closes the function
        # We'll look for the pattern: "}" followed by newline and then the next function/interface
        # Actually, let's just find controls_props_pos and take everything before it
        # But we need to make sure we're not including other content
        
        # Let me just locate the exact function by finding from "function StandardHeaderBalance(" 
        # to the matching "}"
        
        # Count braces to find the matching closing brace
        brace_count = 0
        func_end = old_func_start_pos
        for i in range(old_func_start_pos, len(new_content)):
            if new_content[i] == '{':
                brace_count += 1
            elif new_content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    func_end = i + 1  # Include the closing brace
                    break
        
        print(f"Found StandardHeaderBalance from {old_func_start_pos} to {func_end}")
        
        # New replacement function
        new_func = '''(/** The header balance.
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

        # Replace
        replacement_start = old_func_start_pos
        replacement_end = func_end
        
        new_content = new_content[:replacement_start] + new_func + new_content[replacement_end:]
        print(f"Replaced StandardHeaderBalance function. New length: {len(new_content)}")
    else:
        print("Could not find 'interface ControlsProps'")
else:
    print("Could not find 'function StandardHeaderBalance('")

# Write the result
with open('C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\artifacts\\crypto-paper-lab\\src\\pages\\dashboard.tsx', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done! File written.")