[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [AllowEmptyString()]
    [string]$CommitMessage,

    [switch]$SkipInstall,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
    Write-Host '[FAILED] A non-empty commit message is required. Usage: .\update.ps1 "commit message" [-SkipInstall] [-DryRun]' -ForegroundColor Red
    exit 1
}

function Invoke-UpdateStep {
    param(
        [int]$Number,
        [string]$Name,
        [string]$Label,
        [string]$Plan,
        [scriptblock]$Action
    )

    Write-Host "[$Number/5] $Label"
    if ($DryRun) {
        Write-Host "       Would run: $Plan"
        return
    }

    $locationPushed = $false
    try {
        Push-Location $RepoRoot
        $locationPushed = $true
        $global:LASTEXITCODE = 0
        & $Action
        if ($LASTEXITCODE -ne 0) {
            throw "Command returned exit code $LASTEXITCODE."
        }
    }
    catch {
        Write-Host "[FAILED] at step ${Number}: ${Name}" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }
    finally {
        if ($locationPushed) {
            Pop-Location
        }
    }
}

$commitPlan = "git add -A; git commit -m `"$CommitMessage`""
Invoke-UpdateStep -Number 1 -Name "Git add and commit" -Label "Staging and committing..." -Plan $commitPlan -Action {
    git add -A
    if ($LASTEXITCODE -ne 0) { throw "git add -A failed with exit code $LASTEXITCODE." }
    git commit -m $CommitMessage
    if ($LASTEXITCODE -ne 0) { throw "git commit failed with exit code $LASTEXITCODE." }
}

Invoke-UpdateStep -Number 2 -Name "Git push" -Label "Pushing to GitHub..." -Plan "git push origin main" -Action {
    git push origin main
    if ($LASTEXITCODE -ne 0) { throw "git push failed with exit code $LASTEXITCODE." }
}

Invoke-UpdateStep -Number 3 -Name "Rebuild executable" -Label "Rebuilding CryptoPaperLab.exe..." -Plan ".\build_exe.ps1" -Action {
    & .\build_exe.ps1
    if ($LASTEXITCODE -ne 0) { throw "build_exe.ps1 failed with exit code $LASTEXITCODE." }
}

Invoke-UpdateStep -Number 4 -Name "Rebuild installer" -Label "Rebuilding installer..." -Plan '& "C:\Users\Survival\AppData\Local\Programs\Inno Setup 6\ISCC.exe" "CryptoPaperLab_Installer.iss"' -Action {
    & "C:\Users\Survival\AppData\Local\Programs\Inno Setup 6\ISCC.exe" "CryptoPaperLab_Installer.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compiler failed with exit code $LASTEXITCODE." }
}

if ($SkipInstall) {
    Write-Host "[5/5] Installing updated app... (skipped by -SkipInstall)"
}
else {
    Invoke-UpdateStep -Number 5 -Name "Install updated app" -Label "Installing updated app..." -Plan 'Start-Process "Output\CryptoPaperLab-Setup.exe" -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait' -Action {
        $installer = Start-Process "Output\CryptoPaperLab-Setup.exe" -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
        if ($installer.ExitCode -ne 0) {
            throw "Installer returned exit code $($installer.ExitCode)."
        }
    }
}

if ($DryRun) {
    Write-Host "Dry run complete. No commands were executed."
}
elseif ($SkipInstall) {
    Write-Host "Update complete. Build finished; installation was skipped."
    Write-Host "Run Output\CryptoPaperLab-Setup.exe when you are ready to install."
}
else {
    Write-Host "Update complete. Version now installed."
    Write-Host 'Open the Desktop shortcut "Crypto Paper Lab" to use it.'
}
