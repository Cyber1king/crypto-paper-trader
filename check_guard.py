with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\crypto_paper_lab\researchguard.py', 'r') as f:
    content = f.read()

print("=== Lines with DATA_VERIFIED ===")
for i, line in enumerate(content.split('\n')):
    if 'DATA_VERIFIED' in line.upper():
        print(f'Line {i+1}: {line.rstrip()}')

print("\n=== Lines with RESEARCH_CONSUMED ===")
for i, line in enumerate(content.split('\n')):
    if 'RESEARCH_CONSUMED' in line.upper():
        print(f'Line {i+1}: {line.rstrip()}')

print("\n=== Lines with research_approval ===")
for i, line in enumerate(content.split('\n')):
    if 'research_approval' in line.lower():
        print(f'Line {i+1}: {line.rstrip()}')

print("\n=== Lines with MARKET_TYPES_BLOCKED ===")
for i, line in enumerate(content.split('\n')):
    if 'MARKET_TYPES_BLOCKED' in line or 'market_types_blocked' in line.lower():
        print(f'Line {i+1}: {line.rstrip()}')

print("\n=== Lines with is_forex_market_open ===")
for i, line in enumerate(content.split('\n')):
    if 'is_forex_market_open' in line:
        print(f'Line {i+1}: {line.rstrip()}')