with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\moderegistry.py', 'r') as f:
    content = f.read()

# Search for research_approval checks
print("=== Lines with research_approval ===")
for i, line in enumerate(content.split('\n')):
    if 'research_approval' in line.lower():
        print(f'Line {i+1}: {line.rstrip()}')

print("\n=== Lines with RESEARCH/CONSUME ===")
for i, line in enumerate(content.split('\n')):
    if 'RESEARCH' in line.upper() and ('APPROVED' in line.upper() or 'CONSUMED' in line.upper()):
        print(f'Line {i+1}: {line.rstrip()}')

print("\n=== Lines with DATA_VERIFIED ===")
for i, line in enumerate(content.split('\n')):
    if 'DATA_VERIFIED' in line.upper():
        print(f'Line {i+1}: {line.rstrip()}')