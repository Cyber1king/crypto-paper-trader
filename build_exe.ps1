# Build the frontend first
Push-Location artifacts/crypto-paper-lab
$env:PORT = "5173"
$env:BASE_PATH = "/"
pnpm build
Pop-Location

# Install PyInstaller if missing
pip install pyinstaller

# Clean previous build
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist

# Build the .exe
pyinstaller CryptoPaperLab.spec --clean --noconfirm

Write-Host ""
Write-Host "Build complete. Executable at: dist\CryptoPaperLab\CryptoPaperLab.exe" -ForegroundColor Green
