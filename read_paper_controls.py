import os
path = r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\artifacts\\crypto-paper-lab\\src\\components\\paper-controls.tsx'
if os.path.exists(path):
    with open(path, 'r') as f:
        content = f.read()
    # Find the button section
    idx = content.index('/* Buttons */') if '/* Buttons */' in content else content.index('buttons') if 'buttons' in content.lower() else -1
    if idx >= 0:
        print(content[idx:idx+2000])
    else:
        # Just print the whole file
        print(content)
else:
    print('File not found')
    # Search
    for root, dirs, files in os.walk(r'C:\\Users\\Survival\\Documents\\Default Project\\crypto-paper-trader\\artifacts\\crypto-paper-lab\\src'):
        for f in files:
            if 'paper' in f.lower():
                print(os.path.join(root, f))