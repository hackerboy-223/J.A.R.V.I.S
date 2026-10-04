; J.A.R.V.I.S. Windows installer
; Build the PyInstaller folder first, then compile this file with Inno Setup 6.

#define MyAppName "J.A.R.V.I.S."
#define MyAppVersion "0.1.0"
#define MyAppPublisher "H@CKERBOY"
#define MyAppExeName "JARVIS.exe"

[Setup]
AppId={{C1D67462-E64B-47AE-978A-7AA1CE61BE25}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\JARVIS
DefaultGroupName=J.A.R.V.I.S.
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=JARVIS-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes

[Files]
Source: "..\dist\J.A.R.V.I.S\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\J.A.R.V.I.S."; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\J.A.R.V.I.S."; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer J.A.R.V.I.S."; Flags: nowait postinstall skipifsilent
