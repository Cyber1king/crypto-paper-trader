with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    lines = f.readlines()
# Print lines 255-300
for i in range(254, 300):
    if i < len(lines):
        print(f'{i+1}: {lines[i].rstrip()}')
PYEOF