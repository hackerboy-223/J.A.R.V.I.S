; J.A.R.V.I.S. Windows installer
; Generated from the PyInstaller folder build.

#define MyAppName "J.A.R.V.I.S."
#define MyAppVersion "0.1.0"
#define MyAppPublisher "H@CKERBOY"
#define MyAppExeName "JARVIS.exe"

[Setup]
AppId={{D80A2C9E-62EF-4C6D-A2A3-5ED2EC13E9B1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
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
SetupLogging=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Files]
Source: "..\dist\J.A.R.V.I.S\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Icons]
Name: "{autoprograms}\J.A.R.V.I.S."; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\J.A.R.V.I.S."; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer J.A.R.V.I.S."; Flags: nowait postinstall skipifsilent
