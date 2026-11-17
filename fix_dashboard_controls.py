with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\pages\dashboard.tsx', 'r') as f:
    content = f.read()

# Find and replace the useReplayControls call (specific line 219-221)
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
    print('old string not found')

with open(r'C:\Users\Survival\Documents\Default Project\\crypto-paper-trader\artifacts\crypto-paper-lab\src\pages\dashboard.tsx', 'w') as f:
    f.write(content)