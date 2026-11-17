#!/usr/bin/env python3
with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\crypto_paper_lab\dataset.py', 'r') as f:
    lines = f.readlines()

# Insert after line 319 (0-indexed: 318), which is the docstring closing ""] 
insert_after = 318

new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if i == insert_after:
        new_lines.append('    # Resolve the effective market type. Callers may pass `market_type`\n')
        new_lines.append('    # explicitly; otherwise we fall back to the identity (which carries\n')
        new_lines.append('    # the same field). `None` means strict uniform interval checking.\n')
        new_lines.append('    if market_type is None and identity is not None:\n')
        new_lines.append('        market_type = getattr(identity, "market_type", None)\n')

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\crypto_paper_lab\dataset.py', 'w') as f:
    f.writelines(new_lines)

print('Lines inserted successfully')