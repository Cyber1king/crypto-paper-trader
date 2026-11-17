with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\app.py', 'r') as f:
    content = f.read()

# Find def replay_start
idx = content.find('def replay_start(')
if idx >= 0:
    # Print the line
    lines = content[:idx].split('\n')
    print(f'Found at position {idx}')
    # Print surrounding context
    print('Lines around replay_start:')
    for i in range(max(0, idx//80 - 5), min(len(lines), idx//80 + 10)):
        print(f'{i+1}: {lines[i][:80]}')
else:
    print('def replay_start not found')