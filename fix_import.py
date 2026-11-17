#!/usr/bin/env python3
with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\crypto_paper_lab\dataset.py', 'r') as f:
    content = f.read()

# Replace the import
content = content.replace('from datetime import datetime', 'import datetime', 1)

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\crypto_paper_lab\dataset.py', 'w') as f:
    f.write(content)

print('Import fixed')