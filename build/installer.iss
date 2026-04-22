; Inno Setup Script – Plato Word Box Solver (single-exe edition)
; Requires Inno Setup 6+

#define MyAppName      "Plato Word Box Solver"
#define MyAppVersion   "1.2.1"
#define MyAppPublisher "Fabian Barua"
#define MyAppExeName   "WordBoxSolver.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=dist\installer
OutputBaseFilename=WordBoxSolver_Setup_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; Force-close a running instance so the .exe can be replaced on upgrade
CloseApplications=force
RestartApplications=no
; Make upgrades silent w.r.t. install dir / language selection
UsePreviousAppDir=yes
UsePreviousLanguage=yes
UsePreviousTasks=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Single exe (PyInstaller writes to <repo>/dist; this .iss lives in <repo>/build)
Source: "..\dist\WordBoxSolver.exe"; DestDir: "{app}"; Flags: ignoreversion

; Bundled scrcpy + adb (placed next to the exe so DeviceManager finds tools/ )
Source: "..\tools\scrcpy\*"; DestDir: "{app}\tools\scrcpy"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}";  Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";      Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
