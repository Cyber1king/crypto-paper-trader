with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\pages\dashboard.tsx', 'r') as f:
    content = f.read()

# Find and replace the useReplayControls call
old_call = '''  const controls = useReplayControls(isControllable ? mode : undefined, {
    alsoRefresh: refreshKeys,
});'''

new_call = '''  const controls = useReplayControls(isControllable ? mode : undefined, selectedMarket, {
    alsoRefresh: refreshKeys,
});'''

if old_call in content:
    content = content.replace(old_call, new_call)
    print('useReplayControls call updated successfully')
else:
    print('old string not found - alternative search')
    # Try finding it differently
    idx = content.find('useReplayControls(isControllable')
    if idx >= 0:
        print(f'Found at {idx}')
        # Print context
        lines = content.split('\n')
        for i in range(idx//80, min((idx//80)+5, len(lines))):
            print(f'Line {i+1}: {lines[i][:100]}')

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\pages\dashboard.tsx', 'w') as f:
    f.write(content)