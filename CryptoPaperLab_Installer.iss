#define MyAppName "Crypto Paper Lab"
#define MyAppVersion "1.0.0"
#define MyAppExeName "CryptoPaperLab.exe"

[Setup]
AppId={{933eb948-e225-4e8a-9650-0d3115adea5c}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\CryptoPaperLab
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Uninstallable=yes
PrivilegesRequired=lowest
OutputBaseFilename=CryptoPaperLab-Setup

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
